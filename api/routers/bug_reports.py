"""
Bug report endpoint with screenshot attachment support.
Sends bug reports via SES email to the support team.
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import smtplib
import time
import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from collections import defaultdict, deque

from core.config import get_config

config = get_config()
router = APIRouter(prefix="/api/bug-reports", tags=["bug-reports"])
logger = logging.getLogger(__name__)

# Rate limiting - simple sliding window per IP
rate_limit_store = defaultdict(lambda: deque())
RATE_LIMIT_WINDOW = 600  # 10 minutes
RATE_LIMIT_MAX = 10  # Max 10 bug reports per 10 minutes per IP

# Max screenshot size: 10MB
MAX_SCREENSHOT_SIZE = 10 * 1024 * 1024
MAX_SCREENSHOTS = 3


def check_rate_limit(ip: str) -> bool:
    """Check if IP is within rate limits"""
    now = time.time()
    requests = rate_limit_store[ip]

    # Remove old requests outside the window
    while requests and requests[0] < now - RATE_LIMIT_WINDOW:
        requests.popleft()

    if len(requests) >= RATE_LIMIT_MAX:
        return False

    requests.append(now)
    return True


def send_bug_report_email(
    title: str,
    description: str,
    severity: str,
    page_url: str,
    browser_info: str,
    user_email: Optional[str],
    user_name: Optional[str],
    screenshots: List[tuple] = None,  # List of (filename, content_bytes)
) -> None:
    """Send bug report email via SES SMTP with optional screenshot attachments"""

    ses_region = config.ses_region or "us-east-1"
    ses_smtp_server = config.ses_smtp_server or f"email-smtp.{ses_region}.amazonaws.com"
    ses_smtp_user = config.ses_smtp_user
    ses_smtp_password = config.ses_smtp_password
    
    # Bug reports go to support address
    bug_report_to = config.bug_report_to
    bug_report_from = config.contact_from or "noreply@bcmassets.com"

    if not ses_smtp_user or not ses_smtp_password:
        raise ValueError("SES SMTP credentials not configured")

    # Create email message
    msg = MIMEMultipart()
    msg['From'] = bug_report_from
    msg['To'] = bug_report_to
    msg['Subject'] = f"[{severity.upper()}] Bug Report: {title[:50]}"

    # Severity emoji for quick visual scanning
    severity_emoji = {
        'low': '🟢',
        'medium': '🟡', 
        'high': '🟠',
        'critical': '🔴'
    }.get(severity.lower(), '⚪')

    # Email body
    body = f"""
{severity_emoji} NEW BUG REPORT
{'=' * 50}

SEVERITY: {severity.upper()}
TITLE: {title}

REPORTED BY:
  Name: {user_name or 'Anonymous'}
  Email: {user_email or 'Not provided'}

CONTEXT:
  Page URL: {page_url or 'Not provided'}
  Browser: {browser_info or 'Not provided'}

DESCRIPTION:
{'-' * 50}
{description}
{'-' * 50}

ATTACHMENTS: {len(screenshots) if screenshots else 0} screenshot(s)

---
Submitted via Sentry Bug Reporter
"""

    msg.attach(MIMEText(body, 'plain'))

    # Attach screenshots
    if screenshots:
        for filename, content in screenshots:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            msg.attach(part)

    # Send email
    try:
        server = smtplib.SMTP(ses_smtp_server, 587)
        server.starttls()
        server.login(ses_smtp_user, ses_smtp_password)
        server.sendmail(bug_report_from, bug_report_to, msg.as_string())
        server.quit()
        logger.info(f"Bug report sent: {title[:30]}... ({severity})")
    except smtplib.SMTPAuthenticationError:
        logger.error("Bug report email auth failed", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable")
    except smtplib.SMTPException:
        logger.error("Bug report SMTP error", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable")
    except Exception:
        logger.error("Bug report send failed", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable")


@router.post("")
async def submit_bug_report(
    request: Request,
    title: str = Form(..., min_length=5, max_length=200),
    description: str = Form(..., min_length=10, max_length=5000),
    severity: str = Form(default="medium"),
    page_url: Optional[str] = Form(default=None),
    browser_info: Optional[str] = Form(default=None),
    user_email: Optional[str] = Form(default=None),
    user_name: Optional[str] = Form(default=None),
    screenshots: List[UploadFile] = File(default=[]),
):
    """
    Submit a bug report with optional screenshot attachments.
    
    - **title**: Brief summary of the bug (5-200 chars)
    - **description**: Detailed description including steps to reproduce (10-5000 chars)
    - **severity**: low, medium, high, or critical
    - **page_url**: URL where the bug occurred
    - **browser_info**: Browser/OS information
    - **user_email**: Reporter's email for follow-up
    - **user_name**: Reporter's name
    - **screenshots**: Up to 3 screenshot images (max 10MB each)
    """

    # Validate severity
    valid_severities = ['low', 'medium', 'high', 'critical']
    if severity.lower() not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity. Must be one of: {', '.join(valid_severities)}"
        )

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many bug reports. Please try again later."
        )

    # Process screenshots
    screenshot_data = []
    if screenshots:
        if len(screenshots) > MAX_SCREENSHOTS:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_SCREENSHOTS} screenshots allowed"
            )

        for i, screenshot in enumerate(screenshots):
            # Validate file type
            if screenshot.content_type and not screenshot.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {screenshot.filename} is not an image"
                )

            # Read content
            content = await screenshot.read()
            
            if len(content) > MAX_SCREENSHOT_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Screenshot {screenshot.filename} exceeds 10MB limit"
                )

            # Use original filename or generate one
            filename = screenshot.filename or f"screenshot_{i+1}.png"
            screenshot_data.append((filename, content))

    # Send the bug report
    try:
        send_bug_report_email(
            title=title,
            description=description,
            severity=severity.lower(),
            page_url=page_url,
            browser_info=browser_info,
            user_email=user_email,
            user_name=user_name,
            screenshots=screenshot_data,
        )
        return {
            "success": True,
            "message": "Bug report submitted successfully. Thank you for your feedback!"
        }
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.error("Bug report submission failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit bug report")

