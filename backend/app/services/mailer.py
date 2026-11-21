"""Outbound SMTP mail helper."""

from __future__ import annotations

import logging
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from app.models.settings import SmtpSettings
from app.utils.secret_box import decrypt_secret

logger = logging.getLogger(__name__)


class MailerError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _password(row: SmtpSettings) -> Optional[str]:
    if not row.password_encrypted:
        return None
    return decrypt_secret(row.password_encrypted)


def send_email(
    row: SmtpSettings,
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    inline_images: Optional[dict[str, Path]] = None,
    list_unsubscribe_email: Optional[str] = None,
) -> None:
    """Send email. inline_images maps Content-ID (without brackets) → file path."""
    if not row.is_enabled:
        raise MailerError("SMTP is disabled. Enable it in Settings first.")
    if not row.host or not row.from_email:
        raise MailerError("SMTP host and from_email are required.")

    msg = EmailMessage()
    msg["Subject"] = subject
    from_name = (row.from_name or "").strip()
    msg["From"] = f"{from_name} <{row.from_email}>" if from_name else row.from_email
    msg["To"] = to_email
    reply = row.reply_to or row.from_email
    if reply:
        msg["Reply-To"] = reply
    # Deliverability hints (one-to-one send, not blast headers)
    unsub = list_unsubscribe_email or row.from_email
    if unsub:
        msg["List-Unsubscribe"] = f"<mailto:{unsub}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg["X-Entity-Ref-ID"] = to_email  # helps some filters treat as unique
    msg.set_content(body_text)

    if body_html:
        msg.add_alternative(body_html, subtype="html")
        if inline_images:
            html_part = msg.get_payload()[-1]
            for cid, path in inline_images.items():
                file_path = Path(path)
                if not file_path.is_file():
                    logger.warning("Inline image missing: %s", file_path)
                    continue
                maintype, subtype = ("image", "png")
                guessed, _ = mimetypes.guess_type(str(file_path))
                if guessed and "/" in guessed:
                    maintype, subtype = guessed.split("/", 1)
                with file_path.open("rb") as fh:
                    html_part.add_related(
                        fh.read(),
                        maintype=maintype,
                        subtype=subtype,
                        cid=f"<{cid}>",
                        filename=file_path.name,
                    )

    password = _password(row)
    try:
        if row.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(row.host, row.port, timeout=30, context=context) as smtp:
                if row.username:
                    smtp.login(row.username, password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(row.host, row.port, timeout=30) as smtp:
                smtp.ehlo()
                if row.use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if row.username:
                    smtp.login(row.username, password or "")
                smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        logger.exception("SMTP auth failed")
        raise MailerError(f"SMTP authentication failed: {exc}", 502) from exc
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        logger.exception("SMTP send failed")
        raise MailerError(f"SMTP send failed: {exc}", 502) from exc
