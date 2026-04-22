import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v2/users/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "user_me",
            "email": "user_me@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "user_me", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v2/users/", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user_me"
    assert data["email"] == "user_me@example.com"
    assert data["email_notifications_enabled"] is True


@pytest.mark.asyncio
async def test_patch_me_success(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "user_patch",
            "email": "user_patch@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "user_patch", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]

    response = await client.patch(
        "/api/v2/users/",
        json={"full_name": "Test User", "bio": "A test bio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "user_patch"
    assert data["full_name"] == "Test User"
    assert data["bio"] == "A test bio"
    assert data["email_notifications_enabled"] is True


@pytest.mark.asyncio
async def test_patch_me_can_disable_email_notifications(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "user_notifications",
            "email": "user_notifications@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "user_notifications", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]

    response = await client.patch(
        "/api/v2/users/",
        json={"email_notifications_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email_notifications_enabled"] is False


@pytest.mark.asyncio
async def test_get_public_user_profile_success(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "public_user",
            "email": "public_user@example.com",
            "password": "password",
            "bio": "public bio",
        },
    )

    response = await client.get("/api/v2/users/public_user")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "public_user"
    assert data["bio"] == "public bio"
    assert "email" not in data


@pytest.mark.asyncio
async def test_get_user_boards_hides_secret_boards_from_anonymous(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "boards_public_user",
            "email": "boards_public@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "boards_public_user", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v2/boards/",
        json={"title": "Public Board", "visibility": "public"},
        headers=headers,
    )
    await client.post(
        "/api/v2/boards/",
        json={"title": "Secret Board", "visibility": "secret"},
        headers=headers,
    )

    response = await client.get("/api/v2/users/boards_public_user/boards")
    assert response.status_code == 200
    titles = {board["title"] for board in response.json()}
    assert titles == {"Public Board"}


@pytest.mark.asyncio
async def test_get_user_boards_owner_can_see_secret_boards(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "boards_owner_user",
            "email": "boards_owner@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "boards_owner_user", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/v2/boards/",
        json={"title": "Secret Board", "visibility": "secret"},
        headers=headers,
    )

    response = await client.get(
        "/api/v2/users/boards_owner_user/boards", headers=headers
    )
    assert response.status_code == 200
    titles = {board["title"] for board in response.json()}
    assert "Secret Board" in titles
