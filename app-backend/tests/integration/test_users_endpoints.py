"""Tests de integracion de la gestion de usuarios."""

from httpx import AsyncClient


async def test_list_users_requires_admin(client: AsyncClient, user_headers: dict[str, str]) -> None:
    r = await client.get("/users/", headers=user_headers)
    assert r.status_code == 403


async def test_list_users_as_admin(
    client: AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    r = await client.get("/users/", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total_items"] >= 2
    emails = {item["email"] for item in body["items"]}
    assert "test-user@example.com" in emails
    assert "test-admin@example.com" in emails


async def test_user_can_view_own_profile_but_not_others(
    client: AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    me = await client.get("/auth/me", headers=user_headers)
    my_id = me.json()["id"]

    own_profile = await client.get(f"/users/{my_id}", headers=user_headers)
    assert own_profile.status_code == 200

    admin_me = await client.get("/auth/me", headers=admin_headers)
    admin_id = admin_me.json()["id"]

    other_profile = await client.get(f"/users/{admin_id}", headers=user_headers)
    assert other_profile.status_code == 403


async def test_admin_can_update_user_role(
    client: AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    me = await client.get("/auth/me", headers=user_headers)
    user_id = me.json()["id"]

    r = await client.patch(f"/users/{user_id}", json={"is_active": False}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # El usuario desactivado ya no puede usar su access token existente.
    blocked = await client.get("/auth/me", headers=user_headers)
    assert blocked.status_code == 401
