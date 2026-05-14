import uuid
from ai.schemas import AIOperationOutput
from core.exception import NotFoundError
from ai.repository import AIRepository
import asyncio
import base64
import binascii
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import AIUsageRecordModel, AIOperationType, AIProvider, AIStatus
from ai.prompts import BuiltPrompt, build_image_generation_prompt
from ai.quota import QuotaService, operation_unit_cost, quota_metadata_to_dict
from ai.safety import validate_image_prompt
from ai.schemas import GenerateImageRequest, GenerateImageResponse
from ai.tracking import record_ai_operation
from boards.models import GeneratedPinModel, PinModerationStatus
from core.exception import (
    AITimeoutError,
    AppError,
    BadRequestError,
    InvalidAIOutputError,
    ProviderError,
    RateLimitError,
)
from core.infra.openai import OpenAIClient
from core.infra.s3 import S3Service
from core.logger import logger
from users.models import UserModel


class OpenAIService:
    def __init__(
        self,
        s3_service: S3Service,
        openai_client: OpenAIClient,
        db: AsyncSession,
        quota_service: QuotaService,
        ai_repository: AIRepository,
    ) -> None:
        self.db = db
        self.s3_service = s3_service
        self.openai_client = openai_client
        self.quota_service = quota_service
        self.ai_repository = ai_repository

    async def generate_image(
        self, data: GenerateImageRequest, user: UserModel
    ) -> GenerateImageResponse:
        prompt = build_image_generation_prompt(data)
        started_at = perf_counter()
        try:
            validate_image_prompt(data.prompt)
        except BadRequestError as exc:
            await self._record_failed_operation(prompt, started_at, user, exc)
            raise

        quota = await self.quota_service.check_and_reserve(
            user.id, AIOperationType.IMAGE_GENERATION
        )

        if not isinstance(prompt.content, str):
            raise ProviderError("Invalid prompt format")

        try:
            response = await asyncio.to_thread(
                self.openai_client.generate_image,
                prompt.content,
                data.num_images,
                data.aspect_ratio,
            )
            if not response:
                raise InvalidAIOutputError("Image generation returned empty output")
        except (
            InvalidAIOutputError,
            ProviderError,
            AITimeoutError,
            RateLimitError,
        ) as exc:
            await self._record_failed_operation(prompt, started_at, user, exc)
            raise
        except Exception as exc:
            await self._record_failed_operation(prompt, started_at, user, exc)
            raise ProviderError() from exc

        generated_images: list[GeneratedPinModel] = []
        try:
            for item in response:
                content = await self._extract_image_bytes(item)
                image_url = await self.s3_service.upload_bytes_to_s3(
                    content,
                    content_type="image/png",
                    folder="generated",
                    extension="png",
                )
                generated_pin = GeneratedPinModel(
                    user_id=user.id,
                    image_url=image_url,
                    prompt=data.prompt,
                    style=data.style,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                    moderation_status=PinModerationStatus.APPROVED,
                )
                self.db.add(generated_pin)
                generated_images.append(generated_pin)
            await self.db.flush()
            operation = await record_ai_operation(
                self.db,
                provider=AIProvider.OPENAI,
                model=self._model_name(),
                operation_type=AIOperationType.IMAGE_GENERATION,
                prompt_version=prompt.version,
                input_parameters=prompt.input_parameters,
                status=AIStatus.COMPLETED,
                latency_ms=self._elapsed_ms(started_at),
                user_id=user.id,
                generated_pin_id=generated_images[0].id if generated_images else None,
            )
            self._record_usage(
                user_id=user.id,
                operation_id=operation.id,
                operation_type=AIOperationType.IMAGE_GENERATION,
                units_used=data.num_images,
            )
            await self.db.commit()
        except AppError as exc:
            await self.db.rollback()
            await self._delete_uploaded_images(generated_images)
            await self._record_failed_operation(prompt, started_at, user, exc)
            raise
        except Exception as exc:
            await self.db.rollback()
            await self._delete_uploaded_images(generated_images)
            await self._record_failed_operation(prompt, started_at, user, exc)
            raise AppError(detail="Failed to save generated images") from exc

        return GenerateImageResponse(
            generated_images=generated_images,
            operation_id=operation.id,
            quota=quota_metadata_to_dict(quota),
        )

    async def get_operation_by_id(
        self,
        operation_id: uuid.UUID,
        user: UserModel,
    ) -> AIOperationOutput:
        operation = await AIRepository(self.db).get_operation_by_id(operation_id, user)
        if operation is None:
            raise NotFoundError("AI operation not found")
        return AIOperationOutput.from_operation(operation)

    async def _extract_image_bytes(self, item: Any) -> bytes:
        if isinstance(item, dict):
            url = item.get("url")
            b64_json = item.get("b64_json")
        else:
            url = getattr(item, "url", None)
            b64_json = getattr(item, "b64_json", None)

        if b64_json:
            try:
                return base64.b64decode(b64_json)
            except (ValueError, binascii.Error) as exc:
                raise InvalidAIOutputError("Invalid generated image payload") from exc
        if url:
            return await self.s3_service.download_bytes_from_url(url)
        raise InvalidAIOutputError("Image generation returned no usable output")

    async def _delete_uploaded_images(self, images: list[GeneratedPinModel]) -> None:
        for image in images:
            try:
                await self.s3_service.delete_bytes_from_s3(image.image_url)
            except Exception:
                logger.exception("Failed to delete generated image after rollback")

    async def _record_failed_operation(
        self,
        prompt: BuiltPrompt,
        started_at: float,
        user: UserModel,
        exc: Exception,
    ) -> None:
        try:
            await record_ai_operation(
                self.db,
                provider=AIProvider.OPENAI,
                model=self._model_name(),
                operation_type=AIOperationType.IMAGE_GENERATION,
                prompt_version=prompt.version,
                input_parameters=prompt.input_parameters,
                status=AIStatus.FAILED,
                latency_ms=self._elapsed_ms(started_at),
                error_message=str(exc),
                user_id=user.id,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to record AI operation failure")

    def _elapsed_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _model_name(self) -> str:
        return getattr(self.openai_client, "IMAGE_MODEL", "dall-e-3")

    def _record_usage(
        self,
        user_id,
        operation_id,
        operation_type: AIOperationType,
        units_used: int,
    ) -> None:
        self.db.add(
            AIUsageRecordModel(
                user_id=user_id,
                operation_id=operation_id,
                action_type=operation_type,
                units_used=units_used,
                cost_usd=operation_unit_cost(operation_type) * units_used,
            )
        )
