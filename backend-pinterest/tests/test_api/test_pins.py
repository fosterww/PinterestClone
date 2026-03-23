import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import io

@pytest.fixture
def fake_image():
    return b"fake_image_content"

@pytest.mark.asyncio
async def test_pin_crud_flow(client: AsyncClient, fake_image: bytes, mock_celery_tasks):
    mock_index_task, mock_delete_task = mock_celery_tasks
    await client.post("/api/v1/auth/register", json={
        "username": "pin_tester",
        "email": "pin_tester@example.com",
        "password": "password"
    })
    login_response = await client.post("/api/v1/auth/login", data={
        "username": "pin_tester", "password": "password"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.core.s3.S3Service.upload_image_to_s3", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = "http://fake-s3-url.com/image.jpg"

        response = await client.post(
            "/api/v1/pins/",
            data={"title": "My Test Pin", "description": "Desc", "link_url": "http://pinterest.com"},
            files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
            headers=headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Test Pin"
        assert data["image_url"] == "http://fake-s3-url.com/image.jpg"
        assert data["tags"] == []
        pin_id = data["id"]
        mock_index_task.assert_called_once()
        args, _ = mock_index_task.call_args
        assert args[0] == pin_id

    response = await client.get("/api/v1/pins/")
    assert response.status_code == 200
    assert len(response.json()) > 0

    response = await client.get(f"/api/v1/pins/{pin_id}")
    assert response.status_code == 200
    assert response.json()["id"] == pin_id

    response = await client.patch(
        f"/api/v1/pins/{pin_id}",
        json={"title": "Updated Title"},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

    response = await client.delete(f"/api/v1/pins/{pin_id}", headers=headers)
    assert response.status_code == 204
    mock_delete_task.assert_called_once_with(pin_id)

    response = await client.get(f"/api/v1/pins/{pin_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Pin not found"


@pytest.mark.asyncio
async def test_pin_create_with_tags(client: AsyncClient, fake_image: bytes):
    await client.post("/api/v1/auth/register", json={
        "username": "pin_tag_tester",
        "email": "pin_tag_tester@example.com",
        "password": "password"
    })
    login_response = await client.post("/api/v1/auth/login", data={
        "username": "pin_tag_tester", "password": "password"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.core.s3.S3Service.upload_image_to_s3", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = "http://fake-s3-url.com/image.jpg"

        response = await client.post(
            "/api/v1/pins/",
            data={"title": "Tagged Pin", "tags": ["nature", "travel"]},
            files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
            headers=headers
        )

        assert response.status_code == 201
        data = response.json()
        returned_tag_names = {t["name"] for t in data["tags"]}
        assert "nature" in returned_tag_names
        assert "travel" in returned_tag_names


@pytest.mark.asyncio
async def test_get_related_pins(client: AsyncClient, fake_image: bytes):
    await client.post("/api/v1/auth/register", json={
        "username": "pin_related_tester",
        "email": "pin_related@example.com",
        "password": "password"
    })
    login_response = await client.post("/api/v1/auth/login", data={
        "username": "pin_related_tester", "password": "password"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("src.core.s3.S3Service.upload_image_to_s3", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = "http://fake-s3.com/img.jpg"
        p1 = await client.post("/api/v1/pins/", data={"title": "Pin 1", "tags": ["art", "cool"]}, files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")}, headers=headers)
        p2 = await client.post("/api/v1/pins/", data={"title": "Pin 2", "tags": ["art"]}, files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")}, headers=headers)
        p3 = await client.post("/api/v1/pins/", data={"title": "Pin 3", "tags": ["cool"]}, files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")}, headers=headers)

        p1_id = p1.json()["id"]
        p2_id = p2.json()["id"]
        p3_id = p3.json()["id"]

    with patch("src.core.clarifai.ClarifaiService.search_similar_images_by_id", new_callable=AsyncMock) as mock_clarifai, \
         patch("src.core.cache.CacheService.get_pattern", new_callable=AsyncMock) as mock_cache_get, \
         patch("src.core.cache.CacheService.set", new_callable=AsyncMock):
        mock_clarifai.return_value = [p3_id]
        mock_cache_get.return_value = None

        response = await client.get(f"/api/v1/pins/{p1_id}/related")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        related_ids = {p["id"] for p in data}
        assert p2_id in related_ids
        assert p3_id in related_ids
