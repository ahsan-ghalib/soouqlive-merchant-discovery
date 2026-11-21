"""CRM lead workflow: status transitions, bulk qualify, pipeline helpers."""

from __future__ import annotations

import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.business import Business
from app.models.user import User
from app.schemas.business import LEAD_STATUSES
from app.services.scoring_service import ScoringService

# Allowed forward/side transitions for CRM pipeline discipline
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "new": {"researching", "qualified", "rejected", "do_not_contact"},
    "researching": {"qualified", "contacted", "rejected", "do_not_contact", "new"},
    "qualified": {"contacted", "interested", "follow_up", "rejected", "do_not_contact", "researching"},
    "contacted": {"interested", "follow_up", "rejected", "do_not_contact", "qualified"},
    "interested": {"follow_up", "registered", "rejected", "do_not_contact", "contacted"},
    "follow_up": {"interested", "registered", "contacted", "rejected", "do_not_contact"},
    "registered": {"follow_up"},  # rarely reopen
    "rejected": {"new", "researching"},  # reopen
    "do_not_contact": set(),  # terminal unless admin override
}

ACTIVITY_BY_STATUS = {
    "qualified": "lead_qualified",
    "contacted": "contact_attempted",
    "interested": "merchant_interested",
    "follow_up": "follow_up_scheduled",
    "registered": "merchant_registered",
    "rejected": "lead_rejected",
    "do_not_contact": "opt_out_received",
    "researching": "lead_discovered",
    "new": "lead_discovered",
}


class CRMError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CRMService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.scoring = ScoringService(db)

    async def transition_status(
        self,
        business_id: UUID,
        new_status: str,
        user: User,
        *,
        note: Optional[str] = None,
        force: bool = False,
    ) -> Business:
        if new_status not in LEAD_STATUSES:
            raise CRMError(f"Invalid lead_status. Allowed: {sorted(LEAD_STATUSES)}")

        business = await self.db.get(Business, business_id)
        if business is None:
            raise CRMError("Business not found", 404)

        current = business.lead_status
        if current == new_status:
            return business

        allowed = ALLOWED_TRANSITIONS.get(current, set())
        is_admin = user.role == "admin"
        if new_status not in allowed and not (force and is_admin):
            raise CRMError(
                f"Transition from '{current}' to '{new_status}' is not allowed",
                400,
            )

        business.lead_status = new_status
        self.db.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                user_id=user.id,
                activity_type=ACTIVITY_BY_STATUS.get(new_status, "lead_discovered"),
                description=note or f"Lead status changed: {current} → {new_status}",
                metadata_={"from": current, "to": new_status, "forced": force and is_admin},
            )
        )
        await self.db.flush()
        return business

    async def qualify_leads(
        self,
        *,
        user: User,
        business_ids: Optional[list[UUID]] = None,
        minimum_score: int = 60,
        rescore: bool = True,
        limit: int = 500,
    ) -> dict[str, Any]:
        if business_ids:
            ids = business_ids
        else:
            rows = (
                await self.db.execute(
                    select(Business.id)
                    .where(Business.lead_status.in_(["new", "researching"]))
                    .order_by(Business.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
            ids = list(rows)

        qualified = []
        scored = []
        skipped = []

        for business_id in ids:
            business = await self.db.get(Business, business_id)
            if business is None:
                skipped.append({"id": str(business_id), "reason": "not_found"})
                continue

            if rescore:
                breakdown = await self.scoring.score_business_async(
                    business_id,
                    user_id=user.id,
                    auto_qualify=False,
                )
                score = breakdown.total
                scored.append(str(business_id))
            else:
                score = business.qualification_score or 0

            if score >= minimum_score and business.lead_status in {
                "new",
                "researching",
                "qualified",
            }:
                if business.lead_status != "qualified":
                    await self.transition_status(
                        business_id,
                        "qualified",
                        user,
                        note=f"Auto-qualified at score {score}",
                    )
                qualified.append({"id": str(business_id), "score": score})
            else:
                skipped.append(
                    {"id": str(business_id), "reason": "below_threshold", "score": score}
                )

        return {
            "qualified": qualified,
            "scored": scored,
            "skipped": skipped,
            "minimum_score": minimum_score,
        }

    async def pipeline_summary(self) -> dict[str, Any]:
        rows = (
            await self.db.execute(
                select(Business.lead_status, func.count())
                .group_by(Business.lead_status)
            )
        ).all()
        by_status = {status: count for status, count in rows}
        avg_score = (
            await self.db.execute(select(func.avg(Business.qualification_score)))
        ).scalar_one()
        qualified_count = by_status.get("qualified", 0)
        registered = by_status.get("registered", 0)
        return {
            "by_status": by_status,
            "average_score": float(avg_score or 0),
            "qualified_count": qualified_count,
            "registered_count": registered,
            "conversion_rate": (
                round(registered / qualified_count, 4) if qualified_count else 0.0
            ),
        }

