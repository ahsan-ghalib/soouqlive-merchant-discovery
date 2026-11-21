"""Lead scoring and CRM workflow tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.category import BusinessCategory
from app.models.contact import BusinessContact
from app.services.scoring_service import ScoringService


async def _auth_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": client.admin_email, "password": client.admin_password},
    )
    token = login.json()["data"]["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_scoring_breakdown(db_session: AsyncSession):
    from sqlalchemy import select

    category = (
        await db_session.execute(
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
        db_session.add(category)
        await db_session.flush()

    business = Business(
        id=uuid.uuid4(),
        business_name="Score Me Grill",
        category_id=category.id,
        website_url="https://score-me-grill.example",
        lead_status="new",
        business_status="unknown",
        qualification_score=0,
    )
    db_session.add(business)
    await db_session.flush()
    db_session.add(
        BusinessContact(
            id=uuid.uuid4(),
            business_id=business.id,
            contact_type="business_phone",
            contact_value="+966501112233",
            normalized_value="+966501112233",
            is_verified=True,
        )
    )
    await db_session.commit()

    breakdown = await ScoringService(db_session).score_business_async(
        business.id,
        auto_qualify=True,
        qualify_threshold=60,
    )
    await db_session.refresh(business)

    assert breakdown.total == 85
    assert breakdown.components["relevant_category"] == 25
    assert breakdown.components["active_website"] == 15
    assert breakdown.components["verified_public_contact"] == 15
    assert breakdown.components["relevant_delivery_service"] == 15
    assert breakdown.components["strong_soouqlive_fit"] == 15
    assert breakdown.components["website_gap_opportunity"] == 0
    assert business.qualification_score == 85
    assert "restaurant_portal" in breakdown.details["monetization_packs"]
    assert business.lead_status == "qualified"
    assert "consent" not in str(business.qualification_reason).lower() or "not a scoring" in str(
        business.qualification_reason
    ).lower()


@pytest.mark.asyncio
async def test_crm_transition_and_pipeline(client: AsyncClient):
    headers = await _auth_headers(client)

    created = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Pipeline Cafe",
            "website_url": "https://pipeline-cafe.example",
            "phone": "0502223344",
            "skip_dedupe": True,
        },
    )
    business_id = created.json()["data"]["business"]["id"]

    scored = await client.post(
        f"/api/v1/crm/businesses/{business_id}/score",
        headers=headers,
        json={"auto_qualify": False, "qualify_threshold": 60},
    )
    assert scored.status_code == 200, scored.text
    assert "components" in scored.json()["data"]

    transition = await client.post(
        f"/api/v1/crm/businesses/{business_id}/transition",
        headers=headers,
        json={"lead_status": "researching", "note": "Starting research"},
    )
    assert transition.status_code == 200
    assert transition.json()["data"]["lead_status"] == "researching"

    bad = await client.post(
        f"/api/v1/crm/businesses/{business_id}/transition",
        headers=headers,
        json={"lead_status": "registered"},
    )
    assert bad.status_code == 400

    qualify = await client.post(
        "/api/v1/crm/leads/qualify",
        headers=headers,
        json={"business_ids": [business_id], "minimum_score": 10, "rescore": True},
    )
    assert qualify.status_code == 200, qualify.text
    assert len(qualify.json()["data"]["qualified"]) == 1

    pipeline = await client.get("/api/v1/crm/leads/pipeline", headers=headers)
    assert pipeline.status_code == 200
    assert "by_status" in pipeline.json()["data"]
