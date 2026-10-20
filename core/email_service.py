"""
Email service for sending automated reports.
Simple, reliable email delivery using standard SMTP.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
from datetime import datetime

from .config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Handles email sending for automated reports."""
    
    def __init__(self):
        """Initialize email service with configuration."""
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_user)
        self.from_name = os.getenv('FROM_NAME', 'Binomial Risk Analyst')
        
        # Validate configuration
        if not all([self.smtp_user, self.smtp_password]):
            logger.warning("Email service not configured. Set SMTP_USER and SMTP_PASSWORD environment variables.")
    
    def send_email(self,
                   recipient: str,
                   subject: str,
                   body: str,
                   attachments: Optional[List[tuple]] = None) -> bool:
        """
        Send email with optional attachments.
        
        Args:
            recipient: Email address to send to
            subject: Email subject line
            body: Email body (HTML supported)
            attachments: List of (filename, bytes) tuples
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("Email service not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'html'))
            
            # Add attachments
            if attachments:
                for filename, file_bytes in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(file_bytes)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


def send_report_email(recipient: str,
                     report_bytes: bytes,
                     subject: Optional[str] = None,
                     filename: Optional[str] = None) -> bool:
    """
    Send a report email with the document attached.
    
    Args:
        recipient: Email address to send to
        report_bytes: Report document as bytes
        subject: Email subject (defaults to standard subject)
        filename: Attachment filename (defaults to timestamped name)
        
    Returns:
        True if sent successfully
    """
    service = EmailService()
    
    # Default subject
    if not subject:
        subject = f"Binomial Risk Report - {datetime.now().strftime('%Y-%m-%d')}"
    
    # Default filename
    if not filename:
        filename = f"binomial_report_{datetime.now():%Y%m%d_%H%M}.docx"
    
    # Email body
    body = f"""
    <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #374151; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <img src="https://binomial.tech/logo.png" alt="Binomial" style="height: 40px; margin-bottom: 20px;">
                
                <h2 style="color: #0051CC; margin-bottom: 16px;">Your Risk Report is Ready</h2>
                
                <p>Your automated risk analysis report has been generated and is attached to this email.</p>
                
                <div style="background: #F3F4F6; padding: 16px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Report Details:</strong></p>
                    <ul style="margin: 8px 0 0 0; padding-left: 20px;">
                        <li>Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p %Z')}</li>
                        <li>Format: Microsoft Word (.docx)</li>
                        <li>Attachment: {filename}</li>
                    </ul>
                </div>
                
                <p>This report contains comprehensive risk analysis based on your portfolio configuration and the latest market data.</p>
                
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;">
                
                <p style="font-size: 12px; color: #6B7280; margin: 0;">
                    This is an automated email from Binomial Risk Analyst. 
                    To modify your report schedule or stop receiving these emails, 
                    please visit your dashboard at <a href="https://app.binomial.tech" style="color: #0051CC;">app.binomial.tech</a>.
                </p>
                
                <p style="font-size: 12px; color: #9CA3AF; margin-top: 16px;">
                    © {datetime.now().year} Binomial Technologies. All rights reserved.
                </p>
            </div>
        </body>
    </html>
    """
    
    # Send email with attachment
    return service.send_email(
        recipient=recipient,
        subject=subject,
        body=body,
        attachments=[(filename, report_bytes)]
    )


def send_test_email(recipient: str) -> bool:
    """
    Send a test email to verify configuration.
    
    Args:
        recipient: Email address to send test to
        
    Returns:
        True if sent successfully
    """
    service = EmailService()
    
    subject = "Binomial Risk Analyst - Test Email"
    body = f"""
    <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #374151;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #0051CC;">Email Configuration Test</h2>
                
                <p>This is a test email from Binomial Risk Analyst to verify your email configuration.</p>
                
                <div style="background: #10B981; color: white; padding: 12px; border-radius: 6px; margin: 20px 0;">
                    <strong>✓ Email service is working correctly!</strong>
                </div>
                
                <p>Configuration details:</p>
                <ul>
                    <li>SMTP Host: {service.smtp_host}</li>
                    <li>SMTP Port: {service.smtp_port}</li>
                    <li>From: {service.from_name} &lt;{service.from_email}&gt;</li>
                    <li>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}</li>
                </ul>
                
                <p style="margin-top: 20px; font-size: 14px; color: #6B7280;">
                    You can now schedule automated reports to be delivered to this email address.
                </p>
            </div>
        </body>
    </html>
    """
    
    return service.send_email(
        recipient=recipient,
        subject=subject,
        body=body
    )


# Convenience function for Flask app
def test_email_config() -> dict:
    """
    Test email configuration and return status.
    
    Returns:
        Dict with configuration status
    """
    service = EmailService()
    
    return {
        'configured': bool(service.smtp_user and service.smtp_password),
        'smtp_host': service.smtp_host,
        'smtp_port': service.smtp_port,
        'from_email': service.from_email,
        'from_name': service.from_name
    }