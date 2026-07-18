"""Tests de integracion del flujo de autenticacion: registro, login, refresh, logout."""

from httpx import AsyncClient


async def test_register_and_login(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register", json={"email": "alice@example.com", "password": "AlicePass123"}
    )
    assert r.status_code == 201
    assert r.json()["email"] == "alice@example.com"
    assert r.json()["role"] == "user"

    r = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "AlicePass123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": "BobPassword1"}
    await client.post("/auth/register", json=payload)
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "carol@example.com", "password": "CarolPass123"}
    )
    r = await client.post(
        "/auth/login", json={"email": "carol@example.com", "password": "wrong-password"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_protected_endpoint_without_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/auth/me")
    assert r.status_code in (401, 403)


async def test_me_returns_current_user(client: AsyncClient, user_headers: dict[str, str]) -> None:
    r = await client.get("/auth/me", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "test-user@example.com"


async def test_refresh_rotation_and_reuse_rejected(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "dave@example.com", "password": "DavePass123"}
    )
    login = await client.post(
        "/auth/login", json={"email": "dave@example.com", "password": "DavePass123"}
    )
    old_refresh = login.json()["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh

    reuse = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "TOKEN_REVOKED"

    still_valid = await client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert still_valid.status_code == 200


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "erin@example.com", "password": "ErinPass123"}
    )
    login = await client.post(
        "/auth/login", json={"email": "erin@example.com", "password": "ErinPass123"}
    )
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = await client.post(
        "/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert r.status_code == 204

    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_logout_all_revokes_every_session(client: AsyncClient) -> None:
    creds = {"email": "frank@example.com", "password": "FrankPass123"}
    await client.post("/auth/register", json=creds)
    login1 = (await client.post("/auth/login", json=creds)).json()
    login2 = (await client.post("/auth/login", json=creds)).json()

    headers = {"Authorization": f"Bearer {login1['access_token']}"}
    r = await client.post("/auth/logout-all", headers=headers)
    assert r.status_code == 204

    for tokens in (login1, login2):
        r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 401
