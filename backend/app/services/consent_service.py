"""Consent recording, withdrawal, and outreach eligibility."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.consent import (
    CONSENT_CHANNELS,
    CONSENT_METHODS,
    CONSENT_PURPOSES,
    CONSENT_STATUSES,
    purpose_matches_channel,
)
from app.compliance.suppression import add_suppression, is_suppressed
from app.models.activity import Activity
from app.models.business import Business
from app.models.consent import ConsentRecord
from app.models.contact import BusinessContact
from app.models.source import DataProvider, LeadSource
from app.models.user import User


class ConsentError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": self.reasons,
            "checks": self.checks,
            "note": (
                "Publicly visible business contact details must not automatically "
                "be treated as permission for unsolicited promotional messages."
            ),
        }


class ConsentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_consent(
        self,
        *,
        business_id: Optional[UUID] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[ConsentRecord], int]:
        stmt = select(ConsentRecord)
        count_stmt = select(func.count()).select_from(ConsentRecord)
        if business_id:
            stmt = stmt.where(ConsentRecord.business_id == business_id)
            count_stmt = count_stmt.where(ConsentRecord.business_id == business_id)
        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(ConsentRecord.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get_business_consent(self, business_id: UUID) -> list[ConsentRecord]:
        business = await self.db.get(Business, business_id)
        if business is None:
            raise ConsentError("Business not found", 404)
        rows = (
            await self.db.execute(
                select(ConsentRecord)
                .where(ConsentRecord.business_id == business_id)
                .order_by(ConsentRecord.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def record_consent(
        self,
        *,
        business_id: UUID,
        purpose: str,
        channel: str,
        consent_status: str,
        consent_method: str,
        user: User,
        contact_id: Optional[UUID] = None,
        consent_evidence: Optional[dict[str, Any]] = None,
        consented_at: Optional[datetime] = None,
    ) -> ConsentRecord:
        if purpose not in CONSENT_PURPOSES:
            raise ConsentError(f"Invalid purpose. Allowed: {sorted(CONSENT_PURPOSES)}")
        if channel not in CONSENT_CHANNELS:
            raise ConsentError(f"Invalid channel. Allowed: {sorted(CONSENT_CHANNELS)}")
        if consent_status not in CONSENT_STATUSES:
            raise ConsentError(f"Invalid consent_status. Allowed: {sorted(CONSENT_STATUSES)}")
        if consent_method not in CONSENT_METHODS:
            raise ConsentError(f"Invalid consent_method. Allowed: {sorted(CONSENT_METHODS)}")
        if not purpose_matches_channel(purpose, channel):
            raise ConsentError(f"Purpose '{purpose}' is not valid for channel '{channel}'")

        business = await self.db.get(Business, business_id)
        if business is None:
            raise ConsentError("Business not found", 404)

        contact = None
        if contact_id:
            contact = await self.db.get(BusinessContact, contact_id)
            if contact is None or contact.business_id != business_id:
                raise ConsentError("Contact not found for business", 404)

        if consent_status == "granted" and not consent_evidence:
            raise ConsentError("consent_evidence is required when granting consent")

        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            id=uuid.uuid4(),
            business_id=business_id,
            contact_id=contact_id,
            purpose=purpose,
            channel=channel,
            consent_status=consent_status,
            consent_method=consent_method,
            consent_evidence=consent_evidence,
            consented_at=consented_at or (now if consent_status == "granted" else None),
            withdrawn_at=now if consent_status == "withdrawn" else None,
        )
        self.db.add(record)

        activity_type = "consent_recorded"
        if consent_status == "withdrawn":
            activity_type = "opt_out_received"
            if contact:
                await add_suppression(
                    self.db,
                    contact_type=contact.contact_type,
                    contact_value=contact.contact_value,
                    channel=channel if channel != "ads_platform" else "all",
                    reason="consent_withdrawn",
                )

        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business_id,
                user_id=user.id,
                activity_type=activity_type,
                description=f"Consent {consent_status} for {purpose}/{channel}",
                metadata_={
                    "consent_id": str(record.id),
                    "purpose": purpose,
                    "channel": channel,
                    "status": consent_status,
                },
            )
        )
        await self.db.flush()
        return record

    async def withdraw(
        self,
        consent_id: UUID,
        user: User,
        *,
        reason: str = "withdrawn_by_operator",
    ) -> ConsentRecord:
        record = await self.db.get(ConsentRecord, consent_id)
        if record is None:
            raise ConsentError("Consent record not found", 404)
        if record.consent_status == "withdrawn":
            return record

        record.consent_status = "withdrawn"
        record.withdrawn_at = datetime.now(timezone.utc)
        if record.contact_id:
            contact = await self.db.get(BusinessContact, record.contact_id)
            if contact:
                await add_suppression(
                    self.db,
                    contact_type=contact.contact_type,
                    contact_value=contact.contact_value,
                    channel=record.channel if record.channel != "ads_platform" else "all",
                    reason=reason,
                )

        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=record.business_id,
                user_id=user.id,
                activity_type="opt_out_received",
                description="Consent withdrawn",
                metadata_={"consent_id": str(record.id), "reason": reason},
            )
        )
        await self.db.flush()
        return record

    async def check_eligibility(
        self,
        *,
        business_id: UUID,
        purpose: str,
        channel: str,
        contact_id: Optional[UUID] = None,
    ) -> EligibilityResult:
        reasons: list[str] = []
        checks: dict[str, Any] = {
            "business_exists": False,
            "lead_status_ok": False,
            "purpose_channel_ok": False,
            "consent_granted": False,
            "not_suppressed": False,
            "provider_purpose_ok": True,
        }

        if purpose not in CONSENT_PURPOSES:
            return EligibilityResult(False, ["invalid_purpose"], checks)
        if channel not in CONSENT_CHANNELS:
            return EligibilityResult(False, ["invalid_channel"], checks)

        purpose_ok = purpose_matches_channel(purpose, channel)
        checks["purpose_channel_ok"] = purpose_ok
        if not purpose_ok:
            reasons.append("purpose_channel_mismatch")

        business = await self.db.get(Business, business_id)
        if business is None:
            reasons.append("business_not_found")
            return EligibilityResult(False, reasons, checks)
        checks["business_exists"] = True

        if business.lead_status == "do_not_contact":
            reasons.append("business_do_not_contact")
        else:
            checks["lead_status_ok"] = True

        contact: Optional[BusinessContact] = None
        if contact_id:
            contact = await self.db.get(BusinessContact, contact_id)
            if contact is None or contact.business_id != business_id:
                reasons.append("contact_not_found")
                return EligibilityResult(False, reasons, checks)

        # Active granted consent for purpose+channel
        consent_stmt = select(ConsentRecord).where(
            ConsentRecord.business_id == business_id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.channel == channel,
            ConsentRecord.consent_status == "granted",
            ConsentRecord.withdrawn_at.is_(None),
        )
        if contact_id:
            consent_stmt = consent_stmt.where(
                (ConsentRecord.contact_id == contact_id) | (ConsentRecord.contact_id.is_(None))
            )
        consent = (await self.db.execute(consent_stmt.limit(1))).scalar_one_or_none()
        checks["consent_granted"] = consent is not None
        if consent is None:
            reasons.append("missing_granted_consent")

        # Suppression
        suppressed = False
        if contact:
            suppressed = await is_suppressed(
                self.db,
                contact_type=contact.contact_type,
                contact_value=contact.contact_value,
                channel=channel,
            )
        checks["not_suppressed"] = not suppressed
        if suppressed:
            reasons.append("contact_suppressed")

        # Provider restrictions: advertising audience upload blocked for places-only provenance
        if purpose == "advertising_audience_upload":
            sources = (
                await self.db.execute(
                    select(LeadSource, DataProvider)
                    .join(DataProvider, DataProvider.id == LeadSource.provider_id)
                    .where(LeadSource.business_id == business_id)
                )
            ).all()
            for source, provider in sources:
                policy = provider.data_retention_policy or {}
                purposes = source.permitted_purposes or policy.get("permitted_purposes") or []
                if provider.provider_type == "official_api" and not policy.get("persist_crm_fields", True):
                    checks["provider_purpose_ok"] = False
                    reasons.append("provider_blocks_audience_upload")
                    break
                if purposes and "advertising_audience_upload" not in purposes and "advertising_research" not in purposes:
                    # soft warning only if all sources lack purpose — mark if none allow
                    pass
            # If business has ONLY non-persistable sources, block
            if sources and all(
                (p.data_retention_policy or {}).get("persist_crm_fields") is False
                for _, p in sources
            ):
                checks["provider_purpose_ok"] = False
                if "provider_blocks_audience_upload" not in reasons:
                    reasons.append("provider_blocks_audience_upload")

        eligible = (
            checks["business_exists"]
            and checks["lead_status_ok"]
            and checks["purpose_channel_ok"]
            and checks["consent_granted"]
            and checks["not_suppressed"]
            and checks["provider_purpose_ok"]
            and not reasons
        )
        # Recompute eligible strictly from checks (reasons may include soft items)
        eligible = all(
            [
                checks["business_exists"],
                checks["lead_status_ok"],
                checks["purpose_channel_ok"],
                checks["consent_granted"],
                checks["not_suppressed"],
                checks["provider_purpose_ok"],
            ]
        )
        if eligible:
            reasons = []
        return EligibilityResult(eligible=eligible, reasons=reasons, checks=checks)
