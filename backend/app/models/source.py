"""Data providers and lead provenance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business


class DataProvider(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "data_providers"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_retention_policy: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    configuration: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    lead_sources: Mapped[list[LeadSource]] = relationship(back_populates="provider")


class LeadSource(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "lead_sources"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_providers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collection_method: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    permitted_purposes: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    provider: Mapped[DataProvider] = relationship(back_populates="lead_sources")
    business: Mapped[Business] = relationship(back_populates="lead_sources")
