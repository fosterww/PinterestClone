import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "user_me",
            "email": "user_me@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user_me", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user_me"
    assert data["email"] == "user_me@example.com"


@pytest.mark.asyncio
async def test_patch_me_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "user_patch",
            "email": "user_patch@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "user_patch", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]

    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Test User", "bio": "A test bio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user_patch"
    assert data["full_name"] == "Test User"
    assert data["bio"] == "A test bio"
