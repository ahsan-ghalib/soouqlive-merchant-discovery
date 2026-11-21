"""Manual CSV/JSON import provider adapter."""

from __future__ import annotations

from typing import Any, Optional

from app.providers.base import (
    BusinessProvider,
    ProviderBusinessRecord,
    ProviderDataPolicy,
    ProviderSearchQuery,
)


class ManualImportProvider(BusinessProvider):
    key = "manual_import"
    display_name = "Manual CSV Import"

    def __init__(self, records: Optional[list[dict[str, Any]]] = None) -> None:
        self._records = records or []

    def get_data_policy(self) -> ProviderDataPolicy:
        return ProviderDataPolicy(
            provider_key=self.key,
            provider_type="manual_import",
            persist_crm_fields=True,
            permitted_fields={
                "external_id",
                "business_name",
                "business_name_ar",
                "address",
                "district",
                "city",
                "website_url",
                "phone",
                "email",
                "latitude",
                "longitude",
                "category",
                "description",
                "source_url",
            },
            permitted_purposes=["discovery", "manual_import"],
            retention_days=730,
            daily_quota=50000,
            rate_limit_per_minute=1000,
            notes="Operator-supplied import; provenance still recorded.",
        )

    def can_persist(self, field_name: str) -> bool:
        return field_name in self.get_data_policy().permitted_fields

    def load_records(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    async def search(self, query: ProviderSearchQuery) -> list[ProviderBusinessRecord]:
        self.validate_quota(query.limit)
        results = [self._map_item(item) for item in self._records]
        return results[query.offset : query.offset + query.limit]

    async def get_details(self, provider_id: str) -> Optional[ProviderBusinessRecord]:
        for item in self._records:
            if str(item.get("external_id") or item.get("id")) == provider_id:
                return self._map_item(item)
        return None

    def _map_item(self, item: dict[str, Any]) -> ProviderBusinessRecord:
        return ProviderBusinessRecord(
            external_id=str(item.get("external_id") or item.get("id") or "") or None,
            business_name=item.get("business_name") or item.get("name"),
            business_name_ar=item.get("business_name_ar"),
            address=item.get("address"),
            district=item.get("district"),
            city=item.get("city"),
            website_url=item.get("website_url") or item.get("website"),
            phone=item.get("phone"),
            email=item.get("email"),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            category=item.get("category"),
            description=item.get("description"),
            source_url=item.get("source_url"),
            raw=item,
        )
