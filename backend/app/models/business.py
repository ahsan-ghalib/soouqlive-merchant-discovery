"""Central merchant prospect (business) model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaign import CampaignLead
    from app.models.category import BusinessCategory
    from app.models.consent import ConsentRecord
    from app.models.contact import BusinessContact
    from app.models.discovery_job import EnrichmentJob
    from app.models.location import Location
    from app.models.source import LeadSource
    from app.models.user import User
    from app.models.activity import Activity


class Business(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "businesses"

    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name_ar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7), nullable=True)
    business_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    lead_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="new",
        index=True,
    )
    qualification_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )
    qualification_reason: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_discovered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    category: Mapped[Optional["BusinessCategory"]] = relationship()
    location: Mapped[Optional["Location"]] = relationship()
    assignee: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to])
    contacts: Mapped[list["BusinessContact"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
    )
    lead_sources: Mapped[list["LeadSource"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
    )
    enrichment_jobs: Mapped[list["EnrichmentJob"]] = relationship(
        back_populates="business",
        cascade="all, delete-orphan",
    )
    consent_records: Mapped[list["ConsentRecord"]] = relationship(
        back_populates="business",
    )
    campaign_leads: Mapped[list["CampaignLead"]] = relationship(
        back_populates="business",
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="business",
    )
