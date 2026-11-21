"""Email validation helpers."""

from __future__ import annotations

import re
from typing import Optional

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(value: str) -> Optional[str]:
    if not value:
        return None
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        return None
    return email


def is_valid_email_syntax(value: str) -> bool:
    return normalize_email(value) is not None
