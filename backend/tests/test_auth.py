"""Authentication endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": client.admin_password,  # type: ignore[attr-defined]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]["tokens"]
    assert "refresh_token" in body["data"]["tokens"]
    assert body["data"]["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": client.admin_password,  # type: ignore[attr-defined]
        },
    )
    token = login.json()["data"]["tokens"]["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == client.admin_email  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_refresh_and_logout(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": client.admin_password,  # type: ignore[attr-defined]
        },
    )
    tokens = login.json()["data"]["tokens"]
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["data"]["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": new_refresh},
    )
    assert logout.status_code == 200

    reuse = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": client.admin_password,  # type: ignore[attr-defined]
        },
    )
    token = login.json()["data"]["tokens"]["access_token"]

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "ChangeMeAdmin123!",
            "new_password": "NewSecurePass123!",
        },
    )
    assert changed.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": "ChangeMeAdmin123!",
        },
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": client.admin_email,  # type: ignore[attr-defined]
            "password": "NewSecurePass123!",
        },
    )
    assert new_login.status_code == 200

    # restore for other tests in same session if any
    restore_token = new_login.json()["data"]["tokens"]["access_token"]
    await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {restore_token}"},
        json={
            "current_password": "NewSecurePass123!",
            "new_password": "ChangeMeAdmin123!",
        },
    )
