"""Discovery service and API tests."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.category import BusinessCategory
from app.models.discovery_job import DiscoveryJob
from app.models.location import Country, Location
from app.models.source import DataProvider
from app.providers.licensed_directory import LicensedDirectoryProvider
from app.services.discovery_service import DiscoveryExecutionService, DiscoveryService


SAMPLE_RECORDS = [
    {
        "id": "ext-100",
        "business_name": "Najd Restaurant",
        "business_name_ar": "مطعم نجد",
        "city": "Riyadh",
        "category": "restaurants",
        "phone": "0501112233",
        "email": "hello@najd.example",
        "website_url": "https://najd.example",
        "address": "King Fahd Rd",
    },
    {
        "id": "ext-101",
        "business_name": "Najd Restaurant",
        "city": "Riyadh",
        "category": "restaurants",
        "phone": "0501112233",
        "website_url": "https://najd.example",
    },
]


async def _seed_geo_and_provider(db: AsyncSession) -> dict:
    country = Country(
        id=uuid.uuid4(),
        name="Saudi Arabia",
        name_ar="السعودية",
        iso_code=f"T{uuid.uuid4().hex[:3].upper()}",
        phone_code="+966",
        is_active=True,
    )
    # Keep SA available for API tests that use country_code=SA
    existing = (
        await db.execute(select(Country).where(Country.iso_code == "SA"))
    ).scalar_one_or_none()
    if existing:
        country = existing
    else:
        country.iso_code = "SA"
        db.add(country)
        await db.flush()

    city = (
        await db.execute(
            select(Location).where(
                Location.country_id == country.id,
                Location.slug == "riyadh",
            )
        )
    ).scalar_one_or_none()
    if city is None:
        city = Location(
            id=uuid.uuid4(),
            country_id=country.id,
            name="Riyadh",
            name_ar="الرياض",
            slug="riyadh",
            location_type="city",
            is_active=True,
        )
        db.add(city)

    category = (
        await db.execute(
            select(BusinessCategory).where(BusinessCategory.slug == "restaurants")
        )
    ).scalar_one_or_none()
    if category is None:
        category = BusinessCategory(
            id=uuid.uuid4(),
            name="Restaurants",
            name_ar="مطاعم",
            slug="restaurants",
            is_active=True,
        )
        db.add(category)

    provider = (
        await db.execute(
            select(DataProvider).where(DataProvider.provider_type == "licensed_directory")
        )
    ).scalar_one_or_none()
    if provider is None:
        provider = DataProvider(
            id=uuid.uuid4(),
            name="Licensed Business Directory",
            provider_type="licensed_directory",
            is_active=True,
            policy_reference="licensed-directory-v1",
            data_retention_policy={"persist_crm_fields": True},
            configuration={},
        )
        db.add(provider)

    places = (
        await db.execute(
            select(DataProvider).where(DataProvider.name == "Google Places API")
        )
    ).scalar_one_or_none()
    if places is None:
        db.add(
            DataProvider(
                id=uuid.uuid4(),
                name="Google Places API",
                provider_type="official_api",
                is_active=True,
                policy_reference="google-places-candidate-directory-v2",
                data_retention_policy={"persist_crm_fields": True, "place_id_allowed": True},
                configuration={"adapter_key": "places_api"},
            )
        )

    await db.commit()
    return {
        "country": country,
        "city": city,
        "category": category,
        "provider": provider,
    }


@pytest.mark.asyncio
async def test_preview_and_create_job(client: AsyncClient, db_session: AsyncSession, admin_user):
    await _seed_geo_and_provider(db_session)

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": client.admin_email, "password": client.admin_password},
    )
    token = login.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    preview = await client.post(
        "/api/v1/discovery/preview",
        headers=headers,
        json={
            "country_code": "SA",
            "city": "Riyadh",
            "category": "restaurants",
            "keywords": ["restaurants", "مطاعم"],
            "provider": "licensed_directory",
            "limit": 5,
        },
    )
    # Without API key / samples, preview returns empty success
    assert preview.status_code == 200
    assert preview.json()["success"] is True

    created = await client.post(
        "/api/v1/discovery/jobs",
        headers=headers,
        json={
            "name": "Riyadh Restaurants",
            "country_code": "SA",
            "city": "Riyadh",
            "category": "restaurants",
            "keywords": ["restaurants", "مطاعم"],
            "provider": "licensed_directory",
            "limit": 10,
            "language": "both",
        },
    )
    assert created.status_code == 200, created.text
    job = created.json()["data"]
    assert job["status"] == "pending"
    assert job["total_expected"] == 10


@pytest.mark.asyncio
async def test_places_quota_and_candidate_persist_preview(db_session: AsyncSession, admin_user):
    seeded = await _seed_geo_and_provider(db_session)
    service = DiscoveryService(db_session)

    with pytest.raises(Exception):
        await service.preview(
            {
                "provider": "places_api",
                "keywords": ["restaurant"],
                "limit": 999999,
            }
        )

    preview = await service.preview(
        {
            "provider": "places_api",
            "keywords": ["restaurant"],
            "city": "Riyadh",
            "limit": 2,
        },
        sample_records=[
            {
                "place_id": "abc",
                "business_name": "Candidate Cafe",
                "city": "Riyadh",
                "phone": "+966511122233",
            }
        ],
    )
    assert preview["count"] == 1
    assert preview["results"][0]["persistable"] is True
    assert preview["results"][0]["business_name"] == "Candidate Cafe"


@pytest.mark.asyncio
async def test_execution_creates_and_dedupes(db_session: AsyncSession, admin_user):
    seeded = await _seed_geo_and_provider(db_session)
    service = DiscoveryService(db_session)
    job = await service.create_job(
        {
            "name": "Exec Test",
            "country_code": "SA",
            "city": "Riyadh",
            "category": "restaurants",
            "keywords": ["restaurants"],
            "provider": "licensed_directory",
            "limit": 10,
        },
        admin_user,
    )
    job.status = "queued"
    await db_session.commit()

    from app.core.sync_database import SyncSessionLocal

    with patch(
        "app.services.discovery_service.get_provider",
        return_value=LicensedDirectoryProvider(sample_records=SAMPLE_RECORDS),
    ):
        sync = SyncSessionLocal()
        try:
            result = DiscoveryExecutionService(sync).execute_job(job.id)
            sync.commit()
        finally:
            sync.close()

    assert result.get("created") == 1, result
    assert result.get("duplicates") == 1, result
    assert result.get("status") == "completed", result

    businesses = (
        await db_session.execute(select(Business).where(Business.business_name == "Najd Restaurant"))
    ).scalars().all()
    assert len(businesses) == 1
