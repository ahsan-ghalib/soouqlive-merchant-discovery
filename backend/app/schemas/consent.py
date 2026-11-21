"""Consent schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentCreate(BaseModel):
    business_id: UUID
    contact_id: Optional[UUID] = None
    purpose: str
    channel: str
    consent_status: str = "granted"
    consent_method: str
    consent_evidence: Optional[dict[str, Any]] = None
    consented_at: Optional[datetime] = None


class ConsentWithdrawRequest(BaseModel):
    reason: str = Field(default="withdrawn_by_operator", max_length=100)


class EligibilityCheckRequest(BaseModel):
    business_id: UUID
    purpose: str
    channel: str
    contact_id: Optional[UUID] = None


class ConsentOut(BaseModel):
    id: UUID
    business_id: UUID
    contact_id: Optional[UUID] = None
    purpose: str
    channel: str
    consent_status: str
    consent_method: str
    consent_evidence: Optional[dict[str, Any]] = None
    consented_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
