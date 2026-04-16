import pytest
from httpx import AsyncClient
import io


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


async def _create_pin(
    client: AsyncClient,
    headers: dict,
    title: str,
    tags: list | None = None,
    fake_image: bytes = b"img",
) -> dict:
    data: dict = {"title": title}
    if tags:
        for tag in tags:
            data["tags"] = tag

    request_data = {"title": title}
    if tags:
        request_data["tags"] = tags

    response = await client.post(
        "/api/v2/pins/",
        data=request_data,
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def fake_image():
    return b"fake_image_content"


@pytest.mark.asyncio
async def test_api_personalized_feed(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(client, "personal_user", "personal@example.com")

    await _create_pin(
        client, headers, "Mountain", tags=["nature"], fake_image=fake_image
    )
    await _create_pin(client, headers, "City", tags=["urban"], fake_image=fake_image)
    pin3 = await _create_pin(
        client, headers, "Forest", tags=["nature"], fake_image=fake_image
    )

    response = await client.get(f"/api/v2/pins/{pin3['id']}", headers=headers)
    assert response.status_code == 200

    response = await client.get("/api/v2/pins/personalized", headers=headers)
    assert response.status_code == 200
    pins = response.json()
    assert len(pins) == 3
    titles = [p["title"] for p in pins]

    assert titles[0] == "Forest"
    assert titles[1] == "City"
    assert titles[2] == "Mountain"
