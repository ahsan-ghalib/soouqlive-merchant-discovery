"""Extract public business emails from HTML."""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup

from app.utils.email import normalize_email

_MAILTO_RE = re.compile(r"mailto:([^?\"'\s>]+)", re.I)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)


def extract_emails(html: str, page_url: str | None = None) -> list[str]:
    found: set[str] = set()
    soup = BeautifulSoup(html, "lxml")

    for a in soup.select('a[href^="mailto:"]'):
        href = a.get("href") or ""
        match = _MAILTO_RE.search(href)
        if match:
            _add(found, match.group(1))

    text = soup.get_text(" ", strip=True)
    for match in _EMAIL_RE.finditer(html):
        _add(found, match.group(0))
    for match in _EMAIL_RE.finditer(text):
        _add(found, match.group(0))

    return sorted(found)


def _add(bucket: set[str], raw: str) -> None:
    # normalize_email already drops junk/asset scrapes
    email = normalize_email(raw)
    if email:
        bucket.add(email)
