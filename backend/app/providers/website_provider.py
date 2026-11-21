"""Public website enrichment provider (used by enrichment workers later)."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from app.providers.base import (
    BusinessProvider,
    ProviderBusinessRecord,
    ProviderDataPolicy,
    ProviderSearchQuery,
)


class WebsiteProvider(BusinessProvider):
    """Not a discovery search source — enrichment against a known business URL."""

    key = "public_website"
    display_name = "Public Website Enrichment"

    def get_data_policy(self) -> ProviderDataPolicy:
        return ProviderDataPolicy(
            provider_key=self.key,
            provider_type="public_website",
            persist_crm_fields=True,
            permitted_fields={
                "business_name",
                "business_name_ar",
                "website_url",
                "phone",
                "email",
                "description",
                "source_url",
            },
            permitted_purposes=["enrichment"],
            retention_days=365,
            daily_quota=5000,
            rate_limit_per_minute=30,
            notes="Only permitted public pages; robots.txt and SSRF controls required.",
        )

    def can_persist(self, field_name: str) -> bool:
        return field_name in self.get_data_policy().permitted_fields

    async def search(self, query: ProviderSearchQuery) -> list[ProviderBusinessRecord]:
        raise NotImplementedError(
            "Website provider does not support discovery search. "
            "Use licensed_directory or manual_import for discovery."
        )

    async def get_details(self, provider_id: str) -> Optional[ProviderBusinessRecord]:
        # provider_id is expected to be a public https URL
        parsed = urlparse(provider_id)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        return ProviderBusinessRecord(
            external_id=parsed.netloc,
            website_url=provider_id,
            source_url=provider_id,
        )
