"""
Email sending service for tasks and notifications.
"""

from __future__ import annotations

import logging
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, List, Optional

import aiosmtplib

from core.config import get_config

logger = logging.getLogger(__name__)


class EmailServiceError(RuntimeError):
    """Raised when email delivery fails."""


class EmailService:
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.tasks_email_enabled
        self.smtp_server = self.config.ses_smtp_server
        self.smtp_user = self.config.ses_smtp_user
        self.smtp_password = self.config.ses_smtp_password
        self.smtp_port = int(getattr(self.config, 'ses_smtp_port', 587))
        self.use_tls = True

    async def send_email(
        self,
        to_addresses: Iterable[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> None:
        if not self.enabled:
            logger.warning("Email service disabled; skipping send")
            return

        recipients = [addr for addr in to_addresses if addr]
        if not recipients:
            raise EmailServiceError("Email requires at least one recipient")

        override = self.config.tasks_email_override_to
        if override:
            logger.info("Overriding recipients -> %s", override)
            recipients = [override]

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.tasks_email_from
        message["To"] = ", ".join(recipients)
        message.set_content(text_body or "This email requires an HTML capable client.")
        message.add_alternative(html_body, subtype="html")

        # Add file attachments
        if attachments:
            for file_path in attachments:
                path = Path(file_path)
                if not path.exists():
                    logger.warning("Attachment not found, skipping: %s", file_path)
                    continue

                # Detect MIME type
                mime_type, _ = mimetypes.guess_type(str(path))
                if mime_type:
                    maintype, subtype = mime_type.split('/', 1)
                else:
                    maintype, subtype = 'application', 'octet-stream'

                # Read and attach file
                try:
                    with open(path, 'rb') as f:
                        file_data = f.read()
                        message.add_attachment(
                            file_data,
                            maintype=maintype,
                            subtype=subtype,
                            filename=path.name
                        )
                    logger.info("Attached file: %s (%s/%s)", path.name, maintype, subtype)
                except Exception as exc:
                    logger.error("Failed to attach file %s: %s", path.name, exc)

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_server,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=self.use_tls,
            )
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            raise EmailServiceError(str(exc)) from exc


_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    global _email_service  # pylint: disable=global-statement
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

