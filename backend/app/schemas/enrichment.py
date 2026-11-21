"""Enrichment API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EnrichmentJobCreate(BaseModel):
    business_id: UUID
    job_type: str = Field(default="website_discovery")


class EnrichmentBulkRequest(BaseModel):
    business_ids: list[UUID] = Field(min_length=1, max_length=500)
    job_type: str = Field(default="website_discovery")


class EnrichmentJobOut(BaseModel):
    id: UUID
    business_id: UUID
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    error_message: Optional[str] = None
    result_summary: Optional[dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
