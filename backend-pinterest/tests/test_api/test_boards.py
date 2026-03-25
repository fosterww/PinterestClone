import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import io

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.boards.models import BoardModel


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

    with patch(
        "src.core.s3.S3Service.upload_image_to_s3", new_callable=AsyncMock
    ) as mock_s3:
        mock_s3.return_value = "http://fake.com/image.jpg"
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
