"""Provider retention and persistence policy enforcement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.providers.base import BusinessProvider, ProviderBusinessRecord, ProviderDataPolicy


class SourcePolicyError(Exception):
    pass


def enforce_can_search(provider: BusinessProvider, purpose: str = "discovery") -> None:
    policy = provider.get_data_policy()
    if policy.permitted_purposes and purpose not in policy.permitted_purposes:
        raise SourcePolicyError(
            f"Provider '{provider.key}' does not permit purpose '{purpose}'"
        )


def build_persistable_payload(
    provider: BusinessProvider,
    record: ProviderBusinessRecord,
) -> dict[str, Any]:
    policy = provider.get_data_policy()
    payload = provider.filter_persistable(record)

    if not policy.persist_crm_fields:
        # Google Places-style: do not materialize restricted CRM content
        if not payload.get("external_id"):
            raise SourcePolicyError(
                f"Provider '{provider.key}' does not allow CRM persistence for this record"
            )
    elif not payload.get("business_name") and not payload.get("business_name_ar"):
        raise SourcePolicyError("Persistable record is missing a business name")

    return payload


def retention_expires_at(policy: ProviderDataPolicy) -> Optional[datetime]:
    if policy.retention_days is None:
        return None
    return datetime.now(timezone.utc) + timedelta(days=policy.retention_days)


def preview_safe_record(
    provider: BusinessProvider,
    record: ProviderBusinessRecord,
) -> dict[str, Any]:
    """Return a dashboard preview that never implies restricted data is stored."""
    policy = provider.get_data_policy()
    if policy.preview_only_restricted or not policy.persist_crm_fields:
        return {
            "external_id": record.external_id,
            "preview_label": record.business_name or record.external_id,
            "city": record.city,
            "category": record.category,
            "persistable": False,
            "policy_note": policy.notes
            or "Restricted provider content is preview-only and will not be stored as CRM data.",
        }

    persistable = provider.filter_persistable(record)
    return {
        **persistable,
        "persistable": True,
        "policy_note": policy.notes or None,
    }
