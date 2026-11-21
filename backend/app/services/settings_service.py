"""Application settings service (SMTP)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import SmtpSettings
from app.services.mailer import MailerError, send_email
from app.utils.secret_box import encrypt_secret


class SettingsError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SettingsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_smtp(self) -> SmtpSettings:
        row = await self._get_or_create()
        return row

    def to_out(self, row: SmtpSettings) -> dict[str, Any]:
        return {
            "id": row.id,
            "host": row.host or "",
            "port": row.port or 587,
            "username": row.username,
            "password_set": bool(row.password_encrypted),
            "from_email": row.from_email or "",
            "from_name": row.from_name,
            "reply_to": row.reply_to,
            "use_tls": bool(row.use_tls),
            "use_ssl": bool(row.use_ssl),
            "is_enabled": bool(row.is_enabled),
            "updated_at": row.updated_at,
        }

    async def update_smtp(self, payload: dict[str, Any]) -> SmtpSettings:
        row = await self._get_or_create()
        host = (payload.get("host") or "").strip()
        from_email = (payload.get("from_email") or "").strip()
        port = int(payload.get("port") or 587)
        use_tls = bool(payload.get("use_tls", True))
        use_ssl = bool(payload.get("use_ssl", False))
        if use_tls and use_ssl:
            raise SettingsError("Use either TLS (STARTTLS) or SSL, not both.")

        row.host = host
        row.port = port
        row.username = (payload.get("username") or None) or None
        if row.username is not None:
            row.username = str(row.username).strip() or None
        row.from_email = from_email
        row.from_name = (payload.get("from_name") or None) or None
        if row.from_name is not None:
            row.from_name = str(row.from_name).strip() or None
        reply = payload.get("reply_to")
        row.reply_to = str(reply).strip() if reply else None
        row.use_tls = use_tls
        row.use_ssl = use_ssl
        row.is_enabled = bool(payload.get("is_enabled", False))

        password = payload.get("password")
        if password is not None and str(password).strip() != "":
            row.password_encrypted = encrypt_secret(str(password))

        if row.is_enabled and (not row.host or not row.from_email):
            raise SettingsError("Enable requires host and from_email.")

        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def test_smtp(
        self,
        *,
        to_email: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        use_template: bool = True,
        template: str = "vendor_outreach",
    ) -> dict[str, Any]:
        from app.email_templates import (
            VENDOR_OUTREACH,
            VENDOR_OUTREACH_SUBJECT,
            VENDOR_OUTREACH_TEXT,
            load_template,
            logo_path,
        )

        row = await self._get_or_create()
        try:
            # Allow test even if not enabled, as long as host/from are set
            if not row.host or not row.from_email:
                raise SettingsError("Save SMTP host and from_email before testing.")

            body_html = None
            inline_images = None
            template_used = None
            if use_template:
                name = template or VENDOR_OUTREACH
                try:
                    body_html = load_template(name)
                except FileNotFoundError as exc:
                    raise SettingsError(str(exc), 404) from exc
                body_text = body or VENDOR_OUTREACH_TEXT
                subject_final = subject or VENDOR_OUTREACH_SUBJECT
                logo = logo_path()
                if logo.is_file():
                    inline_images = {"soouqlive-logo": logo}
                template_used = name
            else:
                body_text = body or (
                    "This is a test email from SoouqLive Merchant Discovery SMTP settings."
                )
                subject_final = subject or "SoouqLive SMTP test"

            was_enabled = row.is_enabled
            row.is_enabled = True
            try:
                send_email(
                    row,
                    to_email=to_email,
                    subject=subject_final,
                    body_text=body_text,
                    body_html=body_html,
                    inline_images=inline_images,
                )
            finally:
                row.is_enabled = was_enabled
        except MailerError as exc:
            raise SettingsError(exc.message, exc.status_code) from exc
        return {
            "sent": True,
            "to_email": to_email,
            "subject": subject_final,
            "template": template_used,
        }

    async def _get_or_create(self) -> SmtpSettings:
        result = await self.db.execute(
            select(SmtpSettings).order_by(SmtpSettings.created_at.asc()).limit(1)
        )
        row: Optional[SmtpSettings] = result.scalar_one_or_none()
        if row is not None:
            return row
        row = SmtpSettings(
            id=uuid4(),
            host="",
            port=587,
            from_email="",
            use_tls=True,
            use_ssl=False,
            is_enabled=False,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row
