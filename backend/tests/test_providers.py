"""Provider adapter and policy tests."""

import pytest

from app.compliance.source_policy import build_persistable_payload, preview_safe_record
from app.providers.base import ProviderSearchQuery
from app.providers.licensed_directory import LicensedDirectoryProvider
from app.providers.places_api import PlacesApiProvider
from app.providers.registry import get_provider


SAMPLE = [
    {
        "id": "lic-1",
        "business_name": "Riyadh Grill",
        "business_name_ar": "مشويات الرياض",
        "city": "Riyadh",
        "category": "restaurants",
        "phone": "+966511111111",
        "email": "info@riyadhgrill.example",
        "website_url": "https://riyadhgrill.example",
        "address": "Olaya St",
    },
    {
        "id": "lic-2",
        "business_name": "Jeddah Cafe",
        "city": "Jeddah",
        "category": "cafes",
        "phone": "+966522222222",
    },
]


@pytest.mark.asyncio
async def test_licensed_directory_search_and_persist_policy():
    provider = LicensedDirectoryProvider(sample_records=SAMPLE)
    results = await provider.search(
        ProviderSearchQuery(keyword="restaurants", city="Riyadh", category="restaurants", limit=10)
    )
    assert len(results) == 1
    assert provider.can_persist("business_name") is True
    payload = build_persistable_payload(provider, results[0])
    assert payload["business_name"] == "Riyadh Grill"
    assert payload["phone"] == "+966511111111"


@pytest.mark.asyncio
async def test_places_api_persists_candidate_directory_fields():
    provider = PlacesApiProvider(
        sample_records=[
            {
                "place_id": "ChIJ_test",
                "business_name": "Olaya Bites",
                "address": "Olaya St, Riyadh",
                "city": "Riyadh",
                "phone": "+966500000000",
                "website_url": "https://olayabites.example",
                "category": "restaurants",
            }
        ]
    )
    results = await provider.search(ProviderSearchQuery(keyword="restaurant", limit=5))
    assert len(results) == 1
    assert provider.can_persist("business_name") is True
    assert provider.can_persist("external_id") is True
    assert provider.can_persist("phone") is True
    # Email never from Places policy
    assert provider.can_persist("email") is False
    payload = build_persistable_payload(provider, results[0])
    assert payload["external_id"] == "ChIJ_test"
    assert payload["business_name"] == "Olaya Bites"
    assert payload["phone"] == "+966500000000"
    assert payload["website_url"] == "https://olayabites.example"
    preview = preview_safe_record(provider, results[0])
    assert preview["persistable"] is True


def test_quota_enforcement():
    provider = get_provider("licensed_directory", sample_mode=True, sample_records=SAMPLE)
    with pytest.raises(ValueError):
        provider.validate_quota(999999, used_today=0)
