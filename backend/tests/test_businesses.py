"""Business management and deduplication tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import DataProvider
from sqlalchemy import select


async def _auth_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": client.admin_email, "password": client.admin_password},
    )
    token = login.json()["data"]["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_list_update_assign_business(client: AsyncClient):
    headers = await _auth_headers(client)

    created = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Oasis Pharmacy",
            "business_name_ar": "صيدلية الواحة",
            "website_url": "https://oasis-pharmacy.example",
            "phone": "0509998877",
            "email": "hello@oasis-pharmacy.example",
            "lead_status": "new",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["dedupe"] is None
    business_id = body["business"]["id"]

    listed = await client.get(
        "/api/v1/businesses",
        headers=headers,
        params={"search": "Oasis", "has_phone": True, "has_website": True},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] >= 1

    updated = await client.patch(
        f"/api/v1/businesses/{business_id}",
        headers=headers,
        json={"lead_status": "qualified", "qualification_score": 70},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["lead_status"] == "qualified"
    assert updated.json()["data"]["qualification_score"] == 70

    # assign to self via /auth/me
    me = await client.get("/api/v1/auth/me", headers=headers)
    user_id = me.json()["data"]["id"]
    assigned = await client.post(
        f"/api/v1/businesses/{business_id}/assign",
        headers=headers,
        json={"assigned_to": user_id},
    )
    assert assigned.status_code == 200
    assert assigned.json()["data"]["assigned_to"] == user_id

    contacts = await client.get(
        f"/api/v1/businesses/{business_id}/contacts",
        headers=headers,
    )
    assert contacts.status_code == 200
    assert len(contacts.json()["data"]) >= 2

    activities = await client.get(
        f"/api/v1/businesses/{business_id}/activities",
        headers=headers,
    )
    assert activities.status_code == 200
    assert activities.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_duplicate_create_merges(client: AsyncClient):
    headers = await _auth_headers(client)

    first = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Desert Dates Co",
            "website_url": "https://desert-dates.example",
            "phone": "0551112233",
        },
    )
    assert first.status_code == 200
    first_id = first.json()["data"]["business"]["id"]

    second = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Desert Dates Company",
            "website_url": "https://www.desert-dates.example",
            "email": "sales@desert-dates.example",
            "address": "Riyadh Road",
        },
    )
    assert second.status_code == 200
    payload = second.json()["data"]
    assert payload["dedupe"]["duplicate"] is True
    assert payload["dedupe"]["strategy"] == "website_domain"
    assert payload["business"]["id"] == first_id

    contacts = await client.get(
        f"/api/v1/businesses/{first_id}/contacts",
        headers=headers,
    )
    emails = [c for c in contacts.json()["data"] if c["contact_type"] == "business_email"]
    assert len(emails) == 1


@pytest.mark.asyncio
async def test_soft_delete_and_contact_suppress(client: AsyncClient):
    headers = await _auth_headers(client)

    created = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={
            "business_name": "Suppress Me Shop",
            "email": "optout@suppress-me.example",
            "phone": "0567778899",
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

    suppressed = await client.post(
        f"/api/v1/contacts/{email_contact['id']}/suppress",
        headers=headers,
        json={"channel": "email", "reason": "operator_request"},
    )
    assert suppressed.status_code == 200
    assert suppressed.json()["data"]["channel"] == "email"

    deleted = await client.delete(
        f"/api/v1/businesses/{business_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["soft_deleted"] is True

    got = await client.get(f"/api/v1/businesses/{business_id}", headers=headers)
    assert got.json()["data"]["lead_status"] == "rejected"


@pytest.mark.asyncio
async def test_bulk_import(client: AsyncClient, db_session: AsyncSession):
    # Ensure provider exists
    existing = (
        await db_session.execute(
            select(DataProvider).where(DataProvider.provider_type == "manual_import")
        )
    ).scalar_one_or_none()
    if existing is None:
        db_session.add(
            DataProvider(
                id=uuid.uuid4(),
                name="Manual CSV Import",
                provider_type="manual_import",
                is_active=True,
                policy_reference="manual-import-v1",
                data_retention_policy={"persist_crm_fields": True},
            )
        )
        await db_session.commit()

    headers = await _auth_headers(client)
    response = await client.post(
        "/api/v1/businesses/bulk-import",
        headers=headers,
        json={
            "provider": "manual_import",
            "records": [
                {
                    "business_name": "Bulk One",
                    "phone": "0501231111",
                    "website_url": "https://bulk-one.example",
                },
                {
                    "business_name": "Bulk Two",
                    "email": "two@bulk.example",
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["created"] == 2
    assert data["failed"] == 0
