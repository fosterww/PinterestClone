import uuid
import base64
import io
import asyncio
from typing import List

from PIL import Image, UnidentifiedImageError

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.infra.s3 import S3Service
from core.infra.gemini import GeminiService
from core.exception import (
    AppError,
    ConflictError,
    NotFoundError,
    ForbiddenError,
    BadRequestError,
)

from boards.models import GeneratedPinModel, PinModel
from users.models import UserModel
from pins.schemas import (
    PinCreate,
    PinUpdate,
    CreatedAt,
    Popularity,
)
from tags.service import TagService
from pins.repository.pin import PinRepository
from pins.task import index_image_task


class PinService:
    def __init__(
        self,
        db: AsyncSession,
        repo: PinRepository,
        tag_service: TagService,
        s3_service: S3Service,
        gemini_service: GeminiService,
    ) -> None:
        self.db = db
        self.repo = repo
        self.tag_service = tag_service
        self.s3_service = s3_service
        self.gemini_service = gemini_service

    async def get_pin_by_id(self, pin_id: uuid.UUID) -> PinModel | None:
        result = await self.repo.get_pin_by_id(pin_id)
        if result is None:
            raise NotFoundError("Pin not found")
        return result

    async def get_pins(
        self,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
        created_at: CreatedAt | None = None,
        popularity: Popularity | None = None,
    ) -> List[PinModel]:
        return await self.repo.get_pins(
            offset=offset,
            limit=limit,
            search=search,
            tags=tags,
            created_at=created_at,
            popularity=popularity,
        )

    async def get_pins_by_ids(self, pin_ids: list[str]) -> List[PinModel]:
        return await self.repo.get_pins_by_ids(pin_ids)

    async def get_pin_by_id_and_increment_views(
        self, pin_id: uuid.UUID
    ) -> PinModel | None:
        result = await self.repo.get_pin_by_id_and_increment_views(pin_id)
        if result is None:
            raise NotFoundError("Pin not found")
        return result

    async def create_pin(
        self,
        image: UploadFile | None,
        owner: UserModel,
        data: PinCreate,
    ) -> PinModel:
        if image is not None and data.generated_pin_id is not None:
            raise BadRequestError("Provide either image or generated_pin_id, not both")
        if image is None and data.generated_pin_id is None:
            raise BadRequestError("Either image or generated_pin_id is required")

        generated_pin: GeneratedPinModel | None = None
        if data.generated_pin_id is not None:
            generated_pin = await self.repo._get_generated_pin(
                data.generated_pin_id, owner.id
            )
            original_content = await self.s3_service.download_bytes_from_url(
                generated_pin.image_url
            )
            self._validate_image_bytes(original_content)
            image_url = generated_pin.image_url
        else:
            original_content = await self._read_uploaded_image(image)
            image_url = await self.s3_service.upload_image_to_s3(image)

        base64_thumb = self._build_base64_thumbnail(original_content)

        if data.tags:
            data.tags = [t.strip() for t in data.tags if t.strip()]
        if data.description is not None and not data.description.strip():
            data.description = None

        if not data.tags:
            data.tags = await asyncio.to_thread(
                self.gemini_service.generate_tags,
                original_content,
                data.title,
                data.description,
            )
        if data.generate_ai_description and not data.description:
            data.description = await asyncio.to_thread(
                self.gemini_service.generate_description,
                original_content,
                data.title,
            )
        try:
            tags = await self.tag_service.get_or_create_tag(data.tags)
            pin = await self.repo.create_pin(owner, data, image_url, tags)
            if generated_pin is not None:
                await self.db.delete(generated_pin)
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to create pin")
        index_image_task.delay(str(pin.id), base64_thumb)
        return pin

    async def _read_uploaded_image(self, image: UploadFile | None) -> bytes:
        if image is None:
            raise BadRequestError("Image is required")

        allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if image.content_type not in allowed:
            raise BadRequestError("Unsupported image type")

        await image.seek(0)
        content = await image.read()
        await image.seek(0)
        self._validate_image_bytes(content)
        return content

    def _validate_image_bytes(self, image_bytes: bytes) -> None:
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                if img.size[0] > 1100 or img.size[1] > 2100:
                    raise BadRequestError("Image dimensions exceed 1100x2100 pixels")
        except UnidentifiedImageError:
            raise BadRequestError("Invalid or corrupted image file")

    def _build_base64_thumbnail(self, image_bytes: bytes) -> str:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((500, 500))
            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG")
            return base64.b64encode(thumb_io.getvalue()).decode("utf-8")

    async def update_pin(
        self, pin: PinModel, data: PinUpdate, current_user: UserModel
    ) -> PinModel:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            pin.tags = await self.tag_service.get_or_create_tag(update_data["tags"])
            del update_data["tags"]
        try:
            updated_pin = await self.repo.update_pin(pin, update_data)
            await self.db.commit()
            return updated_pin
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to update pin")

    async def delete_pin(self, pin: PinModel, current_user: UserModel) -> None:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        try:
            await self.repo.delete_pin(pin)
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to delete pin")

    async def like_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        try:
            await self.repo.add_like(pin_id, user_id)
            await self.db.commit()
        except ConflictError:
            await self.db.rollback()
            raise ConflictError("Already liked")
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to like pin")
        return await self.repo.get_pin_by_id(pin_id)

    async def unlike_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        try:
            await self.repo.delete_like(pin_id, user_id)
            await self.db.commit()
        except NotFoundError:
            await self.db.rollback()
            raise NotFoundError("Like not found")
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to unlike pin")
        return await self.repo.get_pin_by_id(pin_id)
