"""Licensed business directory adapter (authorized CRM-persistable source)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.providers.base import (
    BusinessProvider,
    ProviderBusinessRecord,
    ProviderDataPolicy,
    ProviderSearchQuery,
)


class LicensedDirectoryProvider(BusinessProvider):
    key = "licensed_directory"
    display_name = "Licensed Business Directory"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        sample_records: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.business_provider_api_key
        resolved = base_url if base_url is not None else settings.business_provider_base_url
        self.base_url = (resolved or "").rstrip("/")
        self._sample_records = sample_records

    def get_data_policy(self) -> ProviderDataPolicy:
        return ProviderDataPolicy(
            provider_key=self.key,
            provider_type="licensed_directory",
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
            permitted_purposes=["discovery", "enrichment", "advertising_research"],
            retention_days=730,
            daily_quota=10000,
            rate_limit_per_minute=120,
            notes="Independently licensed dataset eligible for CRM persistence.",
        )

    def can_persist(self, field_name: str) -> bool:
        return field_name in self.get_data_policy().permitted_fields

    async def search(self, query: ProviderSearchQuery) -> list[ProviderBusinessRecord]:
        self.validate_quota(query.limit)
        if self._sample_records is not None:
            return self._from_samples(query)

        if not self.api_key or not self.base_url:
            # Safe empty result when credentials are not configured
            return []

        params = {
            "q": query.keyword,
            "q_ar": query.keyword_ar or "",
            "country": query.country_code,
            "city": query.city or "",
            "category": query.category or "",
            "limit": query.limit,
            "offset": query.offset,
            "language": query.language,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/businesses/search",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        items = payload.get("results") or payload.get("data") or []
        return [self._map_item(item) for item in items[: query.limit]]

    async def get_details(self, provider_id: str) -> Optional[ProviderBusinessRecord]:
        if self._sample_records is not None:
            for item in self._sample_records:
                if str(item.get("id") or item.get("external_id")) == provider_id:
                    return self._map_item(item)
            return None

        if not self.api_key or not self.base_url:
            return None

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/v1/businesses/{provider_id}",
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._map_item(response.json())

    def _from_samples(self, query: ProviderSearchQuery) -> list[ProviderBusinessRecord]:
        assert self._sample_records is not None
        keyword = (query.keyword or "").lower()
        keyword_ar = query.keyword_ar or ""
        matched: list[ProviderBusinessRecord] = []
        for item in self._sample_records:
            name = str(item.get("business_name") or "")
            name_ar = str(item.get("business_name_ar") or "")
            city = str(item.get("city") or "")
            category = str(item.get("category") or "")
            if query.city and city and query.city.lower() not in city.lower():
                continue
            if query.category and category and query.category.lower() not in category.lower():
                continue
            hay = f"{name} {name_ar} {category}".lower()
            if keyword and keyword not in hay and keyword_ar not in name_ar:
                # allow broad sample discovery when keyword loosely matches category
                if keyword not in category.lower():
                    continue
            matched.append(self._map_item(item))
            if len(matched) >= query.limit:
                break
        return matched

    def _map_item(self, item: dict[str, Any]) -> ProviderBusinessRecord:
        return ProviderBusinessRecord(
            external_id=str(item.get("id") or item.get("external_id") or ""),
            business_name=item.get("business_name") or item.get("name"),
            business_name_ar=item.get("business_name_ar") or item.get("name_ar"),
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
