import pytest
from httpx import AsyncClient
import io

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from boards.models import BoardModel


@pytest.fixture
def fake_image():
    return b"fake_image_content"


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
