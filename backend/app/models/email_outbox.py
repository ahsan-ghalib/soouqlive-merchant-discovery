"""Slow outbound email blast + outbox tracking."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.contact import BusinessContact


class EmailBlast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_blasts"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False, default="vendor_outreach")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=75)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    total_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["EmailOutboxItem"]] = relationship(
        back_populates="blast",
        cascade="all, delete-orphan",
    )


class EmailOutboxItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "email_outbox_items"
    __table_args__ = (
        UniqueConstraint("blast_id", "to_email", name="uq_email_outbox_blast_email"),
    )

    blast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_blasts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    blast: Mapped[EmailBlast] = relationship(back_populates="items")
    business: Mapped[Optional["Business"]] = relationship()
    contact: Mapped[Optional["BusinessContact"]] = relationship()
