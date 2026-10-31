"""Email delivery service for EduVerse AI password resets and notifications."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def is_email_configured() -> bool:
    """Check whether email delivery is configured via SMTP or development provider."""
    # Explicit provider override
    provider = os.getenv("EDUVERSE_EMAIL_PROVIDER", "").strip().lower()
    if provider == "none":
        return False
    if provider == "console" or provider == "dev":
        return True

    # In production, require actual SMTP host configuration
    is_prod = os.getenv("EDUVERSE_ENV", "development").strip().lower() in {"production", "prod"}
    smtp_host = os.getenv("EDUVERSE_SMTP_HOST", "").strip()
    if smtp_host:
        return True

    # If in local development and not explicitly disabled, console/logger delivery is available
    return not is_prod


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Send a secure password reset email containing single-use token or link."""
    base_url = os.getenv("EDUVERSE_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    reset_url = f"{base_url}/?reset_token={reset_token}"

    provider = os.getenv("EDUVERSE_EMAIL_PROVIDER", "").strip().lower()
    smtp_host = os.getenv("EDUVERSE_SMTP_HOST", "").strip()

    if smtp_host and provider != "console":
        # Dispatch via real SMTP server
        smtp_port = int(os.getenv("EDUVERSE_SMTP_PORT", "587"))
        smtp_user = os.getenv("EDUVERSE_SMTP_USER", "")
        smtp_pass = os.getenv("EDUVERSE_SMTP_PASSWORD", "")
        smtp_from = os.getenv("EDUVERSE_SMTP_FROM", "noreply@eduverse.ai")
        use_tls = os.getenv("EDUVERSE_SMTP_TLS", "true").lower() in {"true", "1", "yes"}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "EduVerse AI — Password Reset Request"
        msg["From"] = smtp_from
        msg["To"] = to_email

        text_content = f"""Hello,

We received a request to reset your password for your EduVerse AI account.

Your password reset token is:
{reset_token}

Or visit the following link to choose a new password:
{reset_url}

This link and token will expire in 1 hour. If you did not make this request, you can safely ignore this email.

— EduVerse AI Team
"""
        msg.attach(MIMEText(text_content, "plain"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())
            log.info("PASSWORD_RESET_EMAIL_DISPATCHED to %s via SMTP (%s)", to_email, smtp_host)
        except Exception as exc:
            log.error("SMTP delivery failed for %s: %s", to_email, exc)
            raise RuntimeError(f"Failed to dispatch password reset email: {exc}") from exc
    else:
        # Development / local testing delivery via secure audit log
        log.info("=================================================================")
        log.info("PASSWORD RESET DISPATCH [DEV MODE]")
        log.info("Recipient: %s", to_email)
        log.info("Reset Token: %s", reset_token)
        log.info("Reset URL: %s", reset_url)
        log.info("=================================================================")
