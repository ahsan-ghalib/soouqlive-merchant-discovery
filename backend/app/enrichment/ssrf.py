"""SSRF / DNS rebinding protections for website enrichment."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


class SSRFError(Exception):
    pass


_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}


@dataclass
class SafeURL:
    url: str
    hostname: str
    resolved_ips: list[str]


def _is_blocked_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or ip in ipaddress.ip_network("169.254.0.0/16")
        or ip in ipaddress.ip_network("100.64.0.0/10")  # carrier-grade NAT
    )


def validate_public_http_url(url: str) -> SafeURL:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise SSRFError("Only http/https URLs are allowed")
    if not parsed.hostname:
        raise SSRFError("URL hostname is required")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise SSRFError("Hostname is not allowed")

    # Block literal IP hosts that are private
    try:
        if _is_blocked_ip(hostname):
            raise SSRFError("Private/internal IP literals are blocked")
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}") from exc

    resolved: list[str] = []
    for info in infos:
        ip_str = info[4][0]
        resolved.append(ip_str)
        if _is_blocked_ip(ip_str):
            raise SSRFError(f"Resolved IP {ip_str} is private/internal and blocked")

    if not resolved:
        raise SSRFError("No DNS A/AAAA records resolved")

    # Rebuild URL without credentials / fragments
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    clean = parsed._replace(netloc=netloc, fragment="").geturl()
    return SafeURL(url=clean, hostname=hostname, resolved_ips=sorted(set(resolved)))


def validate_redirect_target(url: str, original_host: str) -> SafeURL:
    """Re-validate every redirect hop against SSRF rules."""
    safe = validate_public_http_url(url)
    # Same-site preferred; cross-host redirects still allowed if public
    _ = original_host
    return safe
