"""Application-level settings (SMTP, etc.)."""

from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SmtpSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Singleton SMTP outbound mail configuration."""

    __tablename__ = "smtp_settings"

    host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
