import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import io

@pytest.fixture
def fake_image():
    return b"fake_image_content"

@pytest.mark.asyncio
async def test_pin_crud_flow(client: AsyncClient, fake_image: bytes):
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

    with patch("src.pins.router.upload_image_to_s3", new_callable=AsyncMock) as mock_s3:
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
        pin_id = data["id"]

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

    response = await client.get(f"/api/v1/pins/{pin_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == "Pin not found"
