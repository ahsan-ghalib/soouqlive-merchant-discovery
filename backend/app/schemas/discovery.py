"""Discovery job schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DiscoveryJobCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    country_code: str = "SA"
    city: Optional[str] = None
    district: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    provider: str = "licensed_directory"
    limit: int = Field(default=100, ge=1, le=50000)
    language: str = "both"
    country_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    search_keyword: Optional[str] = None
    search_keyword_ar: Optional[str] = None
    search_parameters: Optional[dict[str, Any]] = None


class DiscoveryPreviewRequest(BaseModel):
    name: Optional[str] = None
    country_code: str = "SA"
    city: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    provider: str = "licensed_directory"
    limit: int = Field(default=20, ge=1, le=100)
    language: str = "both"


class CoverageSweepRequest(BaseModel):
    """Create many Places jobs across districts/cuisines to beat the ~60/query cap."""

    city: str = "Riyadh"
    category: str = "restaurants"
    provider: str = "places_api"
    # districts | cuisines | full
    mode: str = Field(default="districts", pattern="^(districts|cuisines|full)$")
    limit_per_query: int = Field(default=60, ge=1, le=100)
    auto_start: bool = True
    country_code: str = "SA"
    language: str = "en"
    areas: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    max_jobs: int = Field(default=40, ge=1, le=100)


class CityScrapeRequest(BaseModel):
    """One job: full-city Places coverage (districts + keywords + geo grid)."""

    name: Optional[str] = None
    city: str = "Riyadh"
    country_code: str = "SA"
    # all | restaurants | cafes | pharmacies | real-estate | …
    category: str = "all"
    provider: str = "places_api"
    limit_per_query: int = Field(default=60, ge=1, le=100)
    max_queries: int = Field(default=250, ge=1, le=300)
    grid: int = Field(default=7, ge=2, le=9)
    auto_start: bool = True
    language: str = "en"
    country_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = Field(default=None, ge=1, le=80)
    keywords: list[str] = Field(default_factory=list)


class DiscoveryJobOut(BaseModel):
    id: UUID
    name: str
    country_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    provider_id: Optional[UUID] = None
    search_keyword: str
    search_keyword_ar: Optional[str] = None
    search_parameters: Optional[dict[str, Any]] = None
    status: str
    total_expected: int
    total_processed: int
    total_created: int
    total_duplicates: int
    total_failed: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}
