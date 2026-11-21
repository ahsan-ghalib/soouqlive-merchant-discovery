"""Seed Saudi Arabia locations, merchant categories, providers, and admin user."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Allow running as `python -m scripts.seed_data` from backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.category import BusinessCategory
from app.models.location import Country, Location
from app.models.source import DataProvider
from app.models.user import User

CATEGORIES = [
    ("Restaurants", "مطاعم", "restaurants"),
    ("Cafes", "مقاهي", "cafes"),
    ("Bakeries", "مخابز", "bakeries"),
    ("Grocery Stores", "بقالات", "grocery-stores"),
    ("Supermarkets", "سوبر ماركت", "supermarkets"),
    ("Dessert Shops", "محلات حلويات", "dessert-shops"),
    ("Flower Shops", "محلات ورد", "flower-shops"),
    ("Fashion Stores", "محلات ملابس", "fashion-stores"),
    ("Cosmetics", "مستحضرات تجميل", "cosmetics"),
    ("Electronics", "إلكترونيات", "electronics"),
    ("Pharmacies", "صيدليات", "pharmacies"),
]

# Major Saudi cities (expand districts later)
CITIES = [
    ("Riyadh", "الرياض", "riyadh", 24.7136, 46.6753),
    ("Jeddah", "جدة", "jeddah", 21.4858, 39.1925),
    ("Dammam", "الدمام", "dammam", 26.4207, 50.0888),
    ("Mecca", "مكة المكرمة", "mecca", 21.3891, 39.8579),
    ("Medina", "المدينة المنورة", "medina", 24.5247, 39.5692),
    ("Khobar", "الخبر", "khobar", 26.2172, 50.1971),
    ("Taif", "الطائف", "taif", 21.2703, 40.4158),
    ("Tabuk", "تبوك", "tabuk", 28.3998, 36.5700),
    ("Abha", "أبها", "abha", 18.2164, 42.5053),
    ("Buraydah", "بريدة", "buraydah", 26.3260, 43.9750),
]

PROVIDERS = [
    {
        "name": "Licensed Business Directory",
        "provider_type": "licensed_directory",
        "policy_reference": "licensed-directory-v1",
        "data_retention_policy": {
            "persist_crm_fields": True,
            "retention_days": 730,
            "notes": "Independently licensed dataset eligible for CRM persistence",
        },
        "configuration": {"default_quota_per_day": 10000},
    },
    {
        "name": "Google Places API",
        "provider_type": "official_api",
        "policy_reference": "google-places-candidate-directory-v2",
        "data_retention_policy": {
            "persist_crm_fields": True,
            "place_id_allowed": True,
            "retention_days": 365,
            "notes": (
                "Paid Places API candidate directory. Store place_id as external_id. "
                "Email via website enrichment. Attribution required."
            ),
        },
        "configuration": {
            "default_quota_per_day": 1000,
            "adapter_key": "places_api",
            "fetch_details": False,
        },
    },
    {
        "name": "Public Website Enrichment",
        "provider_type": "public_website",
        "policy_reference": "public-website-robots-v1",
        "data_retention_policy": {
            "persist_crm_fields": True,
            "requires_robots_check": True,
            "retention_days": 365,
        },
        "configuration": {"max_pages_per_domain": 5},
    },
    {
        "name": "Manual CSV Import",
        "provider_type": "manual_import",
        "policy_reference": "manual-import-v1",
        "data_retention_policy": {
            "persist_crm_fields": True,
            "retention_days": 730,
        },
        "configuration": {},
    },
]


async def seed() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        # Admin user
        result = await session.execute(
            select(User).where(User.email == settings.seed_admin_email.lower())
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            session.add(
                User(
                    id=uuid.uuid4(),
                    full_name=settings.seed_admin_name,
                    email=settings.seed_admin_email.lower(),
                    password_hash=hash_password(settings.seed_admin_password),
                    role="admin",
                    is_active=True,
                )
            )
            print(f"Created admin user: {settings.seed_admin_email}")
        else:
            print(f"Admin user already exists: {settings.seed_admin_email}")

        # Saudi Arabia
        result = await session.execute(select(Country).where(Country.iso_code == "SA"))
        country = result.scalar_one_or_none()
        if country is None:
            country = Country(
                id=uuid.uuid4(),
                name="Saudi Arabia",
                name_ar="المملكة العربية السعودية",
                iso_code="SA",
                phone_code="+966",
                is_active=True,
            )
            session.add(country)
            await session.flush()
            print("Created country: Saudi Arabia")
        else:
            print("Country already exists: Saudi Arabia")

        # Country-level location node
        result = await session.execute(
            select(Location).where(
                Location.country_id == country.id,
                Location.slug == "saudi-arabia",
            )
        )
        country_loc = result.scalar_one_or_none()
        if country_loc is None:
            country_loc = Location(
                id=uuid.uuid4(),
                country_id=country.id,
                parent_id=None,
                name="Saudi Arabia",
                name_ar="المملكة العربية السعودية",
                slug="saudi-arabia",
                location_type="country",
                is_active=True,
            )
            session.add(country_loc)
            await session.flush()

        for name, name_ar, slug, lat, lng in CITIES:
            result = await session.execute(
                select(Location).where(
                    Location.country_id == country.id,
                    Location.slug == slug,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    Location(
                        id=uuid.uuid4(),
                        country_id=country.id,
                        parent_id=country_loc.id,
                        name=name,
                        name_ar=name_ar,
                        slug=slug,
                        location_type="city",
                        latitude=lat,
                        longitude=lng,
                        is_active=True,
                    )
                )
        print(f"Ensured {len(CITIES)} Saudi cities")

        for name, name_ar, slug in CATEGORIES:
            result = await session.execute(
                select(BusinessCategory).where(BusinessCategory.slug == slug)
            )
            if result.scalar_one_or_none() is None:
                session.add(
                    BusinessCategory(
                        id=uuid.uuid4(),
                        parent_id=None,
                        name=name,
                        name_ar=name_ar,
                        slug=slug,
                        description=f"{name} / {name_ar}",
                        is_active=True,
                    )
                )
        print(f"Ensured {len(CATEGORIES)} business categories")

        for provider in PROVIDERS:
            result = await session.execute(
                select(DataProvider).where(DataProvider.name == provider["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    DataProvider(
                        id=uuid.uuid4(),
                        name=provider["name"],
                        provider_type=provider["provider_type"],
                        policy_reference=provider["policy_reference"],
                        data_retention_policy=provider["data_retention_policy"],
                        configuration=provider["configuration"],
                        is_active=True,
                    )
                )
            else:
                existing.policy_reference = provider["policy_reference"]
                existing.data_retention_policy = provider["data_retention_policy"]
                existing.configuration = provider["configuration"]
                existing.is_active = True
        print(f"Ensured {len(PROVIDERS)} data providers")

        await session.commit()
        print("Seed completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
