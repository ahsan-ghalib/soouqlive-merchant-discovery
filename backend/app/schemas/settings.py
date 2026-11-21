"""Settings schemas (SMTP)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SmtpSettingsOut(BaseModel):
    id: UUID
    host: str
    port: int
    username: Optional[str] = None
    password_set: bool = False
    from_email: str
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    use_tls: bool = True
    use_ssl: bool = False
    is_enabled: bool = False
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmtpSettingsUpdate(BaseModel):
    host: str = Field(default="", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=255)
    # Omit or empty = keep existing password
    password: Optional[str] = Field(default=None, max_length=512)
    from_email: str = Field(default="", max_length=255)
    from_name: Optional[str] = Field(default=None, max_length=255)
    reply_to: Optional[str] = Field(default=None, max_length=255)
    use_tls: bool = True
    use_ssl: bool = False
    is_enabled: bool = False


class SmtpTestRequest(BaseModel):
    to_email: EmailStr
    # Defaults to vendor outreach HTML template when use_template=True
    use_template: bool = True
    template: str = Field(default="vendor_outreach", max_length=64)
    subject: Optional[str] = Field(default=None, max_length=200)
    body: Optional[str] = Field(default=None, max_length=5000)
