"""Consent and suppression models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.contact import BusinessContact


class ConsentRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "consent_records"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_contacts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(30), nullable=False)
    consent_method: Mapped[str] = mapped_column(String(50), nullable=False)
    consent_evidence: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    consented_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship(back_populates="consent_records")
    contact: Mapped[Optional["BusinessContact"]] = relationship(
        back_populates="consent_records",
    )


class SuppressionRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "suppression_records"

    contact_value_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
