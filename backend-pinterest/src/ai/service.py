import asyncio
import base64
import binascii
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai.schemas import GenerateImageRequest, GenerateImageResponse
from boards.models import GeneratedPinModel
from core.exception import AppError
from core.infra.openai import OpenAIClient
from core.infra.s3 import S3Service
from core.logger import logger
from users.models import UserModel


class AIService:
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
        prompt = self._build_prompt(data)

        response = await asyncio.to_thread(
            self.openai_client.generate_image,
            prompt,
            data.num_images,
        )
        if not response:
            raise AppError(detail="Failed to generate image")

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
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            await self._delete_uploaded_images(generated_images)
            raise
        except Exception as exc:
            await self.db.rollback()
            await self._delete_uploaded_images(generated_images)
            raise AppError(detail="Failed to save generated images") from exc

        return GenerateImageResponse(generated_images=generated_images)

    def _build_prompt(self, data: GenerateImageRequest) -> str:
        prompt = data.prompt
        requirements: list[str] = []
        if data.style:
            requirements.append(f"Style: {data.style}")
        if data.aspect_ratio:
            requirements.append(f"Target aspect ratio: {data.aspect_ratio}")
        if data.negative_prompt:
            requirements.append(f"Avoid: {data.negative_prompt}")
        if data.seed is not None:
            requirements.append(f"Use seed {data.seed} if supported by the model")

        if not requirements:
            return prompt

        formatted_requirements = "\n".join(f"- {item}" for item in requirements)
        return f"{prompt}\n\nAdditional requirements:\n{formatted_requirements}"

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
                raise AppError(detail="Invalid generated image payload") from exc
        if url:
            return await self.s3_service.download_bytes_from_url(url)
        raise AppError(detail="Image generation returned no usable output")

    async def _delete_uploaded_images(self, images: list[GeneratedPinModel]) -> None:
        for image in images:
            try:
                await self.s3_service.delete_bytes_from_s3(image.image_url)
            except Exception:
                logger.exception("Failed to delete generated image after rollback")
