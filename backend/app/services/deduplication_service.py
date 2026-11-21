"""Lead deduplication helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.business import Business
from app.models.contact import BusinessContact
from app.models.source import LeadSource
from app.utils.arabic import normalize_business_name
from app.utils.email import normalize_email
from app.utils.normalization import normalize_domain
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)


@dataclass
class DedupeMatch:
    business: Business
    strategy: str
    score: float


@dataclass
class MergeResult:
    survivor: Business
    merged_fields: list[str]
    contacts_added: int
    provenance_added: bool


class DeduplicationService:
    """Deduplicate in order: external id → domain → phone → name+city → fuzzy."""

    def __init__(self, session: AsyncSession | Session) -> None:
        self.session = session

    async def find_duplicate_async(
        self,
        *,
        external_id: Optional[str] = None,
        provider_id: Optional[UUID] = None,
        website_url: Optional[str] = None,
        phone: Optional[str] = None,
        business_name: Optional[str] = None,
        city: Optional[str] = None,
        location_id: Optional[UUID] = None,
        exclude_business_id: Optional[UUID] = None,
        fuzzy_threshold: float = 0.7,
    ) -> Optional[DedupeMatch]:
        assert isinstance(self.session, AsyncSession)

        if external_id and provider_id:
            stmt = (
                select(Business)
                .join(LeadSource, LeadSource.business_id == Business.id)
                .where(
                    LeadSource.provider_id == provider_id,
                    LeadSource.external_reference == external_id,
                )
            )
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
            if business:
                return DedupeMatch(business=business, strategy="external_id", score=1.0)

        domain = normalize_domain(website_url)
        if domain:
            result = await self.session.execute(
                select(Business).where(Business.website_url.is_not(None)).limit(1000)
            )
            for candidate in result.scalars().all():
                if exclude_business_id and candidate.id == exclude_business_id:
                    continue
                if normalize_domain(candidate.website_url) == domain:
                    return DedupeMatch(business=candidate, strategy="website_domain", score=0.98)

        normalized = normalize_phone(phone) if phone else None
        if normalized:
            stmt = (
                select(Business)
                .join(BusinessContact, BusinessContact.business_id == Business.id)
                .where(
                    BusinessContact.contact_type == "business_phone",
                    BusinessContact.normalized_value == normalized,
                )
            )
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
            if business:
                return DedupeMatch(business=business, strategy="phone", score=0.95)

        if business_name:
            normalized_name = normalize_business_name(business_name)
            stmt = select(Business).where(Business.normalized_name == normalized_name)
            if location_id:
                stmt = stmt.where(Business.location_id == location_id)
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
            if business:
                return DedupeMatch(business=business, strategy="name_city", score=0.9)

            fuzzy_stmt = (
                select(
                    Business,
                    func.similarity(Business.normalized_name, normalized_name).label("sim"),
                )
                .where(Business.normalized_name.is_not(None))
                .where(
                    func.similarity(Business.normalized_name, normalized_name) >= fuzzy_threshold
                )
            )
            if exclude_business_id:
                fuzzy_stmt = fuzzy_stmt.where(Business.id != exclude_business_id)
            if location_id:
                fuzzy_stmt = fuzzy_stmt.where(Business.location_id == location_id)
            row = (
                await self.session.execute(
                    fuzzy_stmt.order_by(
                        func.similarity(Business.normalized_name, normalized_name).desc()
                    ).limit(1)
                )
            ).first()
            if row:
                return DedupeMatch(business=row[0], strategy="fuzzy_name", score=float(row[1]))

        return None

    def find_duplicate_sync(
        self,
        *,
        external_id: Optional[str] = None,
        provider_id: Optional[UUID] = None,
        website_url: Optional[str] = None,
        phone: Optional[str] = None,
        business_name: Optional[str] = None,
        location_id: Optional[UUID] = None,
        exclude_business_id: Optional[UUID] = None,
        fuzzy_threshold: float = 0.7,
    ) -> Optional[DedupeMatch]:
        assert isinstance(self.session, Session)

        if external_id and provider_id:
            stmt = (
                select(Business)
                .join(LeadSource, LeadSource.business_id == Business.id)
                .where(
                    LeadSource.provider_id == provider_id,
                    LeadSource.external_reference == external_id,
                )
            )
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = self.session.execute(stmt.limit(1)).scalars().first()
            if business:
                return DedupeMatch(business=business, strategy="external_id", score=1.0)

        domain = normalize_domain(website_url)
        if domain:
            candidates = (
                self.session.execute(
                    select(Business).where(Business.website_url.is_not(None)).limit(1000)
                )
                .scalars()
                .all()
            )
            for candidate in candidates:
                if exclude_business_id and candidate.id == exclude_business_id:
                    continue
                if normalize_domain(candidate.website_url) == domain:
                    return DedupeMatch(business=candidate, strategy="website_domain", score=0.98)

        normalized = normalize_phone(phone) if phone else None
        if normalized:
            stmt = (
                select(Business)
                .join(BusinessContact, BusinessContact.business_id == Business.id)
                .where(
                    BusinessContact.contact_type == "business_phone",
                    BusinessContact.normalized_value == normalized,
                )
            )
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = self.session.execute(stmt.limit(1)).scalars().first()
            if business:
                return DedupeMatch(business=business, strategy="phone", score=0.95)

        if business_name:
            normalized_name = normalize_business_name(business_name)
            stmt = select(Business).where(Business.normalized_name == normalized_name)
            if location_id:
                stmt = stmt.where(Business.location_id == location_id)
            if exclude_business_id:
                stmt = stmt.where(Business.id != exclude_business_id)
            business = self.session.execute(stmt.limit(1)).scalars().first()
            if business:
                return DedupeMatch(business=business, strategy="name_city", score=0.9)

            fuzzy_stmt = (
                select(
                    Business,
                    func.similarity(Business.normalized_name, normalized_name).label("sim"),
                )
                .where(Business.normalized_name.is_not(None))
                .where(
                    func.similarity(Business.normalized_name, normalized_name) >= fuzzy_threshold
                )
            )
            if exclude_business_id:
                fuzzy_stmt = fuzzy_stmt.where(Business.id != exclude_business_id)
            row = self.session.execute(
                fuzzy_stmt.order_by(
                    func.similarity(Business.normalized_name, normalized_name).desc()
                ).limit(1)
            ).first()
            if row:
                return DedupeMatch(business=row[0], strategy="fuzzy_name", score=float(row[1]))

        return None

    async def merge_into_async(
        self,
        survivor: Business,
        *,
        incoming_fields: dict[str, Any],
        phone: Optional[str] = None,
        email: Optional[str] = None,
        provider_id: Optional[UUID] = None,
        external_reference: Optional[str] = None,
        source_url: Optional[str] = None,
        collection_method: str = "manual_import",
        user_id: Optional[UUID] = None,
        allow_contact_merge: bool = True,
    ) -> MergeResult:
        """Merge permitted fields/contacts into an existing business; preserve activities."""
        assert isinstance(self.session, AsyncSession)
        merged_fields: list[str] = []

        fillable = [
            "business_name_ar",
            "address",
            "district",
            "website_url",
            "description",
            "description_ar",
            "latitude",
            "longitude",
            "category_id",
            "location_id",
        ]
        for field_name in fillable:
            new_value = incoming_fields.get(field_name)
            if new_value in (None, ""):
                continue
            current = getattr(survivor, field_name, None)
            if current in (None, ""):
                setattr(survivor, field_name, new_value)
                merged_fields.append(field_name)

        if incoming_fields.get("business_name") and not survivor.business_name:
            survivor.business_name = incoming_fields["business_name"]
            survivor.normalized_name = normalize_business_name(survivor.business_name)
            merged_fields.append("business_name")

        contacts_added = 0
        if allow_contact_merge:
            contacts_added += await self._add_contact_if_missing(
                survivor.id, "business_phone", phone
            )
            contacts_added += await self._add_contact_if_missing(
                survivor.id, "business_email", email
            )

        provenance_added = False
        if provider_id:
            existing_prov = (
                await self.session.execute(
                    select(LeadSource).where(
                        LeadSource.business_id == survivor.id,
                        LeadSource.provider_id == provider_id,
                        LeadSource.external_reference == (external_reference or None),
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if existing_prov is None:
                self.session.add(
                    LeadSource(
                        id=uuid.uuid4(),
                        business_id=survivor.id,
                        provider_id=provider_id,
                        source_type="merge",
                        source_url=source_url,
                        external_reference=external_reference,
                        collection_method=collection_method,
                        permitted_purposes=["discovery", "manual_import"],
                        metadata_={"merged_fields": merged_fields},
                    )
                )
                provenance_added = True

        self.session.add(
            Activity(
                id=uuid.uuid4(),
                business_id=survivor.id,
                user_id=user_id,
                activity_type="lead_discovered",
                description="Duplicate merge applied",
                metadata_={
                    "merged_fields": merged_fields,
                    "contacts_added": contacts_added,
                    "provenance_added": provenance_added,
                },
            )
        )
        await self.session.flush()
        logger.info(
            "Merged into business %s fields=%s contacts=%s",
            survivor.id,
            merged_fields,
            contacts_added,
        )
        return MergeResult(
            survivor=survivor,
            merged_fields=merged_fields,
            contacts_added=contacts_added,
            provenance_added=provenance_added,
        )

    async def _add_contact_if_missing(
        self,
        business_id: UUID,
        contact_type: str,
        value: Optional[str],
    ) -> int:
        if not value:
            return 0
        if contact_type == "business_phone":
            normalized = normalize_phone(value)
        elif contact_type == "business_email":
            normalized = normalize_email(value)
        else:
            normalized = value.strip().lower()
        if not normalized:
            return 0

        exists = (
            await self.session.execute(
                select(BusinessContact).where(
                    BusinessContact.business_id == business_id,
                    BusinessContact.contact_type == contact_type,
                    BusinessContact.normalized_value == normalized,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if exists:
            return 0

        self.session.add(
            BusinessContact(
                id=uuid.uuid4(),
                business_id=business_id,
                contact_type=contact_type,
                contact_value=value,
                normalized_value=normalized,
                is_primary=False,
                is_verified=False,
            )
        )
        return 1
