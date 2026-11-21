"""Business contact schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

CONTACT_TYPES = {
    "business_email",
    "business_phone",
    "website_contact_form",
    "social_profile",
    "other",
}


class ContactCreate(BaseModel):
    business_id: UUID
    contact_type: str
    contact_value: str = Field(min_length=1)
    label: Optional[str] = None
    is_primary: bool = False
    source_id: Optional[UUID] = None

    @field_validator("contact_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in CONTACT_TYPES:
            raise ValueError(f"Invalid contact_type. Allowed: {sorted(CONTACT_TYPES)}")
        return value


class ContactUpdate(BaseModel):
    contact_value: Optional[str] = Field(default=None, min_length=1)
    label: Optional[str] = None
    is_primary: Optional[bool] = None
    contact_type: Optional[str] = None

    @field_validator("contact_type")
    @classmethod
    def validate_type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in CONTACT_TYPES:
            raise ValueError(f"Invalid contact_type. Allowed: {sorted(CONTACT_TYPES)}")
        return value


class ContactVerifyRequest(BaseModel):
    verification_method: str = Field(default="manual_review", max_length=50)
    is_verified: bool = True


class ContactSuppressRequest(BaseModel):
    channel: str = Field(description="email|sms|whatsapp|phone|all")
    reason: str = Field(default="operator_suppression", max_length=100)


class ContactOut(BaseModel):
    id: UUID
    business_id: UUID
    contact_type: str
    contact_value: str
    normalized_value: Optional[str] = None
    label: Optional[str] = None
    is_primary: bool
    is_verified: bool
    verification_method: Optional[str] = None
    source_id: Optional[UUID] = None
    collected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
