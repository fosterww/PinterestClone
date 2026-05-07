import asyncio
import base64
import uuid
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ai.models import AIOperationType, AIProvider, AIStatus
from ai.prompts import build_description_generation_prompt, build_tag_generation_prompt
from ai.tracking import record_ai_operation
from boards.models import (
    PinEditHistoryModel,
    PinEditSource,
    PinModel,
    PinModerationStatus,
    PinProcessingState,
)
from core.exception import ProviderError
from core.infra.celery import celery_app
from core.infra.clarifai import get_clarifai_service
from core.infra.gemini import GeminiService
from database import AsyncSessionLocal
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
            await record_ai_operation(
                db,
                provider=AIProvider.GEMINI,
                model=GeminiService.MODEL,
                operation_type=AIOperationType.TAG_GENERATION,
                status=AIStatus.FAILED,
                error_message=error,
                related_pin_id=pin.id,
                user_id=pin.owner_id,
            )

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
        tag_prompt = build_tag_generation_prompt(
            pin.title, pin.description, image_bytes
        )
        started_at = perf_counter()
        generated_tags = gemini_service.generate_tags(
            image_bytes, pin.title, pin.description
        )
        if generated_tags is None:
            raise ProviderError("Failed to generate tags")
        await record_ai_operation(
            db,
            provider=AIProvider.GEMINI,
            model=GeminiService.MODEL,
            operation_type=AIOperationType.TAG_GENERATION,
            prompt_version=tag_prompt.version,
            input_parameters=tag_prompt.input_parameters,
            status=AIStatus.COMPLETED if generated_tags else AIStatus.FAILED,
            latency_ms=_elapsed_ms(started_at),
            error_message=None if generated_tags else "Empty tags output",
            related_pin_id=pin.id,
            user_id=pin.owner_id,
        )
        tag_service = TagService(db)
        pin.tags = await tag_service.get_or_create_tag(generated_tags)
        if generate_ai_description and not pin.description:
            description_prompt = build_description_generation_prompt(
                pin.title, image_bytes
            )
            started_at = perf_counter()
            generated_description = gemini_service.generate_description(
                image_bytes, pin.title
            )
            if generated_description is None:
                raise ProviderError("Failed to generate description")
            await record_ai_operation(
                db,
                provider=AIProvider.GEMINI,
                model=GeminiService.MODEL,
                operation_type=AIOperationType.DESCRIPTION_GENERATION,
                prompt_version=description_prompt.version,
                input_parameters=description_prompt.input_parameters,
                status=(
                    AIStatus.COMPLETED if generated_description else AIStatus.FAILED
                ),
                latency_ms=_elapsed_ms(started_at),
                error_message=None
                if generated_description
                else "Empty description output",
                related_pin_id=pin.id,
                user_id=pin.owner_id,
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
    pin_id: str,
    error: str | None = None,
    final_failure: bool = False,
    latency_ms: int | None = None,
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
            await record_ai_operation(
                db,
                provider=AIProvider.CLARIFAI,
                model="clarifai-visual-index",
                operation_type=AIOperationType.IMAGE_INDEXING,
                status=AIStatus.FAILED,
                latency_ms=latency_ms,
                error_message=error,
                related_pin_id=pin.id,
                user_id=pin.owner_id,
            )

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


async def _record_indexing_success(pin_id: str, latency_ms: int | None = None) -> None:
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
        await record_ai_operation(
            db,
            provider=AIProvider.CLARIFAI,
            model="clarifai-visual-index",
            operation_type=AIOperationType.IMAGE_INDEXING,
            status=AIStatus.COMPLETED,
            latency_ms=latency_ms,
            related_pin_id=pin.id,
            user_id=pin.owner_id,
        )
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
    started_at = perf_counter()
    try:
        asyncio.run(_index_image(pin_id, image_bytes))
    except Exception as exc:
        final_failure = self.request.retries >= MAX_INDEX_RETRIES
        asyncio.run(
            _record_indexing_attempt(
                pin_id, str(exc), final_failure, _elapsed_ms(started_at)
            )
        )
        if final_failure:
            raise
        raise self.retry(exc=exc, countdown=2**self.request.retries)
    asyncio.run(_record_indexing_success(pin_id, _elapsed_ms(started_at)))


async def _delete_image(pin_id: str) -> None:
    clarifai_service = await get_clarifai_service()
    try:
        await clarifai_service.delete_image(pin_id)
    finally:
        await clarifai_service.close()


@celery_app.task(name="delete_image_task", queue="default")
def delete_image_task(pin_id: str) -> None:
    asyncio.run(_delete_image(pin_id))


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
