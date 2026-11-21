"""Extract public business phone numbers from HTML."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.utils.phone import normalize_phone

_TEL_RE = re.compile(r"tel:([+\d][\d\-\s().]{5,})", re.I)
# Saudi-friendly + generic international patterns
_PHONE_RE = re.compile(
    r"(?:\+?966[\s\-]?)?(?:0?5\d{8}|0?1\d{8}|0?9\d{8}|\+?\d{8,15})"
)


def extract_phones(html: str, default_region: str = "SA") -> list[str]:
    found: set[str] = set()
    soup = BeautifulSoup(html, "lxml")

    for a in soup.select('a[href^="tel:"]'):
        href = a.get("href") or ""
        match = _TEL_RE.search(href)
        if match:
            _add(found, match.group(1), default_region)

    text = soup.get_text(" ", strip=True)
    for match in _PHONE_RE.finditer(text):
        _add(found, match.group(0), default_region)

    # Also scan raw HTML for tel: and common attrs
    for match in _TEL_RE.finditer(html):
        _add(found, match.group(1), default_region)

    return sorted(found)


def _add(bucket: set[str], raw: str, default_region: str) -> None:
    normalized = normalize_phone(raw, default_region=default_region)
    if normalized:
        bucket.add(normalized)
