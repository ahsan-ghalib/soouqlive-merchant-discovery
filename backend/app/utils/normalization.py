"""General normalization helpers for discovery/dedupe."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from app.utils.arabic import normalize_business_name
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone


def normalize_domain(url_or_host: Optional[str]) -> Optional[str]:
    if not url_or_host:
        return None
    value = url_or_host.strip().lower()
    if not value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    if not host:
        return None
    host = host.split("@")[-1]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def business_match_key(name: str, city: Optional[str] = None) -> str:
    base = normalize_business_name(name)
    city_part = normalize_business_name(city or "")
    return f"{base}|{city_part}".strip("|")


__all__ = [
    "normalize_business_name",
    "normalize_domain",
    "normalize_email",
    "normalize_phone",
    "business_match_key",
]
