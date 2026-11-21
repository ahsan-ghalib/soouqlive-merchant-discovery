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

_DISCARD_DOMAINS = {
    "example.com",
    "example.org",
    "sentry.io",
    "wixpress.com",
    "cloudflare.com",
    "schema.org",
}


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
    email = normalize_email(raw)
    if not email:
        return
    domain = email.split("@", 1)[1]
    if domain in _DISCARD_DOMAINS:
        return
    if any(email.endswith(f"@{d}") for d in _DISCARD_DOMAINS):
        return
    bucket.add(email)
