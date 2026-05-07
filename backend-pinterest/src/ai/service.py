import asyncio
import base64
import binascii
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import AIOperationType, AIProvider, AIStatus
from ai.prompts import BuiltPrompt, build_image_generation_prompt
from ai.schemas import GenerateImageRequest, GenerateImageResponse
from ai.tracking import record_ai_operation
from boards.models import GeneratedPinModel
from core.exception import (
    AITimeoutError,
    AppError,
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
    ) -> None:
        self.db = db
        self.s3_service = s3_service
        self.openai_client = openai_client

    async def generate_image(
        self, data: GenerateImageRequest, user: UserModel
    ) -> GenerateImageResponse:
        prompt = build_image_generation_prompt(data)
        started_at = perf_counter()

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
        )

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
