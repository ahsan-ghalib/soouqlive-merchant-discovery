"""Business / lead schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


LEAD_STATUSES = {
    "new",
    "researching",
    "qualified",
    "contacted",
    "interested",
    "follow_up",
    "registered",
    "rejected",
    "do_not_contact",
}

BUSINESS_STATUSES = {"unknown", "active", "inactive", "closed"}


class BusinessCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    business_name_ar: Optional[str] = Field(default=None, max_length=255)
    category_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    address: Optional[str] = None
    district: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    business_status: str = "unknown"
    lead_status: str = "new"
    phone: Optional[str] = None
    email: Optional[str] = None
    external_reference: Optional[str] = None
    provider_id: Optional[UUID] = None
    skip_dedupe: bool = False

    @field_validator("lead_status")
    @classmethod
    def validate_lead_status(cls, value: str) -> str:
        if value not in LEAD_STATUSES:
            raise ValueError(f"Invalid lead_status. Allowed: {sorted(LEAD_STATUSES)}")
        return value

    @field_validator("business_status")
    @classmethod
    def validate_business_status(cls, value: str) -> str:
        if value not in BUSINESS_STATUSES:
            raise ValueError(f"Invalid business_status. Allowed: {sorted(BUSINESS_STATUSES)}")
        return value


class BusinessUpdate(BaseModel):
    business_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    business_name_ar: Optional[str] = Field(default=None, max_length=255)
    category_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    address: Optional[str] = None
    district: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    business_status: Optional[str] = None
    lead_status: Optional[str] = None
    qualification_score: Optional[int] = Field(default=None, ge=0, le=100)
    qualification_reason: Optional[dict[str, Any]] = None

    @field_validator("lead_status")
    @classmethod
    def validate_lead_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in LEAD_STATUSES:
            raise ValueError(f"Invalid lead_status. Allowed: {sorted(LEAD_STATUSES)}")
        return value

    @field_validator("business_status")
    @classmethod
    def validate_business_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in BUSINESS_STATUSES:
            raise ValueError(f"Invalid business_status. Allowed: {sorted(BUSINESS_STATUSES)}")
        return value


class BusinessAssignRequest(BaseModel):
    assigned_to: Optional[UUID] = None


class BusinessBulkImportRequest(BaseModel):
    provider: str = "manual_import"
    records: list[dict[str, Any]] = Field(min_length=1, max_length=5000)
    location_id: Optional[UUID] = None
    category_id: Optional[UUID] = None


class BusinessBulkUpdateItem(BaseModel):
    id: UUID
    patch: BusinessUpdate


class BusinessBulkUpdateRequest(BaseModel):
    items: list[BusinessBulkUpdateItem] = Field(min_length=1, max_length=500)


class BusinessOut(BaseModel):
    id: UUID
    business_name: str
    business_name_ar: Optional[str] = None
    normalized_name: Optional[str] = None
    category_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    address: Optional[str] = None
    district: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    business_status: str
    lead_status: str
    qualification_score: int
    qualification_reason: Optional[dict[str, Any]] = None
    assigned_to: Optional[UUID] = None
    first_discovered_at: Optional[datetime] = None
    last_enriched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    has_email: Optional[bool] = None
    has_phone: Optional[bool] = None

    model_config = {"from_attributes": True}


class BusinessListFilters(BaseModel):
    city: Optional[str] = None
    location_id: Optional[UUID] = None
    category: Optional[str] = None
    category_id: Optional[UUID] = None
    lead_status: Optional[str] = None
    business_status: Optional[str] = None
    minimum_score: Optional[int] = Field(default=None, ge=0, le=100)
    maximum_score: Optional[int] = Field(default=None, ge=0, le=100)
    has_website: Optional[bool] = None
    has_email: Optional[bool] = None
    has_phone: Optional[bool] = None
    source: Optional[str] = None
    assigned_to: Optional[UUID] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=200)
