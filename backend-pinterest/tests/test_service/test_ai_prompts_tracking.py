import pytest
from sqlalchemy import select

from ai.models import AIOperationModel, AIOperationType, AIProvider, AIStatus
from ai.prompts import (
    build_description_generation_prompt,
    build_image_generation_prompt,
    build_tag_generation_prompt,
)
from ai.schemas import GenerateImageRequest
from ai.service import OpenAIService
from ai.tracking import record_ai_operation
from core.exception import AITimeoutError, InvalidAIOutputError, ProviderError, RateLimitError
from users.models import UserModel


ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUA"
    "AV7zKjoAAAAASUVORK5CYII="
)


def test_build_image_generation_prompt_includes_version_and_inputs():
    data = GenerateImageRequest(
        prompt="A clean product photo of a red chair",
        style="studio lighting",
        negative_prompt="blur",
        aspect_ratio="1:1",
        seed=42,
    )

    prompt = build_image_generation_prompt(data)

    assert prompt.name == "image_generation"
    assert prompt.version == "image_generation_v1"
    assert "A clean product photo of a red chair" in prompt.content
    assert "Style: studio lighting" in prompt.content
    assert "Avoid: blur" in prompt.content
    assert prompt.input_parameters["seed"] == 42


def test_build_gemini_prompts_are_versioned_without_storing_image_bytes():
    image_bytes = b"fake-image"

    tag_prompt = build_tag_generation_prompt("Cozy room", None, image_bytes)
    description_prompt = build_description_generation_prompt("Cozy room", image_bytes)

    assert tag_prompt.name == "tag_generation"
    assert tag_prompt.version == "tag_generation_v1"
    assert tag_prompt.input_parameters == {
        "title": "Cozy room",
        "description": None,
        "image_bytes_length": len(image_bytes),
    }
    assert description_prompt.name == "description_generation"
    assert description_prompt.version == "description_generation_v1"
    assert description_prompt.input_parameters == {
        "title": "Cozy room",
        "image_bytes_length": len(image_bytes),
    }


@pytest.mark.asyncio
async def test_record_ai_operation_persists_structured_metadata(db_session):
    operation = await record_ai_operation(
        db_session,
        provider=AIProvider.OPENAI,
        model="dall-e-3",
        operation_type=AIOperationType.IMAGE_GENERATION,
        prompt_version="image_generation_v1",
        input_parameters={"prompt": "test"},
        status=AIStatus.FAILED,
        latency_ms=123,
        error_message="x" * 1200,
    )
    await db_session.commit()

    saved = await db_session.get(AIOperationModel, operation.id)

    assert saved is not None
    assert saved.provider == AIProvider.OPENAI
    assert saved.operation_type == AIOperationType.IMAGE_GENERATION
    assert saved.prompt_version == "image_generation_v1"
    assert saved.input_parameters == {"prompt": "test"}
    assert saved.status == AIStatus.FAILED
    assert saved.latency_ms == 123
    assert saved.error_message == "x" * 1000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "status_code", "detail"),
    [
        (ProviderError("OpenAI unavailable"), 502, "OpenAI unavailable"),
        (AITimeoutError("OpenAI timed out"), 504, "OpenAI timed out"),
        (RateLimitError("OpenAI quota exceeded"), 429, "OpenAI quota exceeded"),
    ],
)
async def test_generate_image_provider_failures_are_recorded(
    db_session, exc, status_code, detail
):
    user = await _create_user(db_session)
    service = OpenAIService(
        _FakeS3Service(),
        _FakeOpenAIClient(exc=exc),
        db_session,
    )

    with pytest.raises(type(exc)) as excinfo:
        await service.generate_image(GenerateImageRequest(prompt="test image"), user)

    operation = await db_session.scalar(select(AIOperationModel))
    assert excinfo.value.status_code == status_code
    assert excinfo.value.detail == detail
    assert operation is not None
    assert operation.provider == AIProvider.OPENAI
    assert operation.operation_type == AIOperationType.IMAGE_GENERATION
    assert operation.status == AIStatus.FAILED
    assert operation.error_message == f"{status_code}: {detail}"
    assert operation.user_id == user.id


@pytest.mark.asyncio
async def test_generate_image_invalid_output_cleans_up_and_records_failure(db_session):
    user = await _create_user(db_session)
    s3_service = _FakeS3Service()
    service = OpenAIService(
        s3_service,
        _FakeOpenAIClient(
            response=[
                {"b64_json": ONE_PIXEL_PNG},
                {"b64_json": "not-base64"},
            ]
        ),
        db_session,
    )
    request = GenerateImageRequest.model_construct(
        prompt="test image",
        negative_prompt=None,
        style=None,
        aspect_ratio="1:1",
        seed=None,
        num_images=2,
    )

    with pytest.raises(InvalidAIOutputError) as excinfo:
        await service.generate_image(request, user)

    operation = await db_session.scalar(select(AIOperationModel))
    assert excinfo.value.status_code == 502
    assert excinfo.value.detail == "Invalid generated image payload"
    assert s3_service.deleted_urls == ["http://mock-s3-url.com/generated/1.png"]
    assert operation is not None
    assert operation.status == AIStatus.FAILED
    assert operation.error_message == "502: Invalid generated image payload"
    assert operation.user_id == user.id


@pytest.mark.asyncio
async def test_generate_image_passes_aspect_ratio_to_openai_client(db_session):
    user = await _create_user(db_session)
    openai_client = _FakeOpenAIClient(response=[{"b64_json": ONE_PIXEL_PNG}])
    service = OpenAIService(
        _FakeS3Service(),
        openai_client,
        db_session,
    )

    await service.generate_image(
        GenerateImageRequest(prompt="test image", aspect_ratio="16:9"),
        user,
    )

    assert openai_client.last_aspect_ratio == "16:9"


async def _create_user(db_session) -> UserModel:
    user = UserModel(
        username="ai_failure_user",
        email="ai_failure_user@example.com",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    return user


class _FakeOpenAIClient:
    IMAGE_MODEL = "fake-openai"

    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response
        self.exc = exc
        self.last_aspect_ratio: str | None = None

    def generate_image(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: str | None = "1:1",
    ):
        self.last_aspect_ratio = aspect_ratio
        if self.exc is not None:
            raise self.exc
        return self.response


class _FakeS3Service:
    def __init__(self):
        self.uploaded_count = 0
        self.deleted_urls: list[str] = []

    async def upload_bytes_to_s3(
        self,
        content: bytes,
        content_type: str = "image/png",
        folder: str = "generated",
        extension: str = "png",
    ):
        self.uploaded_count += 1
        return f"http://mock-s3-url.com/{folder}/{self.uploaded_count}.{extension}"

    async def download_bytes_from_url(self, url: str):
        return b"image"

    async def delete_bytes_from_s3(self, url: str):
        self.deleted_urls.append(url)
