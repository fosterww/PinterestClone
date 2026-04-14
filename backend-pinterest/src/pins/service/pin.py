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
    ConflictError,
    NotFoundError,
    ForbiddenError,
    BadRequestError,
)

from boards.models import PinModel
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
        tags: list[str] = [],
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

    async def create_pin(
        self,
        image: UploadFile,
        owner: UserModel,
        data: PinCreate,
    ) -> PinModel:
        allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if image.content_type not in allowed:
            raise BadRequestError("Unsupported image type")

        try:
            with Image.open(image.file) as img:
                if img.size[0] > 1100 or img.size[1] > 2100:
                    raise BadRequestError("Image dimensions exceed 1100x2100 pixels")
        except UnidentifiedImageError:
            raise BadRequestError("Invalid or corrupted image file")

        await image.seek(0)
        original_content = await image.read()
        await image.seek(0)

        image_url = await self.s3_service.upload_image_to_s3(image)

        with Image.open(io.BytesIO(original_content)) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((500, 500))
            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG")
            base64_thumb = base64.b64encode(thumb_io.getvalue()).decode("utf-8")

        if data.tags:
            data.tags = [t.strip() for t in data.tags if t.strip()]

        if not data.tags:
            data.tags = await asyncio.to_thread(
                self.gemini_service.generate_tags,
                original_content,
                data.title,
                data.description,
            )
        tags = await self.tag_service.get_or_create_tag(data.tags)
        pin = await self.repo.create_pin(owner, data, image_url, tags)
        index_image_task.delay(str(pin.id), base64_thumb)
        return pin

    async def update_pin(
        self, pin: PinModel, data: PinUpdate, current_user: UserModel
    ) -> PinModel:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            pin.tags = await self.tag_service.get_or_create_tag(update_data["tags"])
            del update_data["tags"]
        return await self.repo.update_pin(pin, update_data)

    async def delete_pin(self, pin: PinModel, current_user: UserModel) -> None:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        await self.repo.delete_pin(pin)

    async def like_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        try:
            await self.repo.add_like(pin_id, user_id)
            await self.db.commit()
        except ConflictError:
            await self.db.rollback()
            raise ConflictError("Already liked")
        return await self.repo.get_pin_by_id(pin_id)

    async def unlike_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        try:
            await self.repo.delete_like(pin_id, user_id)
            await self.db.commit()
        except NotFoundError:
            await self.db.rollback()
            raise NotFoundError("Like not found")
        return await self.repo.get_pin_by_id(pin_id)
