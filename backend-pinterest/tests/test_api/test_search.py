import io

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, username: str, email: str) -> dict:
    await client.post(
        "/api/v2/auth/register",
        json={"username": username, "email": email, "password": "password"},
    )
    login = await client.post(
        "/api/v2/auth/login",
        data={"username": username, "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_image():
    return b"fake_image_content"


@pytest.mark.asyncio
async def test_search_all_returns_users_boards_and_pins(
    client: AsyncClient, fake_image: bytes
):
    headers = await _register_and_login(client, "anna_search", "anna@example.com")

    await client.post(
        "/api/v2/boards/",
        json={"title": "Anna Travel Board"},
        headers=headers,
    )
    await client.post(
        "/api/v2/pins/",
        data={"title": "Anna Sunset Pin"},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )

    response = await client.get("/api/v2/search/?q=Anna&target=all")
    assert response.status_code == 200
    data = response.json()
    assert any(user["username"] == "anna_search" for user in data["users"])
    assert any(board["title"] == "Anna Travel Board" for board in data["boards"])
    assert any(pin["title"] == "Anna Sunset Pin" for pin in data["pins"])


@pytest.mark.asyncio
async def test_search_target_users_only_returns_users(client: AsyncClient):
    await _register_and_login(client, "daria_user", "daria@example.com")

    response = await client.get("/api/v2/search/?q=daria&target=users")
    assert response.status_code == 200
    data = response.json()
    assert any(user["username"] == "daria_user" for user in data["users"])
    assert data["boards"] == []
    assert data["pins"] == []
