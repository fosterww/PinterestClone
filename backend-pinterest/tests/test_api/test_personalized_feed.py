import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boards.models import PinModel, PinModerationStatus, PinProcessingState
from users.repository import UserRepository


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


async def _trust_pin_ids(db_session: AsyncSession, *pin_ids: str) -> None:
    ids = [uuid.UUID(pin_id) for pin_id in pin_ids]
    result = await db_session.execute(select(PinModel).where(PinModel.id.in_(ids)))
    for pin in result.scalars().all():
        pin.processing_state = PinProcessingState.INDEXED
        pin.moderation_status = PinModerationStatus.APPROVED
        pin.is_duplicate = False
        pin.duplicate_of_pin_id = None
    await db_session.flush()


@pytest.mark.asyncio
async def test_api_personalized_feed(
    client: AsyncClient, db_session: AsyncSession, fake_image: bytes
):
    headers = await _register_and_login(client, "personal_user", "personal@example.com")

    pin1 = await _create_pin(
        client, headers, "Mountain", tags=["nature"], fake_image=fake_image
    )
    pin2 = await _create_pin(
        client, headers, "City", tags=["urban"], fake_image=fake_image
    )
    pin3 = await _create_pin(
        client, headers, "Forest", tags=["nature"], fake_image=fake_image
    )
    await _trust_pin_ids(db_session, pin1["id"], pin2["id"], pin3["id"])

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


@pytest.mark.asyncio
async def test_api_personalized_feed_prefers_followed_users(
    client: AsyncClient, fake_image: bytes, db_session: AsyncSession
):
    follower_headers = await _register_and_login(
        client, "feed_follower", "feed_follower@example.com"
    )
    followed_headers = await _register_and_login(
        client, "feed_followed", "feed_followed@example.com"
    )

    follower_user = await UserRepository(db_session).get_user_by_username(
        "feed_follower"
    )
    await UserRepository(db_session).follow_user(follower_user.id, "feed_followed")

    pin1 = await _create_pin(
        client,
        followed_headers,
        "Followed New",
        tags=["travel"],
        fake_image=fake_image,
    )
    pin2 = await _create_pin(
        client,
        followed_headers,
        "Followed Old",
        tags=["travel"],
        fake_image=fake_image,
    )
    own_pin = await _create_pin(
        client,
        follower_headers,
        "Own Nature",
        tags=["nature"],
        fake_image=fake_image,
    )
    pin4 = await _create_pin(
        client,
        follower_headers,
        "Another Own",
        tags=["nature"],
        fake_image=fake_image,
    )
    await _trust_pin_ids(db_session, pin1["id"], pin2["id"], own_pin["id"], pin4["id"])

    response = await client.get(
        f"/api/v2/pins/{own_pin['id']}", headers=follower_headers
    )
    assert response.status_code == 200

    response = await client.get("/api/v2/pins/personalized", headers=follower_headers)
    assert response.status_code == 200

    titles = [pin["title"] for pin in response.json()]
    assert set(titles[:2]) == {"Followed New", "Followed Old"}
    assert "Own Nature" in titles


@pytest.mark.asyncio
async def test_api_personalized_feed_backfills_with_latest_global_pins(
    client: AsyncClient, fake_image: bytes, db_session: AsyncSession
):
    follower_headers = await _register_and_login(
        client, "global_follower", "global_follower@example.com"
    )
    followed_headers = await _register_and_login(
        client, "global_followed", "global_followed@example.com"
    )
    global_headers = await _register_and_login(
        client, "global_source", "global_source@example.com"
    )

    follower_user = await UserRepository(db_session).get_user_by_username(
        "global_follower"
    )
    await UserRepository(db_session).follow_user(follower_user.id, "global_followed")

    pin1 = await _create_pin(
        client,
        followed_headers,
        "Only Followed Pin",
        tags=["travel"],
        fake_image=fake_image,
    )
    pin2 = await _create_pin(
        client,
        global_headers,
        "Newest Global Pin",
        tags=["design"],
        fake_image=fake_image,
    )
    await _trust_pin_ids(db_session, pin1["id"], pin2["id"])

    response = await client.get("/api/v2/pins/personalized", headers=follower_headers)
    assert response.status_code == 200

    titles = [pin["title"] for pin in response.json()]
    assert titles[0] == "Only Followed Pin"
    assert "Newest Global Pin" in titles
