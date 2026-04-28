import asyncio
import base64
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.infra.celery import celery_app
from core.infra.clarifai import get_clarifai_service
from core.infra.gemini import GeminiService
from database import AsyncSessionLocal
from boards.models import (
    PinEditHistoryModel,
    PinEditSource,
    PinModel,
    PinModerationStatus,
    PinProcessingState,
)
from tags.service import TagService


MAX_TAG_RETRIES = 3
MAX_INDEX_RETRIES = 3


async def _index_image(pin_id: str, image_bytes: bytes) -> None:
    clarifai_service = await get_clarifai_service()
    try:
        await clarifai_service.index_image_bytes(pin_id, image_bytes)
    finally:
        await clarifai_service.close()


async def _record_tagging_attempt(
    pin_id: str, error: str | None = None, final_failure: bool = False
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == uuid.UUID(pin_id))
            .options(selectinload(PinModel.tags))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            return

        before = {
            "processing_state": pin.processing_state.value,
            "moderation_status": pin.moderation_status.value,
            "tagging_attempts": pin.tagging_attempts,
            "last_processing_error": pin.last_processing_error,
        }
        pin.tagging_attempts += 1
        pin.last_processing_error = error
        if final_failure:
            pin.processing_state = PinProcessingState.FAILED
            pin.moderation_status = PinModerationStatus.FAILED

        db.add(
            PinEditHistoryModel(
                pin_id=pin.id,
                source=PinEditSource.SYSTEM,
                changed_fields=[
                    "tagging_attempts",
                    "last_processing_error",
                    "processing_state",
                    "moderation_status",
                ],
                before=before,
                after={
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                    "tagging_attempts": pin.tagging_attempts,
                    "last_processing_error": pin.last_processing_error,
                },
                reason="pin_tagging_failed" if final_failure else "pin_tagging_retry",
            )
        )
        await db.commit()


async def _tag_pin_image(
    pin_id: str, image_bytes: bytes, generate_ai_description: bool
) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == uuid.UUID(pin_id))
            .options(selectinload(PinModel.tags))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            return False

        before = {
            "processing_state": pin.processing_state.value,
            "moderation_status": pin.moderation_status.value,
            "tagged_at": pin.tagged_at.isoformat() if pin.tagged_at else None,
            "description": pin.description,
            "last_processing_error": pin.last_processing_error,
            "tags": [tag.name for tag in pin.tags],
        }

        gemini_service = GeminiService()
        generated_tags = gemini_service.generate_tags(
            image_bytes, pin.title, pin.description
        )
        tag_service = TagService(db)
        pin.tags = await tag_service.get_or_create_tag(generated_tags)
        if generate_ai_description and not pin.description:
            generated_description = gemini_service.generate_description(
                image_bytes, pin.title
            )
            if generated_description:
                pin.description = generated_description

        pin.processing_state = PinProcessingState.TAGGED
        pin.tagged_at = datetime.now(timezone.utc)
        pin.last_processing_error = None

        db.add(
            PinEditHistoryModel(
                pin_id=pin.id,
                source=PinEditSource.SYSTEM,
                changed_fields=[
                    "tags",
                    "description",
                    "processing_state",
                    "tagged_at",
                    "last_processing_error",
                ],
                before=before,
                after={
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                    "tagged_at": pin.tagged_at.isoformat(),
                    "description": pin.description,
                    "last_processing_error": pin.last_processing_error,
                    "tags": [tag.name for tag in pin.tags],
                },
                reason="pin_tagged",
            )
        )
        await db.commit()
        return True


@celery_app.task(bind=True, name="tag_pin_image_task", queue="default")
def tag_pin_image_task(
    self, pin_id: str, base64_image: str, generate_ai_description: bool = False
) -> None:
    image_bytes = base64.b64decode(base64_image)
    try:
        tagged = asyncio.run(
            _tag_pin_image(pin_id, image_bytes, generate_ai_description)
        )
        if tagged:
            index_image_task.delay(pin_id, base64_image)
    except Exception as exc:
        final_failure = self.request.retries >= MAX_TAG_RETRIES
        asyncio.run(_record_tagging_attempt(pin_id, str(exc), final_failure))
        if final_failure:
            raise
        raise self.retry(exc=exc, countdown=2**self.request.retries)


async def _record_indexing_attempt(
    pin_id: str, error: str | None = None, final_failure: bool = False
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PinModel).where(PinModel.id == uuid.UUID(pin_id))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            return

        before = {
            "processing_state": pin.processing_state.value,
            "moderation_status": pin.moderation_status.value,
            "indexing_attempts": pin.indexing_attempts,
            "last_processing_error": pin.last_processing_error,
        }
        pin.indexing_attempts += 1
        pin.last_processing_error = error
        if final_failure:
            pin.processing_state = PinProcessingState.FAILED
            pin.moderation_status = PinModerationStatus.FAILED

        db.add(
            PinEditHistoryModel(
                pin_id=pin.id,
                source=PinEditSource.SYSTEM,
                changed_fields=[
                    "indexing_attempts",
                    "last_processing_error",
                    "processing_state",
                    "moderation_status",
                ],
                before=before,
                after={
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                    "indexing_attempts": pin.indexing_attempts,
                    "last_processing_error": pin.last_processing_error,
                },
                reason="pin_indexing_failed" if final_failure else "pin_indexing_retry",
            )
        )
        await db.commit()


async def _record_indexing_success(pin_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PinModel).where(PinModel.id == uuid.UUID(pin_id))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            return

        before = {
            "processing_state": pin.processing_state.value,
            "moderation_status": pin.moderation_status.value,
            "indexed_at": pin.indexed_at.isoformat() if pin.indexed_at else None,
            "last_processing_error": pin.last_processing_error,
        }
        pin.processing_state = PinProcessingState.INDEXED
        pin.moderation_status = (
            PinModerationStatus.HIDDEN
            if pin.is_duplicate
            else PinModerationStatus.APPROVED
        )
        pin.indexed_at = datetime.now(timezone.utc)
        pin.last_processing_error = None
        db.add(
            PinEditHistoryModel(
                pin_id=pin.id,
                source=PinEditSource.SYSTEM,
                changed_fields=[
                    "processing_state",
                    "moderation_status",
                    "indexed_at",
                    "last_processing_error",
                ],
                before=before,
                after={
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                    "indexed_at": pin.indexed_at.isoformat(),
                    "last_processing_error": pin.last_processing_error,
                },
                reason="pin_indexed",
            )
        )
        await db.commit()


@celery_app.task(bind=True, name="index_image_task", queue="default")
def index_image_task(self, pin_id: str, base64_image: str) -> None:
    image_bytes = base64.b64decode(base64_image)
    try:
        asyncio.run(_index_image(pin_id, image_bytes))
    except Exception as exc:
        final_failure = self.request.retries >= MAX_INDEX_RETRIES
        asyncio.run(_record_indexing_attempt(pin_id, str(exc), final_failure))
        if final_failure:
            raise
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    asyncio.run(_record_indexing_success(pin_id))


async def _delete_image(pin_id: str) -> None:
    clarifai_service = await get_clarifai_service()
    try:
        await clarifai_service.delete_image(pin_id)
    finally:
        await clarifai_service.close()


@celery_app.task(name="delete_image_task", queue="default")
def delete_image_task(pin_id: str) -> None:
    asyncio.run(_delete_image(pin_id))
