from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from httpx import AsyncClient

from app.core.config import settings


async def _register_and_login(
    client: AsyncClient,
    email: str = "andre@example.com",
    password: str = "supersecret",
    name: str = "Andre",
) -> str:
    await client.post("/auth/register", json={"email": email, "password": password, "name": name})
    login_response = await client.post("/auth/login", json={"email": email, "password": password})
    token: str = login_response.json()["access_token"]
    return token


async def test_register_returns_the_created_user_without_password(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "andre@example.com", "password": "supersecret", "name": "Andre"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "andre@example.com"
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_with_duplicate_email_fails(client: AsyncClient) -> None:
    payload = {"email": "andre@example.com", "password": "supersecret", "name": "Andre"}
    await client.post("/auth/register", json=payload)

    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 400


async def test_login_returns_a_bearer_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "andre@example.com", "password": "supersecret", "name": "Andre"},
    )

    response = await client.post(
        "/auth/login", json={"email": "andre@example.com", "password": "supersecret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def test_login_with_wrong_password_fails(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "andre@example.com", "password": "supersecret", "name": "Andre"},
    )

    response = await client.post(
        "/auth/login", json={"email": "andre@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401


async def test_login_with_unknown_email_fails(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )

    assert response.status_code == 401


async def test_me_returns_the_caller_with_a_valid_token(client: AsyncClient) -> None:
    token = await _register_and_login(client)

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "andre@example.com"


async def test_me_without_a_token_fails(client: AsyncClient) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == 401


async def test_me_with_a_malformed_token_fails(client: AsyncClient) -> None:
    response = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})

    assert response.status_code == 401


async def test_me_with_an_expired_token_fails(client: AsyncClient) -> None:
    expired_payload = {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}
    expired_token = pyjwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401


async def test_patch_me_updates_name_only(client: AsyncClient) -> None:
    token = await _register_and_login(client)

    response = await client.patch(
        "/auth/me", json={"name": "Andre B"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Andre B"
    assert body["email"] == "andre@example.com"


async def test_patch_me_updates_email_only(client: AsyncClient) -> None:
    token = await _register_and_login(client)

    response = await client.patch(
        "/auth/me", json={"email": "new@example.com"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


async def test_patch_me_updates_both_fields(client: AsyncClient) -> None:
    token = await _register_and_login(client)

    response = await client.patch(
        "/auth/me",
        json={"name": "Andre B", "email": "new@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Andre B"
    assert body["email"] == "new@example.com"


async def test_patch_me_with_an_email_taken_by_another_user_fails(client: AsyncClient) -> None:
    token = await _register_and_login(client, email="andre@example.com")
    await client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "whatever1", "name": "Other"},
    )

    response = await client.patch(
        "/auth/me",
        json={"email": "other@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


async def test_patch_me_resubmitting_own_current_email_succeeds(client: AsyncClient) -> None:
    token = await _register_and_login(client)

    response = await client.patch(
        "/auth/me",
        json={"email": "andre@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


async def test_patch_me_without_a_token_fails(client: AsyncClient) -> None:
    response = await client.patch("/auth/me", json={"name": "Nope"})

    assert response.status_code == 401
