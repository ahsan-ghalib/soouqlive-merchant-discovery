"""Provider retention helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import LeadSource


async def expired_lead_sources(
    db: AsyncSession,
    *,
    as_of: Optional[datetime] = None,
) -> list[LeadSource]:
    now = as_of or datetime.now(timezone.utc)
    result = await db.execute(
        select(LeadSource).where(
            LeadSource.retention_expires_at.is_not(None),
            LeadSource.retention_expires_at <= now,
        )
    )
    return list(result.scalars().all())


def retention_policy_summary(policy: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not policy:
        return {"persist_crm_fields": False, "retention_days": None}
    return {
        "persist_crm_fields": bool(policy.get("persist_crm_fields")),
        "retention_days": policy.get("retention_days"),
        "place_id_allowed": policy.get("place_id_allowed", False),
        "notes": policy.get("notes"),
    }
