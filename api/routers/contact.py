from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, validator, EmailStr
from typing import Optional
import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict, deque
from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client

config = get_config()
router = APIRouter(prefix="/api/contact", tags=["contact"])
logger = logging.getLogger(__name__)

# Rate limiting - simple sliding window per IP
rate_limit_store = defaultdict(lambda: deque())
RATE_LIMIT_WINDOW = 600  # 10 minutes
RATE_LIMIT_MAX = 5  # Max 5 requests per 10 minutes per IP

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None
    message: str
    website: Optional[str] = None  # Honeypot field

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Name is required')
        if len(v) > 200:
            raise ValueError('Name must be 200 characters or less')
        return v.strip()

    @validator('email')
    def validate_email(cls, v):
        if len(str(v)) > 255:
            raise ValueError('Email must be 255 characters or less')
        return v

    @validator('company')
    def validate_company(cls, v):
        if v and len(v) > 200:
            raise ValueError('Company must be 200 characters or less')
        return v.strip() if v else None

    @validator('title')
    def validate_title(cls, v):
        if v and len(v) > 200:
            raise ValueError('Title must be 200 characters or less')
        return v.strip() if v else None

    @validator('message')
    def validate_message(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Message is required')
        if len(v) > 5000:
            raise ValueError('Message must be 5000 characters or less')
        return v.strip()

    @validator('website')
    def validate_honeypot(cls, v):
        if v:  # If honeypot field is filled, it's spam
            raise ValueError('Invalid submission')
        return v

def check_rate_limit(ip: str) -> bool:
    """Check if IP is within rate limits"""
    now = time.time()
    requests = rate_limit_store[ip]

    # Remove old requests outside the window
    while requests and requests[0] < now - RATE_LIMIT_WINDOW:
        requests.popleft()

    # Check if within limit
    if len(requests) >= RATE_LIMIT_MAX:
        return False

    # Add current request
    requests.append(now)
    return True

def send_contact_email(request_data: ContactRequest) -> None:
    """Send contact form email via SES SMTP"""

    # Get SES configuration from environment
    ses_region = config.ses_region or "us-east-1"
    ses_smtp_server = config.ses_smtp_server or f"email-smtp.{ses_region}.amazonaws.com"
    ses_smtp_user = config.ses_smtp_user
    ses_smtp_password = config.ses_smtp_password
    contact_to = config.contact_to or "contact@bcmassets.com"
    contact_from = config.contact_from or "contact@bcmassets.com"

    if not ses_smtp_user or not ses_smtp_password:
        raise ValueError("SES SMTP credentials not configured")

    # Create email message
    msg = MIMEMultipart()
    msg['From'] = contact_from
    msg['To'] = contact_to
    msg['Subject'] = f"Contact Form Submission from {request_data.name}"

    # Email body
    body = f"""
New contact form submission:

Name: {request_data.name}
Email: {request_data.email}
Company: {request_data.company or 'Not provided'}
Title: {request_data.title or 'Not provided'}

Message:
{request_data.message}
"""

    msg.attach(MIMEText(body, 'plain'))

    # Send email
    try:
        server = smtplib.SMTP(ses_smtp_server, 587)
        server.starttls()
        server.login(ses_smtp_user, ses_smtp_password)
        server.sendmail(contact_from, contact_to, msg.as_string())
        server.quit()
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("Contact email authentication failed with SES; verify SMTP credentials are current.", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable. Please contact support while we resolve our mail configuration.")
    except smtplib.SMTPException as exc:
        logger.error("Contact email send failed due to SMTP error.", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable. Please contact support while we resolve our mail configuration.")
    except Exception as exc:
        logger.error("Unexpected error sending contact email.", exc_info=True)
        raise ValueError("Email delivery temporarily unavailable. Please contact support while we resolve our mail configuration.")

@router.post("")
async def submit_contact_form(request: ContactRequest, raw_request: Request):
    """Submit contact form with rate limiting and email notification"""

    # Get client IP for rate limiting
    client_ip = raw_request.client.host if raw_request.client else "unknown"

    # Check rate limit
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )

    db_recorded = False

    if config.enable_postgres:
        try:
            pg = await get_postgres_rls_client()
            # Use None for user_id since this is a public endpoint
            async with pg.acquire_with_user_context(None) as conn:
                await conn.execute("""
                    INSERT INTO demo_requests (name, email, company, title, message, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """, request.name, str(request.email), request.company, request.title, request.message)
                db_recorded = True
        except Exception as e:
            # Don't block on database failures, just log
            logger.warning("Failed to store contact request in database.", exc_info=True)

    try:
        # Send email notification after persisting the request
        send_contact_email(request)
        return {"message": "Contact form submitted successfully"}
    except ValueError as exc:
        if db_recorded:
            detail = (
                "Your request was received, but our email service is temporarily unavailable. "
                "Our team will follow up shortly."
            )
        else:
            detail = (
                "Email delivery is temporarily unavailable. Please try again later or reach us at contact@bcmassets.com."
            )
        raise HTTPException(status_code=503, detail=detail) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process contact form")

