"""Provider registry and factory helpers."""

from __future__ import annotations

from typing import Optional

from app.providers.base import BusinessProvider
from app.providers.licensed_directory import LicensedDirectoryProvider
from app.providers.manual_import import ManualImportProvider
from app.providers.places_api import PlacesApiProvider
from app.providers.website_provider import WebsiteProvider

# Map seeded provider names / types / keys → adapter class
_PROVIDER_ALIASES: dict[str, type[BusinessProvider]] = {
    "licensed_directory": LicensedDirectoryProvider,
    "licensed business directory": LicensedDirectoryProvider,
    "places_api": PlacesApiProvider,
    "google places api": PlacesApiProvider,
    "google_places": PlacesApiProvider,
    "public_website": WebsiteProvider,
    "public website enrichment": WebsiteProvider,
    "manual_import": ManualImportProvider,
    "manual csv import": ManualImportProvider,
}


def list_provider_keys() -> list[str]:
    return [
        LicensedDirectoryProvider.key,
        PlacesApiProvider.key,
        WebsiteProvider.key,
        ManualImportProvider.key,
    ]


def get_provider(
    key: str,
    *,
    sample_mode: bool = False,
    sample_records: Optional[list] = None,
) -> BusinessProvider:
    normalized = key.strip().lower()
    cls = _PROVIDER_ALIASES.get(normalized)
    if cls is None:
        raise KeyError(f"Unknown provider '{key}'")

    if cls is LicensedDirectoryProvider:
        return LicensedDirectoryProvider(
            sample_records=sample_records if sample_mode else None,
        )
    if cls is PlacesApiProvider:
        return PlacesApiProvider(
            sample_records=sample_records if sample_mode else None,
        )
    if cls is ManualImportProvider:
        return ManualImportProvider(records=sample_records or [])
    return WebsiteProvider()


def resolve_provider_key(name_or_type: str) -> str:
    provider = get_provider(name_or_type)
    return provider.key
