"""Opt-out / suppression helpers (HMAC hashed values)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.consent import SuppressionRecord
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone


def hash_contact_value(value: str) -> str:
    settings = get_settings()
    normalized = value.strip().lower()
    digest = hmac.new(
        settings.suppression_hmac_secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def normalize_for_suppression(contact_type: str, contact_value: str) -> Optional[str]:
    if contact_type == "business_email":
        return normalize_email(contact_value)
    if contact_type == "business_phone":
        return normalize_phone(contact_value)
    return contact_value.strip().lower() if contact_value else None


async def is_suppressed(
    db: AsyncSession,
    *,
    contact_type: str,
    contact_value: str,
    channel: str,
) -> bool:
    normalized = normalize_for_suppression(contact_type, contact_value)
    if not normalized:
        return False
    value_hash = hash_contact_value(normalized)
    result = await db.execute(
        select(SuppressionRecord).where(
            SuppressionRecord.contact_value_hash == value_hash,
            SuppressionRecord.contact_type == contact_type,
            SuppressionRecord.channel.in_([channel, "all"]),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def add_suppression(
    db: AsyncSession,
    *,
    contact_type: str,
    contact_value: str,
    channel: str,
    reason: str,
) -> SuppressionRecord:
    normalized = normalize_for_suppression(contact_type, contact_value)
    if not normalized:
        raise ValueError("Contact value could not be normalized for suppression")

    value_hash = hash_contact_value(normalized)
    existing = (
        await db.execute(
            select(SuppressionRecord).where(
                SuppressionRecord.contact_value_hash == value_hash,
                SuppressionRecord.contact_type == contact_type,
                SuppressionRecord.channel == channel,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    record = SuppressionRecord(
        id=uuid4(),
        contact_value_hash=value_hash,
        contact_type=contact_type,
        channel=channel,
        reason=reason,
    )
    db.add(record)
    await db.flush()
    return record
