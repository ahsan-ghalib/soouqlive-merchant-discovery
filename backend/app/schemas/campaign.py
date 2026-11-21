"""Campaign schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None
    campaign_type: str
    target_location_id: Optional[UUID] = None
    target_category_id: Optional[UUID] = None
    target_filters: Optional[dict[str, Any]] = None
    status: str = "draft"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    target_location_id: Optional[UUID] = None
    target_category_id: Optional[UUID] = None
    target_filters: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CampaignLeadsAddRequest(BaseModel):
    business_ids: list[UUID] = Field(min_length=1, max_length=2000)
    assigned_to: Optional[UUID] = None


class CampaignQualifyRequest(BaseModel):
    minimum_score: int = Field(default=60, ge=0, le=100)
    rescore: bool = True


class CampaignOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    campaign_type: str
    target_location_id: Optional[UUID] = None
    target_category_id: Optional[UUID] = None
    target_filters: Optional[dict[str, Any]] = None
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
