"""Parse JSON-LD LocalBusiness / Organization structured data."""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup


def extract_json_ld_business(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, Any] = {
        "names": [],
        "phones": [],
        "emails": [],
        "websites": [],
        "addresses": [],
        "same_as": [],
    }

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(payload):
            _ingest_node(node, result)

    # Deduplicate lists
    for key in list(result.keys()):
        values = result[key]
        if isinstance(values, list):
            result[key] = list(dict.fromkeys([v for v in values if v]))
    return result


def _iter_nodes(payload: Any):
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_nodes(item)
        return
    if isinstance(payload, dict):
        if "@graph" in payload and isinstance(payload["@graph"], list):
            for item in payload["@graph"]:
                yield from _iter_nodes(item)
        yield payload


def _ingest_node(node: dict[str, Any], result: dict[str, Any]) -> None:
    type_val = node.get("@type")
    types = type_val if isinstance(type_val, list) else [type_val]
    types = [str(t).lower() for t in types if t]
    interesting = {
        "localbusiness",
        "organization",
        "restaurant",
        "store",
        "foodestablishment",
        "corporation",
    }
    if types and not any(t in interesting or t.endswith("business") for t in types):
        # Still collect contact points if present
        pass

    name = node.get("name")
    if isinstance(name, str):
        result["names"].append(name)

    telephone = node.get("telephone")
    if isinstance(telephone, str):
        result["phones"].append(telephone)
    elif isinstance(telephone, list):
        result["phones"].extend([t for t in telephone if isinstance(t, str)])

    email = node.get("email")
    if isinstance(email, str):
        result["emails"].append(email)

    url = node.get("url")
    if isinstance(url, str):
        result["websites"].append(url)

    same_as = node.get("sameAs")
    if isinstance(same_as, str):
        result["same_as"].append(same_as)
    elif isinstance(same_as, list):
        result["same_as"].extend([s for s in same_as if isinstance(s, str)])

    address = node.get("address")
    if isinstance(address, str):
        result["addresses"].append(address)
    elif isinstance(address, dict):
        parts = [
            address.get("streetAddress"),
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("postalCode"),
            address.get("addressCountry"),
        ]
        joined = ", ".join([p for p in parts if isinstance(p, str) and p])
        if joined:
            result["addresses"].append(joined)
