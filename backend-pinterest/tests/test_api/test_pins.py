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
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "pin_tester",
            "email": "pin_tester@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "pin_tester", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v2/pins/",
        data={
            "title": "My Test Pin",
            "description": "Desc",
            "link_url": "http://pinterest.com",
        },
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Test Pin"
    assert data["image_url"] == "http://mock-s3-url.com/image.jpg"
    assert data["tags"] == []
    pin_id = data["id"]
    mock_index_task.assert_called_once()
    args, _ = mock_index_task.call_args
    assert args[0] == pin_id

    response = await client.get("/api/v2/pins/")
    assert response.status_code == 200
    assert len(response.json()) > 0

    response = await client.get(f"/api/v2/pins/{pin_id}")
    assert response.status_code == 200
    assert response.json()["id"] == pin_id

    response = await client.patch(
        f"/api/v2/pins/{pin_id}", json={"title": "Updated Title"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"

    response = await client.delete(f"/api/v2/pins/{pin_id}", headers=headers)
    assert response.status_code == 204
    mock_delete_task.assert_called_once_with(pin_id)

    response = await client.get(f"/api/v2/pins/{pin_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Pin not found"


@pytest.mark.asyncio
async def test_pin_create_with_tags(client: AsyncClient, fake_image: bytes):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "pin_tag_tester",
            "email": "pin_tag_tester@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "pin_tag_tester", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Unified with conftest.py's mock_s3_service
    response = await client.post(
        "/api/v2/pins/",
        data={"title": "Tagged Pin", "tags": ["nature", "travel"]},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    returned_tag_names = {t["name"] for t in data["tags"]}
    assert "nature" in returned_tag_names
    assert "travel" in returned_tag_names


@pytest.mark.asyncio
async def test_get_related_pins(client: AsyncClient, fake_image: bytes):
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": "pin_related_tester",
            "email": "pin_related@example.com",
            "password": "password",
        },
    )
    login_response = await client.post(
        "/api/v2/auth/login",
        data={"username": "pin_related_tester", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    p1 = await client.post(
        "/api/v2/pins/",
        data={"title": "Pin 1", "tags": ["art", "cool"]},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    p2 = await client.post(
        "/api/v2/pins/",
        data={"title": "Pin 2", "tags": ["art"]},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    p3 = await client.post(
        "/api/v2/pins/",
        data={"title": "Pin 3", "tags": ["cool"]},
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )

    p1_id = p1.json()["id"]
    p2_id = p2.json()["id"]
    p3_id = p3.json()["id"]

    with (
        patch(
            "src.core.infra.clarifai.ClarifaiService.search_similar_images_by_id",
            new_callable=AsyncMock,
        ) as mock_clarifai,
        patch(
            "src.core.infra.cache.CacheService.get_pattern", new_callable=AsyncMock
        ) as mock_cache_get,
        patch("src.core.infra.cache.CacheService.set", new_callable=AsyncMock),
    ):
        mock_clarifai.return_value = [p3_id]
        mock_cache_get.return_value = None

        response = await client.get(f"/api/v2/pins/{p1_id}/related")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        related_ids = {p["id"] for p in data}
        assert p2_id in related_ids
        assert p3_id in related_ids


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
        data["tags"] = tags
    response = await client.post(
        "/api/v2/pins/",
        data=data,
        files={"image": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_api_like_pin_success(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(client, "like_api_user", "like_api@example.com")
    pin = await _create_pin(client, headers, "Like Test Pin", fake_image=fake_image)

    response = await client.post(f"/api/v2/pins/{pin['id']}/like", headers=headers)
    assert response.status_code == 200
    assert response.json()["likes_count"] == 1


@pytest.mark.asyncio
async def test_api_like_pin_duplicate_returns_409(
    client: AsyncClient, fake_image: bytes
):
    headers = await _register_and_login(client, "like_dup_user", "like_dup@example.com")
    pin = await _create_pin(client, headers, "Dup Like Pin", fake_image=fake_image)

    await client.post(f"/api/v2/pins/{pin['id']}/like", headers=headers)
    response = await client.post(f"/api/v2/pins/{pin['id']}/like", headers=headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_api_unlike_pin_success(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(
        client, "unlike_api_user", "unlike_api@example.com"
    )
    pin = await _create_pin(client, headers, "Unlike Test Pin", fake_image=fake_image)

    await client.post(f"/api/v2/pins/{pin['id']}/like", headers=headers)
    response = await client.post(f"/api/v2/pins/{pin['id']}/unlike", headers=headers)
    assert response.status_code == 200
    assert response.json()["likes_count"] == 0


@pytest.mark.asyncio
async def test_api_unlike_pin_not_liked_returns_404(
    client: AsyncClient, fake_image: bytes
):
    headers = await _register_and_login(
        client, "unlike_nf_user", "unlike_nf@example.com"
    )
    pin = await _create_pin(client, headers, "No Like Pin", fake_image=fake_image)

    response = await client.post(f"/api/v2/pins/{pin['id']}/unlike", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_like_requires_auth(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(
        client, "like_auth_user", "like_auth@example.com"
    )
    pin = await _create_pin(client, headers, "Auth Required Pin", fake_image=fake_image)

    response = await client.post(f"/api/v2/pins/{pin['id']}/like")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_search_pins_by_title(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(
        client, "search_user", "search_user@example.com"
    )
    await _create_pin(client, headers, "Aurora Borealis", fake_image=fake_image)
    await _create_pin(client, headers, "Desert Sand", fake_image=fake_image)
    await _create_pin(client, headers, "Aurora Valley", fake_image=fake_image)

    response = await client.get("/api/v2/pins/?search=Aurora")
    assert response.status_code == 200
    titles = {p["title"] for p in response.json()}
    assert "Aurora Borealis" in titles
    assert "Aurora Valley" in titles
    assert "Desert Sand" not in titles


@pytest.mark.asyncio
async def test_api_filter_pins_by_tag(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(
        client, "tag_filter_user", "tag_filter@example.com"
    )
    await _create_pin(
        client, headers, "Forest Walk", tags=["forest"], fake_image=fake_image
    )
    await _create_pin(
        client, headers, "City Lights", tags=["city"], fake_image=fake_image
    )
    await _create_pin(
        client,
        headers,
        "Forest City Blend",
        tags=["forest", "city"],
        fake_image=fake_image,
    )

    response = await client.get("/api/v2/pins/?tags=forest")
    assert response.status_code == 200
    titles = {p["title"] for p in response.json()}
    assert "Forest Walk" in titles
    assert "Forest City Blend" in titles
    assert "City Lights" not in titles


@pytest.mark.asyncio
async def test_api_filter_pins_by_popularity(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(client, "pop_user", "pop_user@example.com")
    headers2 = await _register_and_login(client, "pop_user2", "pop_user2@example.com")
    low = await _create_pin(client, headers, "Low Pop", fake_image=fake_image)
    high = await _create_pin(client, headers, "High Pop", fake_image=fake_image)

    await client.post(f"/api/v2/pins/{high['id']}/like", headers=headers)
    await client.post(f"/api/v2/pins/{high['id']}/like", headers=headers2)

    response = await client.get("/api/v2/pins/?popularity=most_popular")
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert ids.index(high["id"]) < ids.index(low["id"])


@pytest.mark.asyncio
async def test_api_filter_pins_created_at_newest(
    client: AsyncClient, fake_image: bytes
):
    response = await client.get("/api/v2/pins/?created_at=newest")
    assert response.status_code == 200
    pins = response.json()
    if len(pins) >= 2 and "created_at" in pins[0]:
        from datetime import datetime

        dates = [datetime.fromisoformat(p["created_at"]) for p in pins]
        assert dates[0] >= dates[-1]


@pytest.mark.asyncio
async def test_api_filter_pins_created_at_oldest(
    client: AsyncClient, fake_image: bytes
):
    response = await client.get("/api/v2/pins/?created_at=oldest")
    assert response.status_code == 200
    pins = response.json()
    if len(pins) >= 2 and "created_at" in pins[0]:
        from datetime import datetime

        dates = [datetime.fromisoformat(p["created_at"]) for p in pins]
        assert dates[0] <= dates[-1]


@pytest.mark.asyncio
async def test_api_search_and_tag_combined(client: AsyncClient, fake_image: bytes):
    headers = await _register_and_login(client, "combo_user", "combo_user@example.com")
    await _create_pin(
        client, headers, "River Sunset", tags=["water"], fake_image=fake_image
    )
    await _create_pin(
        client, headers, "River Storm", tags=["storm"], fake_image=fake_image
    )
    await _create_pin(
        client, headers, "Lake Sunset", tags=["water"], fake_image=fake_image
    )

    response = await client.get("/api/v2/pins/?search=River&tags=water")
    assert response.status_code == 200
    titles = {p["title"] for p in response.json()}
    assert titles == {"River Sunset"}
