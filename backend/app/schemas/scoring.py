"""Scoring and CRM schemas."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ScoreBusinessRequest(BaseModel):
    auto_qualify: bool = True
    qualify_threshold: int = Field(default=60, ge=0, le=100)


class ScoreBulkRequest(BaseModel):
    business_ids: list[UUID] = Field(min_length=1, max_length=500)
    auto_qualify: bool = True
    qualify_threshold: int = Field(default=60, ge=0, le=100)
    async_mode: bool = True


class LeadTransitionRequest(BaseModel):
    lead_status: str
    note: Optional[str] = None
    force: bool = False


class QualifyRequest(BaseModel):
    business_ids: Optional[list[UUID]] = None
    minimum_score: int = Field(default=60, ge=0, le=100)
    rescore: bool = True
    limit: int = Field(default=500, ge=1, le=5000)
