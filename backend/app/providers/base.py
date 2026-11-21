"""Abstract business-data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProviderSearchQuery:
    keyword: str
    keyword_ar: Optional[str] = None
    country_code: str = "SA"
    city: Optional[str] = None
    category: Optional[str] = None
    language: str = "both"
    limit: int = 100
    offset: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderBusinessRecord:
    """Normalized provider output before persistence policy is applied."""

    external_id: Optional[str]
    business_name: Optional[str]
    business_name_ar: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderDataPolicy:
    provider_key: str
    provider_type: str
    persist_crm_fields: bool
    place_id_allowed: bool = False
    permitted_fields: set[str] = field(default_factory=set)
    restricted_fields: set[str] = field(default_factory=set)
    permitted_purposes: list[str] = field(default_factory=list)
    retention_days: Optional[int] = None
    daily_quota: int = 1000
    rate_limit_per_minute: int = 60
    attribution_required: bool = False
    preview_only_restricted: bool = False
    notes: str = ""


class BusinessProvider(ABC):
    """Common abstract provider adapter."""

    key: str
    display_name: str

    @abstractmethod
    async def search(
        self,
        query: ProviderSearchQuery,
    ) -> list[ProviderBusinessRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_details(self, provider_id: str) -> Optional[ProviderBusinessRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_data_policy(self) -> ProviderDataPolicy:
        raise NotImplementedError

    @abstractmethod
    def can_persist(self, field_name: str) -> bool:
        raise NotImplementedError

    def validate_quota(self, requested: int, used_today: int = 0) -> None:
        policy = self.get_data_policy()
        if requested <= 0:
            raise ValueError("Requested volume must be positive")
        remaining = max(policy.daily_quota - used_today, 0)
        if requested > remaining:
            raise ValueError(
                f"Requested {requested} exceeds remaining quota {remaining} "
                f"for provider '{self.key}' (daily_quota={policy.daily_quota})"
            )

    def filter_persistable(
        self,
        record: ProviderBusinessRecord,
    ) -> dict[str, Any]:
        """Return only fields allowed for durable CRM storage."""
        policy = self.get_data_policy()
        candidates = {
            "external_id": record.external_id,
            "business_name": record.business_name,
            "business_name_ar": record.business_name_ar,
            "address": record.address,
            "district": record.district,
            "city": record.city,
            "website_url": record.website_url,
            "phone": record.phone,
            "email": record.email,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "category": record.category,
            "description": record.description,
            "source_url": record.source_url,
        }
        if not policy.persist_crm_fields:
            allowed: dict[str, Any] = {}
            if policy.place_id_allowed and record.external_id:
                allowed["external_id"] = record.external_id
            return allowed

        result: dict[str, Any] = {}
        for name, value in candidates.items():
            if value is None or value == "":
                continue
            if name in policy.restricted_fields:
                continue
            if policy.permitted_fields and name not in policy.permitted_fields:
                continue
            if self.can_persist(name):
                result[name] = value
        return result
