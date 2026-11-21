"""Business category taxonomy."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BusinessCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_categories"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_business_categories_slug"),
    )

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[Optional["BusinessCategory"]] = relationship(
        remote_side="BusinessCategory.id",
        back_populates="children",
    )
    children: Mapped[list["BusinessCategory"]] = relationship(back_populates="parent")
