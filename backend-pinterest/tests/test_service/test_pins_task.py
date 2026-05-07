import base64
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from ai.models import AIOperationModel, AIOperationType, AIProvider, AIStatus
from boards.models import PinModel, PinModerationStatus, PinProcessingState
from pins import task as pins_task
from users.models import UserModel


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_tag_pin_image_task_does_not_enqueue_index_when_pin_is_missing(monkeypatch):
    async def fake_tag_pin_image(pin_id, image_bytes, generate_ai_description):
        return False

    index_delay = Mock()
    monkeypatch.setattr(pins_task, "_tag_pin_image", fake_tag_pin_image)
    monkeypatch.setattr(pins_task.index_image_task, "delay", index_delay)

    pins_task.tag_pin_image_task.run(
        "missing-pin-id", base64.b64encode(b"image").decode("utf-8"), False
    )

    index_delay.assert_not_called()


@pytest.mark.asyncio
async def test_tag_pin_image_records_gemini_operations(db_session, monkeypatch):
    user = UserModel(
        username="ai-task-user",
        email="ai-task-user@example.com",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    pin = PinModel(
        owner_id=user.id,
        title="Sunny kitchen",
        image_url="http://example.com/kitchen.jpg",
        processing_state=PinProcessingState.UPLOADED,
        moderation_status=PinModerationStatus.PENDING,
    )
    db_session.add(pin)
    await db_session.commit()

    class FakeGeminiService:
        MODEL = "fake-gemini"

        def generate_tags(self, image_bytes, title, description):
            return ["kitchen", "sunlight"]

        def generate_description(self, image_bytes, title):
            return "A bright kitchen with sunlight."

    monkeypatch.setattr(
        pins_task, "AsyncSessionLocal", lambda: SessionContext(db_session)
    )
    monkeypatch.setattr(pins_task, "GeminiService", FakeGeminiService)

    tagged = await pins_task._tag_pin_image(str(pin.id), b"image-bytes", True)

    operations = (
        (
            await db_session.execute(
                select(AIOperationModel).order_by(AIOperationModel.operation_type)
            )
        )
        .scalars()
        .all()
    )
    operation_types = {operation.operation_type for operation in operations}

    assert tagged is True
    assert operation_types == {
        AIOperationType.DESCRIPTION_GENERATION,
        AIOperationType.TAG_GENERATION,
    }
    assert all(operation.provider == AIProvider.GEMINI for operation in operations)
    assert all(operation.model == "fake-gemini" for operation in operations)
    assert all(operation.status == AIStatus.COMPLETED for operation in operations)
    assert all(operation.related_pin_id == pin.id for operation in operations)
    assert all(operation.user_id == user.id for operation in operations)


@pytest.mark.asyncio
async def test_record_indexing_success_records_clarifai_operation(
    db_session, monkeypatch
):
    user = UserModel(
        username="ai-index-user",
        email="ai-index-user@example.com",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    pin = PinModel(
        owner_id=user.id,
        title="Indexed pin",
        image_url="http://example.com/indexed.jpg",
        processing_state=PinProcessingState.TAGGED,
        moderation_status=PinModerationStatus.PENDING,
    )
    db_session.add(pin)
    await db_session.commit()

    monkeypatch.setattr(
        pins_task, "AsyncSessionLocal", lambda: SessionContext(db_session)
    )

    await pins_task._record_indexing_success(str(pin.id), latency_ms=321)

    operation = await db_session.scalar(select(AIOperationModel))

    assert operation is not None
    assert operation.provider == AIProvider.CLARIFAI
    assert operation.model == "clarifai-visual-index"
    assert operation.operation_type == AIOperationType.IMAGE_INDEXING
    assert operation.status == AIStatus.COMPLETED
    assert operation.latency_ms == 321
    assert operation.related_pin_id == pin.id
    assert operation.user_id == user.id
