"""Consent eligibility and campaign management tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": client.admin_email, "password": client.admin_password},
    )
    token = login.json()["data"]["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_consent_required_for_eligibility(client: AsyncClient):
    headers = await _auth_headers(client)

    created = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Consent Cafe",
            "email": "hello@consent-cafe.example",
            "phone": "0503332211",
            "skip_dedupe": True,
        },
    )
    business_id = created.json()["data"]["business"]["id"]
    contacts = await client.get(
        f"/api/v1/businesses/{business_id}/contacts",
        headers=headers,
    )
    email_contact = next(
        c for c in contacts.json()["data"] if c["contact_type"] == "business_email"
    )

    # Public contact alone is NOT eligible
    check = await client.post(
        "/api/v1/consent/check-eligibility",
        headers=headers,
        json={
            "business_id": business_id,
            "contact_id": email_contact["id"],
            "purpose": "promotional_email",
            "channel": "email",
        },
    )
    assert check.status_code == 200
    assert check.json()["data"]["eligible"] is False
    assert "missing_granted_consent" in check.json()["data"]["reasons"]

    # Grant consent with evidence
    granted = await client.post(
        "/api/v1/consent",
        headers=headers,
        json={
            "business_id": business_id,
            "contact_id": email_contact["id"],
            "purpose": "promotional_email",
            "channel": "email",
            "consent_status": "granted",
            "consent_method": "digital_opt_in",
            "consent_evidence": {"source": "merchant_form", "ref": "FORM-1"},
        },
    )
    assert granted.status_code == 200, granted.text
    consent_id = granted.json()["data"]["id"]

    check2 = await client.post(
        "/api/v1/consent/check-eligibility",
        headers=headers,
        json={
            "business_id": business_id,
            "contact_id": email_contact["id"],
            "purpose": "promotional_email",
            "channel": "email",
        },
    )
    assert check2.json()["data"]["eligible"] is True

    # Withdraw → not eligible + suppressed
    withdrawn = await client.post(
        f"/api/v1/consent/{consent_id}/withdraw",
        headers=headers,
        json={"reason": "merchant_request"},
    )
    assert withdrawn.status_code == 200

    check3 = await client.post(
        "/api/v1/consent/check-eligibility",
        headers=headers,
        json={
            "business_id": business_id,
            "contact_id": email_contact["id"],
            "purpose": "promotional_email",
            "channel": "email",
        },
    )
    assert check3.json()["data"]["eligible"] is False


@pytest.mark.asyncio
async def test_campaign_flow(client: AsyncClient):
    headers = await _auth_headers(client)

    b1 = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Campaign Merchant One",
            "website_url": "https://campaign-one.example",
            "phone": "0504445566",
            "skip_dedupe": True,
        },
    )
    b2 = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Campaign Merchant Two",
            "website_url": "https://campaign-two.example",
            "skip_dedupe": True,
        },
    )
    id1 = b1.json()["data"]["business"]["id"]
    id2 = b2.json()["data"]["business"]["id"]

    campaign = await client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "name": "Riyadh Acquisition Q1",
            "campaign_type": "merchant_acquisition",
            "description": "Acquire restaurants",
            "status": "draft",
        },
    )
    assert campaign.status_code == 200, campaign.text
    campaign_id = campaign.json()["data"]["id"]

    added = await client.post(
        f"/api/v1/campaigns/{campaign_id}/leads",
        headers=headers,
        json={"business_ids": [id1, id2]},
    )
    assert added.status_code == 200
    assert len(added.json()["data"]["added"]) == 2

    activate = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert activate.status_code == 200

    qualify = await client.post(
        f"/api/v1/campaigns/{campaign_id}/qualify",
        headers=headers,
        json={"minimum_score": 5, "rescore": True},
    )
    assert qualify.status_code == 200, qualify.text

    analytics = await client.get(
        f"/api/v1/campaigns/{campaign_id}/analytics",
        headers=headers,
    )
    assert analytics.status_code == 200
    assert analytics.json()["data"]["total_businesses"] == 2

    removed = await client.delete(
        f"/api/v1/campaigns/{campaign_id}/leads/{id2}",
        headers=headers,
    )
    assert removed.status_code == 200
