"""Business / lead management service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.business import Business
from app.models.category import BusinessCategory
from app.models.consent import ConsentRecord
from app.models.contact import BusinessContact
from app.models.location import Location
from app.models.source import DataProvider, LeadSource
from app.models.user import User
from app.providers.base import ProviderSearchQuery
from app.providers.manual_import import ManualImportProvider
from app.schemas.business import BusinessCreate, BusinessListFilters, BusinessUpdate
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.deduplication_service import DeduplicationService
from app.utils.arabic import normalize_business_name
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone


class LeadError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class LeadService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dedupe = DeduplicationService(db)

    async def list_businesses(
        self,
        filters: BusinessListFilters,
    ) -> tuple[list[dict[str, Any]], int]:
        phone_exists = exists(
            select(BusinessContact.id).where(
                BusinessContact.business_id == Business.id,
                BusinessContact.contact_type == "business_phone",
            )
        )
        email_exists = exists(
            select(BusinessContact.id).where(
                BusinessContact.business_id == Business.id,
                BusinessContact.contact_type == "business_email",
            )
        )

        stmt = select(
            Business,
            phone_exists.label("has_phone"),
            email_exists.label("has_email"),
        )
        count_stmt = select(func.count()).select_from(Business)

        conditions = []

        if filters.location_id:
            conditions.append(Business.location_id == filters.location_id)
        elif filters.city:
            loc_ids = (
                await self.db.execute(
                    select(Location.id).where(func.lower(Location.name) == filters.city.lower())
                )
            ).scalars().all()
            if loc_ids:
                conditions.append(Business.location_id.in_(loc_ids))
            else:
                return [], 0

        if filters.category_id:
            conditions.append(Business.category_id == filters.category_id)
        elif filters.category:
            cat = (
                await self.db.execute(
                    select(BusinessCategory.id).where(
                        or_(
                            BusinessCategory.slug == filters.category.lower().replace(" ", "-"),
                            func.lower(BusinessCategory.name) == filters.category.lower(),
                        )
                    )
                )
            ).scalar_one_or_none()
            if cat:
                conditions.append(Business.category_id == cat)
            else:
                return [], 0

        if filters.lead_status:
            conditions.append(Business.lead_status == filters.lead_status)
        if filters.business_status:
            conditions.append(Business.business_status == filters.business_status)
        if filters.minimum_score is not None:
            conditions.append(Business.qualification_score >= filters.minimum_score)
        if filters.maximum_score is not None:
            conditions.append(Business.qualification_score <= filters.maximum_score)
        if filters.has_website is True:
            conditions.append(Business.website_url.is_not(None))
            conditions.append(Business.website_url != "")
        elif filters.has_website is False:
            conditions.append(or_(Business.website_url.is_(None), Business.website_url == ""))
        if filters.has_phone is True:
            conditions.append(phone_exists)
        elif filters.has_phone is False:
            conditions.append(~phone_exists)
        if filters.has_email is True:
            conditions.append(email_exists)
        elif filters.has_email is False:
            conditions.append(~email_exists)
        if filters.assigned_to:
            conditions.append(Business.assigned_to == filters.assigned_to)
        if filters.created_from:
            conditions.append(Business.created_at >= filters.created_from)
        if filters.created_to:
            conditions.append(Business.created_at <= filters.created_to)
        if filters.search:
            term = f"%{filters.search.strip()}%"
            conditions.append(
                or_(
                    Business.business_name.ilike(term),
                    Business.business_name_ar.ilike(term),
                    Business.normalized_name.ilike(term),
                )
            )
        if filters.source:
            source_exists = exists(
                select(LeadSource.id)
                .join(DataProvider, DataProvider.id == LeadSource.provider_id)
                .where(
                    LeadSource.business_id == Business.id,
                    or_(
                        DataProvider.provider_type == filters.source,
                        func.lower(DataProvider.name) == filters.source.lower(),
                        LeadSource.source_type == filters.source,
                    ),
                )
            )
            conditions.append(source_exists)

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(Business.created_at.desc())
                .offset((filters.page - 1) * filters.limit)
                .limit(filters.limit)
            )
        ).all()

        data: list[dict[str, Any]] = []
        for business, has_phone, has_email in rows:
            item = {
                "id": business.id,
                "business_name": business.business_name,
                "business_name_ar": business.business_name_ar,
                "normalized_name": business.normalized_name,
                "category_id": business.category_id,
                "location_id": business.location_id,
                "address": business.address,
                "district": business.district,
                "website_url": business.website_url,
                "description": business.description,
                "description_ar": business.description_ar,
                "latitude": business.latitude,
                "longitude": business.longitude,
                "business_status": business.business_status,
                "lead_status": business.lead_status,
                "qualification_score": business.qualification_score,
                "qualification_reason": business.qualification_reason,
                "assigned_to": business.assigned_to,
                "first_discovered_at": business.first_discovered_at,
                "last_enriched_at": business.last_enriched_at,
                "created_at": business.created_at,
                "updated_at": business.updated_at,
                "has_phone": bool(has_phone),
                "has_email": bool(has_email),
            }
            data.append(item)
        return data, total

    async def get_business(self, business_id: UUID) -> Business:
        business = await self.db.get(Business, business_id)
        if business is None:
            raise LeadError("Business not found", 404)
        return business

    async def create_business(
        self,
        payload: BusinessCreate,
        user: User,
    ) -> tuple[Business, Optional[dict[str, Any]]]:
        if not payload.skip_dedupe:
            match = await self.dedupe.find_duplicate_async(
                external_id=payload.external_reference,
                provider_id=payload.provider_id,
                website_url=payload.website_url,
                phone=payload.phone,
                business_name=payload.business_name,
                location_id=payload.location_id,
            )
            if match:
                merge = await self.dedupe.merge_into_async(
                    match.business,
                    incoming_fields=payload.model_dump(exclude_unset=True),
                    phone=payload.phone,
                    email=payload.email,
                    provider_id=payload.provider_id,
                    external_reference=payload.external_reference,
                    collection_method="api_create",
                    user_id=user.id,
                )
                return merge.survivor, {
                    "duplicate": True,
                    "strategy": match.strategy,
                    "score": match.score,
                    "merged_fields": merge.merged_fields,
                    "contacts_added": merge.contacts_added,
                }

        business = Business(
            id=uuid.uuid4(),
            business_name=payload.business_name,
            business_name_ar=payload.business_name_ar,
            normalized_name=normalize_business_name(payload.business_name),
            category_id=payload.category_id,
            location_id=payload.location_id,
            address=payload.address,
            district=payload.district,
            website_url=payload.website_url,
            description=payload.description,
            description_ar=payload.description_ar,
            latitude=payload.latitude,
            longitude=payload.longitude,
            business_status=payload.business_status,
            lead_status=payload.lead_status,
            first_discovered_at=datetime.now(timezone.utc),
        )
        self.db.add(business)
        await self.db.flush()

        if payload.provider_id:
            self.db.add(
                LeadSource(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    provider_id=payload.provider_id,
                    source_type="manual",
                    external_reference=payload.external_reference,
                    collection_method="api_create",
                    permitted_purposes=["manual_import", "discovery"],
                )
            )

        await self._add_optional_contacts(business.id, payload.phone, payload.email)
        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                user_id=user.id,
                activity_type="lead_discovered",
                description="Business created manually",
            )
        )
        await self.db.flush()
        return business, None

    async def update_business(
        self,
        business_id: UUID,
        payload: BusinessUpdate,
        user: User,
    ) -> Business:
        business = await self.get_business(business_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(business, key, value)
        if "business_name" in data and data["business_name"]:
            business.normalized_name = normalize_business_name(data["business_name"])

        activity_type = "lead_discovered"
        if data.get("lead_status") == "qualified":
            activity_type = "lead_qualified"
        elif data.get("lead_status") == "rejected":
            activity_type = "lead_rejected"
        elif data.get("lead_status") == "registered":
            activity_type = "merchant_registered"
        elif data.get("lead_status") == "interested":
            activity_type = "merchant_interested"

        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                user_id=user.id,
                activity_type=activity_type,
                description="Business updated",
                metadata_={"updated_fields": list(data.keys())},
            )
        )
        await self.db.flush()
        return business

    async def delete_business(self, business_id: UUID, user: User, *, hard: bool = False) -> dict:
        business = await self.get_business(business_id)
        if not hard:
            business.lead_status = "rejected"
            self.db.add(
                Activity(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    user_id=user.id,
                    activity_type="lead_rejected",
                    description="Business soft-deleted (lead_status=rejected)",
                )
            )
            await self.db.flush()
            return {"id": str(business.id), "deleted": False, "soft_deleted": True}

        consent_count = (
            await self.db.execute(
                select(func.count()).select_from(ConsentRecord).where(
                    ConsentRecord.business_id == business_id
                )
            )
        ).scalar_one()
        activity_count = (
            await self.db.execute(
                select(func.count()).select_from(Activity).where(Activity.business_id == business_id)
            )
        ).scalar_one()
        if consent_count or activity_count:
            raise LeadError(
                "Hard delete blocked: consent/activity audit records exist. Use soft delete.",
                409,
            )
        await self.db.delete(business)
        await self.db.flush()
        return {"id": str(business_id), "deleted": True, "soft_deleted": False}

    async def assign_business(
        self,
        business_id: UUID,
        assigned_to: Optional[UUID],
        user: User,
    ) -> Business:
        business = await self.get_business(business_id)
        if assigned_to is not None:
            assignee = await self.db.get(User, assigned_to)
            if assignee is None or not assignee.is_active:
                raise LeadError("Assignee not found or inactive", 404)
        business.assigned_to = assigned_to
        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                user_id=user.id,
                activity_type="lead_assigned",
                description="Business assignment updated",
                metadata_={"assigned_to": str(assigned_to) if assigned_to else None},
            )
        )
        await self.db.flush()
        return business

    async def list_activities(
        self,
        business_id: UUID,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Activity], int]:
        await self.get_business(business_id)
        total = (
            await self.db.execute(
                select(func.count()).select_from(Activity).where(Activity.business_id == business_id)
            )
        ).scalar_one()
        rows = (
            await self.db.execute(
                select(Activity)
                .where(Activity.business_id == business_id)
                .order_by(Activity.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def list_contacts(self, business_id: UUID) -> list[BusinessContact]:
        await self.get_business(business_id)
        rows = (
            await self.db.execute(
                select(BusinessContact)
                .where(BusinessContact.business_id == business_id)
                .order_by(BusinessContact.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def create_contact(self, payload: ContactCreate, user: User) -> BusinessContact:
        await self.get_business(payload.business_id)
        normalized = self._normalize_contact(payload.contact_type, payload.contact_value)
        if not normalized:
            raise LeadError("Invalid contact value for type", 400)

        existing = (
            await self.db.execute(
                select(BusinessContact).where(
                    BusinessContact.business_id == payload.business_id,
                    BusinessContact.contact_type == payload.contact_type,
                    BusinessContact.normalized_value == normalized,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            raise LeadError("Contact already exists for this business", 409)

        contact = BusinessContact(
            id=uuid.uuid4(),
            business_id=payload.business_id,
            contact_type=payload.contact_type,
            contact_value=payload.contact_value,
            normalized_value=normalized,
            label=payload.label,
            is_primary=payload.is_primary,
            is_verified=False,
            source_id=payload.source_id,
        )
        self.db.add(contact)
        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=payload.business_id,
                user_id=user.id,
                activity_type="lead_discovered",
                description=f"Contact added ({payload.contact_type})",
                metadata_={"contact_type": payload.contact_type},
            )
        )
        await self.db.flush()
        return contact

    async def get_contact(self, contact_id: UUID) -> BusinessContact:
        contact = await self.db.get(BusinessContact, contact_id)
        if contact is None:
            raise LeadError("Contact not found", 404)
        return contact

    async def update_contact(
        self,
        contact_id: UUID,
        payload: ContactUpdate,
    ) -> BusinessContact:
        contact = await self.get_contact(contact_id)
        data = payload.model_dump(exclude_unset=True)
        if "contact_value" in data or "contact_type" in data:
            contact_type = data.get("contact_type", contact.contact_type)
            contact_value = data.get("contact_value", contact.contact_value)
            normalized = self._normalize_contact(contact_type, contact_value)
            if not normalized:
                raise LeadError("Invalid contact value for type", 400)
            contact.normalized_value = normalized
            contact.contact_type = contact_type
            contact.contact_value = contact_value
        if "label" in data:
            contact.label = data["label"]
        if "is_primary" in data and data["is_primary"] is not None:
            contact.is_primary = data["is_primary"]
        await self.db.flush()
        return contact

    async def verify_contact(
        self,
        contact_id: UUID,
        *,
        verification_method: str,
        is_verified: bool,
        user: User,
    ) -> BusinessContact:
        contact = await self.get_contact(contact_id)
        contact.is_verified = is_verified
        contact.verification_method = verification_method
        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=contact.business_id,
                user_id=user.id,
                activity_type="lead_qualified",
                description="Contact verification updated",
                metadata_={
                    "contact_id": str(contact.id),
                    "is_verified": is_verified,
                    "verification_method": verification_method,
                },
            )
        )
        await self.db.flush()
        return contact

    async def bulk_import(
        self,
        *,
        records: list[dict[str, Any]],
        provider_key: str,
        user: User,
        location_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        provider_row = (
            await self.db.execute(
                select(DataProvider).where(
                    or_(
                        DataProvider.provider_type == provider_key,
                        func.lower(DataProvider.name) == provider_key.lower(),
                    ),
                    DataProvider.is_active.is_(True),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if provider_row is None:
            # Ensure manual import provider exists
            provider_row = (
                await self.db.execute(
                    select(DataProvider).where(DataProvider.provider_type == "manual_import")
                )
            ).scalar_one_or_none()
        if provider_row is None:
            raise LeadError("manual_import provider not configured", 400)

        adapter = ManualImportProvider(records=records)
        created = 0
        duplicates = 0
        failed = 0
        results: list[dict[str, Any]] = []

        mapped = await adapter.search(
            ProviderSearchQuery(keyword="import", limit=len(records))
        )
        for record in mapped:
            try:
                payload = BusinessCreate(
                    business_name=record.business_name or "Unknown",
                    business_name_ar=record.business_name_ar,
                    category_id=category_id,
                    location_id=location_id,
                    address=record.address,
                    district=record.district,
                    website_url=record.website_url,
                    description=record.description,
                    latitude=record.latitude,
                    longitude=record.longitude,
                    phone=record.phone,
                    email=record.email,
                    external_reference=record.external_id,
                    provider_id=provider_row.id,
                )
                business, dup = await self.create_business(payload, user)
                if dup:
                    duplicates += 1
                    results.append({"id": str(business.id), "status": "duplicate", **dup})
                else:
                    created += 1
                    results.append({"id": str(business.id), "status": "created"})
            except Exception as exc:
                failed += 1
                results.append({"status": "failed", "error": str(exc)})

        return {
            "created": created,
            "duplicates": duplicates,
            "failed": failed,
            "total": len(records),
            "results": results[:100],
        }

    async def bulk_update(
        self,
        items: list[tuple[UUID, BusinessUpdate]],
        user: User,
    ) -> dict[str, Any]:
        updated = 0
        failed = 0
        details = []
        for business_id, patch in items:
            try:
                business = await self.update_business(business_id, patch, user)
                updated += 1
                details.append({"id": str(business.id), "status": "updated"})
            except LeadError as exc:
                failed += 1
                details.append({"id": str(business_id), "status": "failed", "error": exc.message})
        return {"updated": updated, "failed": failed, "results": details}

    async def _add_optional_contacts(
        self,
        business_id: UUID,
        phone: Optional[str],
        email: Optional[str],
    ) -> None:
        if phone:
            normalized = normalize_phone(phone)
            if normalized:
                self.db.add(
                    BusinessContact(
                        id=uuid.uuid4(),
                        business_id=business_id,
                        contact_type="business_phone",
                        contact_value=phone,
                        normalized_value=normalized,
                        is_primary=True,
                        is_verified=False,
                    )
                )
        if email:
            normalized = normalize_email(email)
            if normalized:
                self.db.add(
                    BusinessContact(
                        id=uuid.uuid4(),
                        business_id=business_id,
                        contact_type="business_email",
                        contact_value=email,
                        normalized_value=normalized,
                        is_primary=True,
                        is_verified=False,
                    )
                )

    @staticmethod
    def _normalize_contact(contact_type: str, value: str) -> Optional[str]:
        if contact_type == "business_phone":
            return normalize_phone(value)
        if contact_type == "business_email":
            return normalize_email(value)
        return value.strip() or None
