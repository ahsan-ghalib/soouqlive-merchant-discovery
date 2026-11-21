"""Phone normalization helpers (E.164 for Saudi numbers)."""

from __future__ import annotations

from typing import Optional

import phonenumbers
from phonenumbers import NumberParseException


def normalize_phone(value: str, default_region: str = "SA") -> Optional[str]:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def phones_equal(a: str, b: str, default_region: str = "SA") -> bool:
    na = normalize_phone(a, default_region)
    nb = normalize_phone(b, default_region)
    return bool(na and nb and na == nb)
