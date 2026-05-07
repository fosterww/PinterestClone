import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boards.models import BoardModel, PinModel, PinModerationStatus, PinProcessingState


@pytest.fixture
def fake_image():
    return b"fake_image_content"


async def _trust_pin(db_session: AsyncSession, pin_id: str) -> None:
    result = await db_session.execute(
        select(PinModel).where(PinModel.id == uuid.UUID(pin_id))
    )
    pin = result.scalar_one()
    pin.processing_state = PinProcessingState.INDEXED
    pin.moderation_status = PinModerationStatus.APPROVED
    pin.is_duplicate = False
    pin.duplicate_of_pin_id = None
    await db_session.flush()


@pytest.mark.asyncio
async def test_boards_flow(
    client: AsyncClient, fake_image: bytes, db_session: AsyncSession
):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "board_tester",
            "email": "board_tester@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "board_tester", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v2/boards/",
        json={"title": "My Travel Docs", "description": "Visits and more"},
        headers=headers,
    )
    assert response.status_code == 201

    result = await db_session.execute(
        select(BoardModel).filter_by(title="My Travel Docs")
    )
    board = result.scalars().first()
    assert board is not None
    board_id = board.id

    pin_response = await client.post(
        "/api/v2/pins/",
        data={"title": "Paris"},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    assert pin_response.status_code == 201
    pin_id = pin_response.json()["id"]

    response = await client.post(
        f"/api/v2/boards/{board_id}/pins/{pin_id}", headers=headers
    )
    assert response.status_code == 201
    await _trust_pin(db_session, pin_id)

    db_session.expire_all()

    response = await client.get(f"/api/v2/boards/{board_id}")
    assert response.status_code == 200

    data = response.json()
    assert "pins" in data
    assert any(p["id"] == pin_id for p in data["pins"])

    response = await client.get("/api/v2/boards/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) > 0

    response = await client.patch(
        f"/api/v2/boards/{board_id}",
        json={"title": "Europe Trip"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Europe Trip"

    response = await client.delete(
        f"/api/v2/boards/{board_id}/pins/{pin_id}", headers=headers
    )
    assert response.status_code == 204

    db_session.expire_all()

    response = await client.get(f"/api/v2/boards/{board_id}")
    data = response.json()
    assert all(p["id"] != pin_id for p in data["pins"])


@pytest.mark.asyncio
async def test_public_board_hides_pending_pins(
    client: AsyncClient, fake_image: bytes, db_session: AsyncSession
):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "board_pending_owner",
            "email": "board_pending_owner@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "board_pending_owner", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    board_response = await client.post(
        "/api/v2/boards/",
        json={"title": "Pending Pins"},
        headers=headers,
    )
    board_id = board_response.json()["id"]
    pin_response = await client.post(
        "/api/v2/pins/",
        data={"title": "Pending Board Pin"},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    pin_id = pin_response.json()["id"]
    await client.post(f"/api/v2/boards/{board_id}/pins/{pin_id}", headers=headers)

    db_session.expire_all()
    anonymous_response = await client.get(f"/api/v2/boards/{board_id}")
    owner_response = await client.get(f"/api/v2/boards/{board_id}", headers=headers)

    assert pin_id not in {pin["id"] for pin in anonymous_response.json()["pins"]}
    assert pin_id in {pin["id"] for pin in owner_response.json()["pins"]}


@pytest.mark.asyncio
async def test_secret_board_requires_owner(client: AsyncClient):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "secret_owner",
            "email": "secret_owner@example.com",
            "password": "password",
        },
    )
    owner_login = await client.post(
        "/api/v2/auth/login",
        data={"username": "secret_owner", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

    create_response = await client.post(
        "/api/v2/boards/",
        json={"title": "Hidden Board", "visibility": "secret"},
        headers=owner_headers,
    )
    board_id = create_response.json()["id"]

    anonymous_response = await client.get(f"/api/v2/boards/{board_id}")
    assert anonymous_response.status_code == 403

    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "other_user",
            "email": "other_user@example.com",
            "password": "password",
        },
    )
    other_login = await client.post(
        "/api/v2/auth/login",
        data={"username": "other_user", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    other_response = await client.get(
        f"/api/v2/boards/{board_id}", headers=other_headers
    )
    assert other_response.status_code == 403

    owner_response = await client.get(
        f"/api/v2/boards/{board_id}", headers=owner_headers
    )
    assert owner_response.status_code == 200


@pytest.mark.asyncio
async def test_add_same_pin_to_board_twice_returns_conflict(
    client: AsyncClient, fake_image: bytes, db_session: AsyncSession
):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "dup_board_user",
            "email": "dup_board_user@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "dup_board_user", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = await client.post(
        "/api/v2/boards/",
        json={"title": "Duplicates"},
        headers=headers,
    )
    assert response.status_code == 201

    result = await db_session.execute(select(BoardModel).filter_by(title="Duplicates"))
    board = result.scalars().first()
    assert board is not None

    pin_response = await client.post(
        "/api/v2/pins/",
        data={"title": "Rome"},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    assert pin_response.status_code == 201
    pin_id = pin_response.json()["id"]

    first_add = await client.post(
        f"/api/v2/boards/{board.id}/pins/{pin_id}", headers=headers
    )
    assert first_add.status_code == 201

    second_add = await client.post(
        f"/api/v2/boards/{board.id}/pins/{pin_id}", headers=headers
    )
    assert second_add.status_code == 409
