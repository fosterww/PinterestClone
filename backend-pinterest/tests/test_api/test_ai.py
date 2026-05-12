from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import (
    AIOperationModel,
    AIOperationType,
    AIProvider,
    AIStatus,
    AIUsageRecordModel,
)


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
async def test_generate_image_and_create_pin_from_generated_asset(
    client: AsyncClient, db_session: AsyncSession
):
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
    operation_id = generate_response.json()["operation_id"]
    quota = generate_response.json()["quota"]
    assert generated_image["image_url"].startswith("http://mock-s3-url.com/generated/")
    assert quota["operation_type"] == "image_generation"
    assert quota["limit"] == 5
    assert quota["used"] == 1
    assert quota["remaining"] == 4
    operation = await db_session.scalar(
        select(AIOperationModel).where(AIOperationModel.id == UUID(operation_id))
    )
    assert operation is not None
    assert operation.provider == AIProvider.OPENAI
    assert operation.operation_type == AIOperationType.IMAGE_GENERATION
    assert operation.prompt_version == "image_generation_v1"
    assert operation.status == AIStatus.COMPLETED
    assert operation.model == "dall-e-3"
    assert operation.generated_pin_id == UUID(generated_image["id"])
    assert operation.input_parameters["prompt"] == (
        "A cozy modern reading corner with warm sunlight"
    )
    usage = await db_session.scalar(
        select(AIUsageRecordModel).where(
            AIUsageRecordModel.operation_id == operation.id
        )
    )
    assert usage is not None
    assert usage.action_type == AIOperationType.IMAGE_GENERATION
    assert usage.units_used == 1

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
async def test_get_ai_operation_returns_status_latency_error_and_output_id(
    client: AsyncClient,
):
    headers = await _register_and_login(client, "ai_ops_user", "ai_ops@example.com")

    generate_response = await client.post(
        "/api/v2/ai/generate-image",
        json={"prompt": "A clean studio product photo of a ceramic lamp"},
        headers=headers,
    )
    assert generate_response.status_code == 200, generate_response.text
    generated_image = generate_response.json()["generated_images"][0]
    operation_id = generate_response.json()["operation_id"]

    response = await client.get(
        f"/api/v2/ai/operations/{operation_id}", headers=headers
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == operation_id
    assert data["status"] == "completed"
    assert data["error"] is None
    assert isinstance(data["latency_ms"], int)
    assert data["output_id"] == generated_image["id"]


@pytest.mark.asyncio
async def test_get_ai_operation_is_scoped_to_current_user(client: AsyncClient):
    owner_headers = await _register_and_login(
        client, "ai_ops_owner", "ai_ops_owner@example.com"
    )
    other_headers = await _register_and_login(
        client, "ai_ops_other", "ai_ops_other@example.com"
    )
    generate_response = await client.post(
        "/api/v2/ai/generate-image",
        json={"prompt": "A small walnut desk organizer"},
        headers=owner_headers,
    )
    assert generate_response.status_code == 200, generate_response.text
    operation_id = generate_response.json()["operation_id"]

    response = await client.get(
        f"/api/v2/ai/operations/{operation_id}", headers=other_headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "AI operation not found"


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


@pytest.mark.asyncio
async def test_generate_image_returns_quota_error_after_daily_limit(
    client: AsyncClient,
):
    headers = await _register_and_login(client, "ai_quota_user", "ai_quota@example.com")

    for _ in range(5):
        response = await client.post(
            "/api/v2/ai/generate-image",
            json={"prompt": "A quiet mountain cabin"},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    response = await client.post(
        "/api/v2/ai/generate-image",
        json={"prompt": "A quiet mountain cabin"},
        headers=headers,
    )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["message"] == "AI quota exceeded"
    assert detail["quota"]["operation_type"] == "image_generation"
    assert detail["quota"]["limit"] == 5
    assert detail["quota"]["remaining"] == 0
