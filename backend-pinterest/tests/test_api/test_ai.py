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


@pytest.mark.asyncio
async def test_generate_image_and_create_pin_from_generated_asset(client: AsyncClient):
    headers = await _register_and_login(client, "ai_user", "ai_user@example.com")

    generate_response = await client.post(
        "/api/v2/ai/generate-image",
        json={
            "prompt": "A cozy modern reading corner with warm sunlight",
            "style": "editorial interior photo",
        },
        headers=headers,
    )
    assert generate_response.status_code == 200, generate_response.text

    generated_image = generate_response.json()["generated_images"][0]
    assert generated_image["image_url"].startswith("http://mock-s3-url.com/generated/")

    create_response = await client.post(
        "/api/v2/pins/",
        files=[
            ("title", (None, "AI Reading Corner")),
            ("generated_pin_id", (None, generated_image["id"])),
        ],
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["image_url"] == generated_image["image_url"]


@pytest.mark.asyncio
async def test_generate_image_rejects_blank_prompt(client: AsyncClient):
    headers = await _register_and_login(client, "ai_blank_user", "ai_blank@example.com")

    response = await client.post(
        "/api/v2/ai/generate-image",
        json={"prompt": "   "},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_image_rejects_multiple_images(client: AsyncClient):
    headers = await _register_and_login(client, "ai_multi_user", "ai_multi@example.com")

    response = await client.post(
        "/api/v2/ai/generate-image",
        json={"prompt": "A quiet mountain cabin", "num_images": 2},
        headers=headers,
    )

    assert response.status_code == 422
