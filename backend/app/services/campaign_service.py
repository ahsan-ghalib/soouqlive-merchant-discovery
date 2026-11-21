"""Campaign management and lead segmentation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.business import Business
from app.models.campaign import Campaign, CampaignLead
from app.models.contact import BusinessContact
from app.models.user import User
from app.services.crm_service import CRMService
from app.services.scoring_service import ScoringService

CAMPAIGN_TYPES = {
    "advertising_research",
    "merchant_acquisition",
    "market_research",
}
CAMPAIGN_STATUSES = {"draft", "active", "paused", "completed", "archived"}
CAMPAIGN_LEAD_STATUSES = {
    "pending",
    "qualified",
    "contacted",
    "interested",
    "follow_up",
    "converted",
    "rejected",
    "do_not_contact",
}


class CampaignError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CampaignService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_campaigns(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[Campaign], int]:
        stmt = select(Campaign)
        count_stmt = select(func.count()).select_from(Campaign)
        if status:
            stmt = stmt.where(Campaign.status == status)
            count_stmt = count_stmt.where(Campaign.status == status)
        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(Campaign.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get(self, campaign_id: UUID) -> Campaign:
        campaign = await self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise CampaignError("Campaign not found", 404)
        return campaign

    async def create(self, payload: dict[str, Any], user: User) -> Campaign:
        campaign_type = payload.get("campaign_type")
        if campaign_type not in CAMPAIGN_TYPES:
            raise CampaignError(f"Invalid campaign_type. Allowed: {sorted(CAMPAIGN_TYPES)}")
        status = payload.get("status") or "draft"
        if status not in CAMPAIGN_STATUSES:
            raise CampaignError(f"Invalid status. Allowed: {sorted(CAMPAIGN_STATUSES)}")

        campaign = Campaign(
            id=uuid.uuid4(),
            name=payload["name"],
            description=payload.get("description"),
            campaign_type=campaign_type,
            target_location_id=payload.get("target_location_id"),
            target_category_id=payload.get("target_category_id"),
            target_filters=payload.get("target_filters"),
            status=status,
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            created_by=user.id,
        )
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def update(self, campaign_id: UUID, payload: dict[str, Any]) -> Campaign:
        campaign = await self.get(campaign_id)
        for key, value in payload.items():
            if key == "campaign_type" and value is not None and value not in CAMPAIGN_TYPES:
                raise CampaignError(f"Invalid campaign_type. Allowed: {sorted(CAMPAIGN_TYPES)}")
            if key == "status" and value is not None and value not in CAMPAIGN_STATUSES:
                raise CampaignError(f"Invalid status. Allowed: {sorted(CAMPAIGN_STATUSES)}")
            if hasattr(campaign, key):
                setattr(campaign, key, value)
        await self.db.flush()
        return campaign

    async def delete(self, campaign_id: UUID) -> None:
        campaign = await self.get(campaign_id)
        if campaign.status == "active":
            raise CampaignError("Pause or archive campaign before delete", 400)
        await self.db.delete(campaign)
        await self.db.flush()

    async def add_leads(
        self,
        campaign_id: UUID,
        business_ids: list[UUID],
        user: User,
        *,
        assigned_to: Optional[UUID] = None,
    ) -> dict[str, Any]:
        campaign = await self.get(campaign_id)
        added = []
        skipped = []
        for business_id in business_ids:
            business = await self.db.get(Business, business_id)
            if business is None:
                skipped.append({"business_id": str(business_id), "reason": "not_found"})
                continue
            if business.lead_status == "do_not_contact":
                skipped.append({"business_id": str(business_id), "reason": "do_not_contact"})
                continue

            existing = (
                await self.db.execute(
                    select(CampaignLead).where(
                        CampaignLead.campaign_id == campaign_id,
                        CampaignLead.business_id == business_id,
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if existing:
                skipped.append({"business_id": str(business_id), "reason": "already_in_campaign"})
                continue

            lead = CampaignLead(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                business_id=business_id,
                status="pending",
                assigned_to=assigned_to,
                last_activity_at=datetime.now(timezone.utc),
            )
            self.db.add(lead)
            self.db.add(
                Activity(
                    id=uuid.uuid4(),
                    business_id=business_id,
                    campaign_id=campaign.id,
                    user_id=user.id,
                    activity_type="lead_assigned",
                    description=f"Added to campaign {campaign.name}",
                    metadata_={"campaign_id": str(campaign.id)},
                )
            )
            added.append(str(business_id))
        await self.db.flush()
        return {"added": added, "skipped": skipped, "campaign_id": str(campaign.id)}

    async def remove_lead(self, campaign_id: UUID, business_id: UUID) -> None:
        await self.get(campaign_id)
        lead = (
            await self.db.execute(
                select(CampaignLead).where(
                    CampaignLead.campaign_id == campaign_id,
                    CampaignLead.business_id == business_id,
                ).limit(1)
            )
        ).scalar_one_or_none()
        if lead is None:
            raise CampaignError("Campaign lead not found", 404)
        await self.db.delete(lead)
        await self.db.flush()

    async def list_leads(
        self,
        campaign_id: UUID,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[CampaignLead], int]:
        await self.get(campaign_id)
        total = (
            await self.db.execute(
                select(func.count()).select_from(CampaignLead).where(
                    CampaignLead.campaign_id == campaign_id
                )
            )
        ).scalar_one()
        rows = (
            await self.db.execute(
                select(CampaignLead)
                .where(CampaignLead.campaign_id == campaign_id)
                .order_by(CampaignLead.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def qualify_campaign(
        self,
        campaign_id: UUID,
        user: User,
        *,
        minimum_score: int = 60,
        rescore: bool = True,
    ) -> dict[str, Any]:
        campaign = await self.get(campaign_id)
        leads = (
            await self.db.execute(
                select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
            )
        ).scalars().all()

        scoring = ScoringService(self.db)
        crm = CRMService(self.db)
        qualified = []
        skipped = []

        for lead in leads:
            business = await self.db.get(Business, lead.business_id)
            if business is None:
                skipped.append({"business_id": str(lead.business_id), "reason": "missing"})
                continue
            if rescore:
                breakdown = await scoring.score_business_async(
                    business.id,
                    user_id=user.id,
                    auto_qualify=False,
                )
                score = breakdown.total
            else:
                score = business.qualification_score or 0

            if score >= minimum_score:
                lead.status = "qualified"
                lead.last_activity_at = datetime.now(timezone.utc)
                if business.lead_status in {"new", "researching"}:
                    await crm.transition_status(
                        business.id,
                        "qualified",
                        user,
                        note=f"Qualified via campaign {campaign.name}",
                    )
                qualified.append({"business_id": str(business.id), "score": score})
            else:
                skipped.append(
                    {"business_id": str(business.id), "reason": "below_threshold", "score": score}
                )
        await self.db.flush()
        return {
            "campaign_id": str(campaign.id),
            "qualified": qualified,
            "skipped": skipped,
            "minimum_score": minimum_score,
        }

    async def analytics(self, campaign_id: UUID) -> dict[str, Any]:
        campaign = await self.get(campaign_id)
        leads = (
            await self.db.execute(
                select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
            )
        ).scalars().all()
        by_status: dict[str, int] = {}
        business_ids = [lead.business_id for lead in leads]
        for lead in leads:
            by_status[lead.status] = by_status.get(lead.status, 0) + 1

        qualified = by_status.get("qualified", 0)
        converted = by_status.get("converted", 0)
        eligible_contacts = 0
        if business_ids and campaign.campaign_type == "merchant_acquisition":
            # Count contacts that would need eligibility — report contact availability,
            # not outreach permission. True eligibility requires consent check.
            eligible_contacts = (
                await self.db.execute(
                    select(func.count()).select_from(BusinessContact).where(
                        BusinessContact.business_id.in_(business_ids),
                        BusinessContact.contact_type.in_(["business_email", "business_phone"]),
                    )
                )
            ).scalar_one()
        elif business_ids and campaign.campaign_type == "advertising_research":
            # Research campaigns: contact outreach eligibility is separate / usually N/A
            eligible_contacts = 0

        registered = (
            await self.db.execute(
                select(func.count()).select_from(Business).where(
                    Business.id.in_(business_ids) if business_ids else False,
                    Business.lead_status == "registered",
                )
            )
        ).scalar_one() if business_ids else 0

        return {
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "campaign_type": campaign.campaign_type,
            "status": campaign.status,
            "total_businesses": len(leads),
            "by_status": by_status,
            "qualified_leads": qualified,
            "public_contacts_available": eligible_contacts,
            "eligible_for_outreach_note": (
                "Use /consent/check-eligibility before outreach. "
                "Advertising research stays separate from direct-outreach eligibility."
            ),
            "registered_merchants": registered,
            "conversion_rate": round(converted / len(leads), 4) if leads else 0.0,
        }

    async def add_leads_from_filters(
        self,
        campaign_id: UUID,
        user: User,
        *,
        location_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        minimum_score: int = 0,
        lead_status: Optional[str] = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        campaign = await self.get(campaign_id)
        conditions = []
        loc = location_id or campaign.target_location_id
        cat = category_id or campaign.target_category_id
        if loc:
            conditions.append(Business.location_id == loc)
        if cat:
            conditions.append(Business.category_id == cat)
        if minimum_score:
            conditions.append(Business.qualification_score >= minimum_score)
        if lead_status:
            conditions.append(Business.lead_status == lead_status)
        conditions.append(Business.lead_status != "do_not_contact")

        stmt = select(Business.id)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Business.qualification_score.desc()).limit(limit)
        ids = list((await self.db.execute(stmt)).scalars().all())
        return await self.add_leads(campaign_id, ids, user)
