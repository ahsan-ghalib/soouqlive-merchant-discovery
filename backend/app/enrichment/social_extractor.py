"""Extract public social profile links."""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

_SOCIAL_HOSTS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "snapchat.com": "snapchat",
}


def extract_social_profiles(html: str, base_url: str | None = None) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        host = urlparse(href).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        for domain, network in _SOCIAL_HOSTS.items():
            if host == domain or host.endswith("." + domain):
                # Prefer first stable profile URL
                found.setdefault(network, href)
                break

    return [{"network": k, "url": v} for k, v in sorted(found.items())]
