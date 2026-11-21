"""Slow vendor-outreach email blasts (anti-spam paced)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.suppression import hash_contact_value
from app.email_templates import (
    VENDOR_OUTREACH,
    VENDOR_OUTREACH_SUBJECT,
    VENDOR_OUTREACH_TEXT,
    load_template,
    logo_path,
)
from app.models.business import Business
from app.models.consent import SuppressionRecord
from app.models.contact import BusinessContact
from app.models.email_outbox import EmailBlast, EmailOutboxItem
from app.models.settings import SmtpSettings
from app.services.mailer import MailerError, send_email
from app.utils.email import is_valid_email_syntax, normalize_email

logger = logging.getLogger(__name__)

JUNK_SUBSTR = (
    "sentry.io",
    "wixpress.com",
    "example.com",
    "email.com",
    "mail.com",
    "test.com",
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
    "postmaster@",
    "@sentry.",
    "ingest.",
)


class OutreachError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def is_junk_email(email: str) -> bool:
    low = (email or "").lower()
    return any(j in low for j in JUNK_SUBSTR)


def pick_sendable_email(raw: str, normalized: Optional[str] = None) -> Optional[str]:
    norm = normalize_email(normalized or raw) or normalize_email(raw)
    if not norm or not is_valid_email_syntax(norm):
        return None
    if is_junk_email(norm):
        return None
    return norm


class OutreachService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_and_queue_vendor_blast(
        self,
        *,
        name: str = "Vendor outreach — slow send",
        delay_seconds: int = 75,
        daily_limit: int = 120,
        auto_start: bool = True,
    ) -> dict[str, Any]:
        smtp = await self._require_smtp()
        recipients = await self._collect_sendable_recipients()
        if not recipients:
            raise OutreachError("No sendable emails found after junk/suppression filters.")

        blast = EmailBlast(
            id=uuid4(),
            name=name,
            template=VENDOR_OUTREACH,
            status="draft",
            delay_seconds=max(45, int(delay_seconds)),
            daily_limit=max(20, int(daily_limit)),
            total_queued=0,
        )
        self.db.add(blast)
        await self.db.flush()

        queued = 0
        seen_emails: set[str] = set()
        for rec in recipients:
            email = rec["email"]
            if email in seen_emails:
                continue
            seen_emails.add(email)
            self.db.add(
                EmailOutboxItem(
                    id=uuid4(),
                    blast_id=blast.id,
                    business_id=rec["business_id"],
                    contact_id=rec["contact_id"],
                    to_email=email,
                    status="pending",
                )
            )
            queued += 1

        blast.total_queued = queued
        await self.db.flush()

        if auto_start:
            blast.status = "running"
            blast.started_at = datetime.now(timezone.utc)
            await self.db.commit()
            from app.workers.outreach_tasks import process_email_blast

            process_email_blast.delay(str(blast.id))
        else:
            await self.db.commit()

        await self.db.refresh(blast)
        return {
            "blast_id": str(blast.id),
            "name": blast.name,
            "status": blast.status,
            "queued": blast.total_queued,
            "delay_seconds": blast.delay_seconds,
            "daily_limit": blast.daily_limit,
            "from_email": smtp.from_email,
            "note": (
                "Sends one-by-one with delay to reduce spam risk. "
                f"Daily cap {blast.daily_limit}/day; resumes next UTC day automatically."
            ),
        }

    async def pause(self, blast_id: UUID) -> EmailBlast:
        blast = await self._get_blast(blast_id)
        if blast.status not in {"running", "waiting_daily_cap"}:
            raise OutreachError("Only running blasts can be paused")
        blast.status = "paused"
        await self.db.commit()
        await self.db.refresh(blast)
        return blast

    async def resume(self, blast_id: UUID) -> EmailBlast:
        blast = await self._get_blast(blast_id)
        if blast.status not in {"paused", "waiting_daily_cap", "draft"}:
            raise OutreachError("Blast cannot be resumed from this status")
        blast.status = "running"
        blast.completed_at = None
        await self.db.commit()
        from app.workers.outreach_tasks import process_email_blast

        process_email_blast.delay(str(blast.id))
        await self.db.refresh(blast)
        return blast

    async def status(self, blast_id: UUID) -> dict[str, Any]:
        blast = await self._get_blast(blast_id)
        pending = await self.db.scalar(
            select(func.count())
            .select_from(EmailOutboxItem)
            .where(
                EmailOutboxItem.blast_id == blast.id,
                EmailOutboxItem.status == "pending",
            )
        )
        return {
            "id": str(blast.id),
            "name": blast.name,
            "status": blast.status,
            "template": blast.template,
            "delay_seconds": blast.delay_seconds,
            "daily_limit": blast.daily_limit,
            "total_queued": blast.total_queued,
            "total_sent": blast.total_sent,
            "total_failed": blast.total_failed,
            "total_skipped": blast.total_skipped,
            "pending": int(pending or 0),
            "last_error": blast.last_error,
            "started_at": blast.started_at,
            "completed_at": blast.completed_at,
        }

    async def list_blasts(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(EmailBlast).order_by(EmailBlast.created_at.desc()).limit(limit)
            )
        ).scalars().all()
        return [
            {
                "id": str(b.id),
                "name": b.name,
                "status": b.status,
                "total_queued": b.total_queued,
                "total_sent": b.total_sent,
                "total_failed": b.total_failed,
                "pending_estimate": max(
                    b.total_queued - b.total_sent - b.total_failed - b.total_skipped, 0
                ),
                "delay_seconds": b.delay_seconds,
                "daily_limit": b.daily_limit,
            }
            for b in rows
        ]

    async def _get_blast(self, blast_id: UUID) -> EmailBlast:
        blast = await self.db.get(EmailBlast, blast_id)
        if blast is None:
            raise OutreachError("Email blast not found", 404)
        return blast

    async def _require_smtp(self) -> SmtpSettings:
        row = (
            await self.db.execute(
                select(SmtpSettings).order_by(SmtpSettings.created_at.asc()).limit(1)
            )
        ).scalar_one_or_none()
        if row is None or not row.host or not row.from_email or not row.password_encrypted:
            raise OutreachError("Configure SMTP in Settings before sending.", 400)
        if not row.is_enabled:
            raise OutreachError("Enable SMTP in Settings before sending.", 400)
        return row

    async def _collect_sendable_recipients(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(
                    Business.id,
                    BusinessContact.id,
                    BusinessContact.contact_value,
                    BusinessContact.normalized_value,
                )
                .join(BusinessContact, BusinessContact.business_id == Business.id)
                .where(
                    BusinessContact.contact_type == "business_email",
                    BusinessContact.contact_value.is_not(None),
                )
                .order_by(Business.created_at.asc())
            )
        ).all()

        suppressed = set(
            (
                await self.db.execute(
                    select(SuppressionRecord.contact_value_hash).where(
                        SuppressionRecord.contact_type == "business_email",
                        SuppressionRecord.channel.in_(["email", "all"]),
                    )
                )
            ).scalars().all()
        )

        # Never re-send vendor outreach to addresses already marked sent
        already_sent = set(
            (
                await self.db.execute(
                    select(func.lower(EmailOutboxItem.to_email))
                    .join(EmailBlast, EmailBlast.id == EmailOutboxItem.blast_id)
                    .where(
                        EmailOutboxItem.status == "sent",
                        EmailBlast.template == VENDOR_OUTREACH,
                    )
                )
            ).scalars().all()
        )

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for business_id, contact_id, value, normalized in rows:
            email = pick_sendable_email(value or "", normalized)
            if not email or email in seen:
                continue
            if email.lower() in already_sent:
                continue
            try:
                h = hash_contact_value(email)
            except Exception:
                h = None
            if h and h in suppressed:
                continue
            seen.add(email)
            out.append(
                {
                    "business_id": business_id,
                    "contact_id": contact_id,
                    "email": email,
                }
            )
        return out


class OutreachExecutionService:
    """Sync worker-side sender."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def process_next(self, blast_id: UUID) -> dict[str, Any]:
        blast = self.session.get(EmailBlast, blast_id)
        if blast is None:
            return {"status": "missing"}
        if blast.status == "paused":
            return {"status": "paused"}
        if blast.status in {"completed", "failed"}:
            return {"status": blast.status}

        # Daily cap (UTC day)
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sent_today = (
            self.session.execute(
                select(func.count())
                .select_from(EmailOutboxItem)
                .where(
                    EmailOutboxItem.blast_id == blast.id,
                    EmailOutboxItem.status == "sent",
                    EmailOutboxItem.sent_at >= start_of_day,
                )
            ).scalar_one()
        )
        if sent_today >= blast.daily_limit:
            blast.status = "waiting_daily_cap"
            blast.last_error = f"Daily cap reached ({blast.daily_limit}). Will resume next UTC day."
            self.session.commit()
            # schedule wake ~ next day + 5 min
            from app.workers.outreach_tasks import process_email_blast

            process_email_blast.apply_async(args=[str(blast.id)], countdown=3600)
            return {"status": "waiting_daily_cap", "sent_today": sent_today}

        item = (
            self.session.execute(
                select(EmailOutboxItem)
                .where(
                    EmailOutboxItem.blast_id == blast.id,
                    EmailOutboxItem.status == "pending",
                )
                .order_by(EmailOutboxItem.created_at.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if item is None:
            blast.status = "completed"
            blast.completed_at = datetime.now(timezone.utc)
            blast.last_error = None
            self.session.commit()
            return {"status": "completed", "sent": blast.total_sent}

        smtp = (
            self.session.execute(
                select(SmtpSettings).order_by(SmtpSettings.created_at.asc()).limit(1)
            )
            .scalars()
            .first()
        )
        if smtp is None or not smtp.is_enabled:
            blast.status = "failed"
            blast.last_error = "SMTP missing or disabled"
            self.session.commit()
            return {"status": "failed", "error": blast.last_error}

        item.status = "sending"
        item.attempt_count = (item.attempt_count or 0) + 1
        self.session.flush()

        try:
            html = load_template(blast.template or VENDOR_OUTREACH)
            # light personalization if business name known
            if item.business_id:
                biz = self.session.get(Business, item.business_id)
                if biz and biz.business_name:
                    # Don't heavily rewrite template; keep as-is for brand consistency
                    pass
            inline = {}
            logo = logo_path()
            if logo.is_file():
                inline["soouqlive-logo"] = logo
            send_email(
                smtp,
                to_email=item.to_email,
                subject=VENDOR_OUTREACH_SUBJECT,
                body_text=VENDOR_OUTREACH_TEXT,
                body_html=html,
                inline_images=inline or None,
                list_unsubscribe_email=smtp.from_email,
            )
            item.status = "sent"
            item.sent_at = datetime.now(timezone.utc)
            item.error = None
            blast.total_sent = (blast.total_sent or 0) + 1
            blast.status = "running"
            blast.last_error = None
        except MailerError as exc:
            item.status = "failed"
            item.error = exc.message
            blast.total_failed = (blast.total_failed or 0) + 1
            blast.last_error = exc.message
            # Auth / hard failures pause the blast
            if exc.status_code == 502 and "authentication" in exc.message.lower():
                blast.status = "failed"
                self.session.commit()
                return {"status": "failed", "error": exc.message}
        except Exception as exc:
            logger.exception("Unexpected outreach send failure")
            item.status = "failed"
            item.error = str(exc)
            blast.total_failed = (blast.total_failed or 0) + 1
            blast.last_error = str(exc)

        self.session.commit()

        # Schedule next pending item
        remaining = (
            self.session.execute(
                select(func.count())
                .select_from(EmailOutboxItem)
                .where(
                    EmailOutboxItem.blast_id == blast.id,
                    EmailOutboxItem.status == "pending",
                )
            ).scalar_one()
        )
        if remaining and blast.status == "running":
            from app.workers.outreach_tasks import process_email_blast

            process_email_blast.apply_async(
                args=[str(blast.id)],
                countdown=max(45, int(blast.delay_seconds or 75)),
            )
            return {
                "status": "scheduled_next",
                "sent_email": item.to_email if item.status == "sent" else None,
                "item_status": item.status,
                "remaining": remaining,
                "delay": blast.delay_seconds,
            }

        if remaining == 0 and blast.status == "running":
            blast.status = "completed"
            blast.completed_at = datetime.now(timezone.utc)
            self.session.commit()
        return {
            "status": blast.status,
            "item_status": item.status,
            "remaining": remaining,
            "total_sent": blast.total_sent,
        }
