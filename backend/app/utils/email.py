"""Email validation helpers."""

from __future__ import annotations

import re
import socket
from functools import lru_cache
from typing import Optional

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Retina / asset filenames often look like email because of "@2x.png"
_ASSET_DOMAIN_RE = re.compile(
    r"(^|\.)(\d+x)(\.|$)|(^|\.)\d+x\d+(\.|$)",
    re.I,
)
_BAD_TLDS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "css",
    "js",
    "map",
    "woff",
    "woff2",
    "ttf",
    "eot",
    "ico",
    "mp4",
    "webm",
    "pdf",
    "zip",
    "rar",
    "gz",
    "tgz",
    "json",
    "xml",
    "html",
    "htm",
    "php",
    "asp",
    "aspx",
}
_HTML_ENTITY_PREFIX = re.compile(r"^(u00[0-9a-f]{2}|x[0-9a-f]{2}|amp|nbsp)", re.I)
_JUNK_DOMAINS = {
    "sentry.io",
    "wixpress.com",
    "example.com",
    "example.org",
    "email.com",
    "mail.com",
    "test.com",
    "cloudflare.com",
    "schema.org",
    "w3.org",
    "github.com",
    "githubusercontent.com",
}
_JUNK_LOCAL_EXACT = {
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
    "postmaster",
}
_JUNK_SUBSTR = (
    "@sentry.",
    "ingest.",
)


def normalize_email(value: str) -> Optional[str]:
    if not value:
        return None
    email = value.strip().lower()
    # Strip accidental HTML-entity garbage glued to local-part (e.g. u003eservice@…)
    if "@" in email:
        local, domain = email.rsplit("@", 1)
        local = re.sub(r"^(u003[ce]|003[ce]|amp;)+", "", local, flags=re.I)
        email = f"{local}@{domain}" if local else email
    if not _EMAIL_RE.match(email):
        return None
    if is_junk_email(email):
        return None
    return email


def is_valid_email_syntax(value: str) -> bool:
    return normalize_email(value) is not None


def is_junk_email(email: str) -> bool:
    """Reject scrapes that look like files, trackers, or non-mail domains."""
    low = (email or "").strip().lower()
    if not low or "@" not in low:
        return True
    if any(j in low for j in _JUNK_SUBSTR):
        return True
    local, _, domain = low.partition("@")
    if not local or not domain:
        return True
    local_base = local.split("+", 1)[0]
    if local_base in _JUNK_LOCAL_EXACT or local_base.startswith(
        ("noreply", "no-reply", "donotreply")
    ):
        return True
    if domain in _JUNK_DOMAINS or any(domain.endswith(f".{d}") for d in _JUNK_DOMAINS):
        return True
    if _HTML_ENTITY_PREFIX.match(local):
        return True
    if local.startswith(("u003e", "u003c", "003e", "003c")):
        return True
    # Asset / retina filenames: foo@2x.png, asset-1@4x-8-….png
    tld = domain.rsplit(".", 1)[-1]
    if tld in _BAD_TLDS:
        return True
    if _ASSET_DOMAIN_RE.search(domain):
        return True
    if re.search(r"@\d+x", low):
        return True
    # Local part that is clearly a filename stem
    if re.search(r"\.(png|jpe?g|gif|webp|svg|css|js)$", local):
        return True
    if len(local) > 64 or len(domain) > 253:
        return True
    return False


@lru_cache(maxsize=4096)
def domain_has_mx(domain: str) -> bool:
    """True only when DNS publishes MX for the domain (cached)."""
    host = (domain or "").strip().lower().rstrip(".")
    if not host or "." not in host:
        return False
    try:
        import dns.resolver  # type: ignore

        try:
            answers = dns.resolver.resolve(host, "MX")
            return bool(answers)
        except Exception:
            return False
    except ImportError:
        # Weak fallback: port-25 DNS resolve — prefer installing dnspython in prod
        try:
            socket.getaddrinfo(host, 25)
            return True
        except socket.gaierror:
            return False


def is_sendable_email(value: str, *, require_mx: bool = True) -> Optional[str]:
    """Normalize + junk-filter + optional MX check. Returns email or None."""
    email = normalize_email(value)
    if not email:
        return None
    if require_mx:
        domain = email.split("@", 1)[1]
        if not domain_has_mx(domain):
            return None
    return email
