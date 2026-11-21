"""HTML parsing helpers for contact-page discovery."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

CONTACT_HINTS = (
    "contact",
    "contact-us",
    "contactus",
    "about",
    "about-us",
    "aboutus",
    "terms",
    "privacy",
    "business",
    "info",
    "تواصل",
    "اتصل",
    "من-نحن",
    "عنّا",
    "عنا",
)


def discover_relevant_links(html: str, base_url: str, limit: int = 5) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    base_host = urlparse(base_url).hostname or ""
    found: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if (parsed.hostname or "") != base_host:
            continue
        path = (parsed.path or "/").lower()
        text = (a.get_text(" ", strip=True) or "").lower()
        blob = f"{path} {text}"
        if not any(hint in blob for hint in CONTACT_HINTS):
            continue
        clean = parsed._replace(fragment="").geturl()
        if clean in seen or clean.rstrip("/") == urlparse(base_url)._replace(fragment="").geturl().rstrip("/"):
            continue
        seen.add(clean)
        found.append(clean)
        if len(found) >= limit:
            break
    return found
