"""Data provider listing endpoints."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.source import DataProvider
from app.providers.registry import get_provider, list_provider_keys
from app.utils.pagination import success_response

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.get("")
async def list_providers(db: DbSession, _user: CurrentUser):
    result = await db.execute(
        select(DataProvider).where(DataProvider.is_active.is_(True)).order_by(DataProvider.name)
    )
    rows = result.scalars().all()
    data = []
    for row in rows:
        adapter_key = row.provider_type
        if row.provider_type == "official_api" and "google" in row.name.lower():
            adapter_key = "places_api"
        try:
            adapter = get_provider(adapter_key)
            policy = adapter.get_data_policy()
            policy_data = {
                "persist_crm_fields": policy.persist_crm_fields,
                "place_id_allowed": policy.place_id_allowed,
                "daily_quota": policy.daily_quota,
                "permitted_purposes": policy.permitted_purposes,
                "notes": policy.notes,
            }
        except KeyError:
            policy_data = row.data_retention_policy

        data.append(
            {
                "id": str(row.id),
                "name": row.name,
                "provider_type": row.provider_type,
                "adapter_key": adapter_key,
                "is_active": row.is_active,
                "policy_reference": row.policy_reference,
                "policy": policy_data,
            }
        )

    return success_response(
        data={
            "providers": data,
            "adapter_keys": list_provider_keys(),
        },
        message="Providers retrieved",
    )
