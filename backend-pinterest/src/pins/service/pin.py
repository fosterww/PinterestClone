import asyncio
import base64
import hashlib
import io
import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import List

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import AIOperationType, AIProvider, AIStatus
from ai.prompts import build_description_generation_prompt
from ai.tracking import record_ai_operation
from boards.models import (
    GeneratedPinModel,
    PinEditHistoryModel,
    PinEditSource,
    PinModel,
    PinModerationStatus,
    PinProcessingState,
)
from core.exception import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProviderError,
)
from core.infra.gemini import GeminiService
from core.infra.s3 import S3Service
from pins.repository.pin import PinRepository
from pins.schemas import CreatedAt, PinCreate, PinUpdate, Popularity
from pins.task import index_image_task, tag_pin_image_task
from tags.service import TagService
from users.models import UserModel


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
        self, pin_id: uuid.UUID, current_user_id: uuid.UUID | None = None
    ) -> PinModel | None:
        pin = await self.repo.get_pin_by_id(pin_id)
        if pin is None:
            raise NotFoundError("Pin not found")
        if pin.owner_id != current_user_id and not self.repo.is_trusted(pin):
            raise NotFoundError("Pin not found")

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
            if generated_pin.moderation_status != PinModerationStatus.APPROVED:
                raise BadRequestError("Generated image is not approved for publishing")
            original_content = await self.s3_service.download_bytes_from_url(
                generated_pin.image_url
            )
            self._validate_image_bytes(original_content)
            image_url = generated_pin.image_url
        else:
            original_content = await self._read_uploaded_image(image)
            image_url = await self.s3_service.upload_image_to_s3(image)

        base64_thumb = self._build_base64_thumbnail(original_content)
        image_metadata = self._extract_image_metadata(original_content)
        await self.repo.lock_pin_file_hash(image_metadata["file_hash_sha256"])
        duplicate_pin = await self.repo.get_first_pin_by_hash(
            image_metadata["file_hash_sha256"]
        )

        if data.tags:
            data.tags = [t.strip() for t in data.tags if t.strip()]
        if data.description is not None and not data.description.strip():
            data.description = None

        has_manual_tags = bool(data.tags)
        if has_manual_tags and data.generate_ai_description and not data.description:
            description_prompt = build_description_generation_prompt(
                data.title, original_content
            )
            started_at = perf_counter()
            data.description = await asyncio.to_thread(
                self.gemini_service.generate_description,
                original_content,
                data.title,
            )
            if data.description is None:
                description_error = "Failed to generate description"
            else:
                description_error = None
            await record_ai_operation(
                self.db,
                provider=AIProvider.GEMINI,
                model=self._gemini_model_name(),
                operation_type=AIOperationType.DESCRIPTION_GENERATION,
                prompt_version=description_prompt.version,
                input_parameters=description_prompt.input_parameters,
                status=AIStatus.COMPLETED if data.description else AIStatus.FAILED,
                latency_ms=self._elapsed_ms(started_at),
                error_message=description_error,
                user_id=owner.id,
            )
            if data.description is None:
                raise ProviderError(description_error)
        try:
            tags = await self.tag_service.get_or_create_tag(data.tags or [])
            pin_metadata = {
                **image_metadata,
                "processing_state": (
                    PinProcessingState.TAGGED
                    if has_manual_tags
                    else PinProcessingState.UPLOADED
                ),
                "moderation_status": (
                    PinModerationStatus.HIDDEN
                    if duplicate_pin is not None
                    else PinModerationStatus.PENDING
                ),
                "tagged_at": datetime.now(timezone.utc) if has_manual_tags else None,
                "is_duplicate": duplicate_pin is not None,
                "duplicate_of_pin_id": duplicate_pin.id if duplicate_pin else None,
            }
            pin = await self.repo.create_pin(owner, data, image_url, tags, pin_metadata)
            await self.repo.add_pin_edit_history(
                pin.id,
                actor_user_id=owner.id,
                source=PinEditSource.USER,
                changed_fields=[
                    "title",
                    "description",
                    "link_url",
                    "image_url",
                    "tags",
                    "image_metadata",
                    "processing_state",
                    "moderation_status",
                ],
                after={
                    "title": pin.title,
                    "description": pin.description,
                    "link_url": pin.link_url,
                    "image_url": pin.image_url,
                    "tags": [tag.name for tag in tags],
                    "image_width": pin.image_width,
                    "image_height": pin.image_height,
                    "dominant_colors": pin.dominant_colors,
                    "is_duplicate": pin.is_duplicate,
                    "duplicate_of_pin_id": str(pin.duplicate_of_pin_id)
                    if pin.duplicate_of_pin_id
                    else None,
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                },
                reason="pin_created",
            )
            if generated_pin is not None:
                await self.db.delete(generated_pin)
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to create pin")
        if not pin.is_duplicate:
            if has_manual_tags:
                index_image_task.delay(str(pin.id), base64_thumb)
            else:
                tag_pin_image_task.delay(
                    str(pin.id), base64_thumb, data.generate_ai_description
                )
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

    def _extract_image_metadata(self, image_bytes: bytes) -> dict:
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.size
            dominant_colors = []
            try:
                image = img.convert("RGB")
                colors_image = image.copy()
                colors_image.thumbnail((100, 100))
                colors = colors_image.quantize(colors=5).convert("RGB").getcolors()
            except Exception:
                colors = None
            if isinstance(colors, list):
                sorted_colors = sorted(colors, key=lambda item: item[0], reverse=True)
                dominant_colors = [
                    f"#{red:02x}{green:02x}{blue:02x}"
                    for _, (red, green, blue) in sorted_colors[:5]
                ]
            return {
                "image_width": width,
                "image_height": height,
                "dominant_colors": dominant_colors,
                "file_hash_sha256": hashlib.sha256(image_bytes).hexdigest(),
            }

    def _elapsed_ms(self, started_at: float) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _gemini_model_name(self) -> str:
        return getattr(self.gemini_service, "MODEL", GeminiService.MODEL)

    async def update_pin(
        self, pin: PinModel, data: PinUpdate, current_user: UserModel
    ) -> PinModel:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        update_data = data.model_dump(exclude_unset=True)
        changed_fields = []
        before = {}
        after = {}
        if "tags" in update_data:
            before["tags"] = [tag.name for tag in pin.tags]
            update_data["tags"] = [
                tag.strip() for tag in update_data["tags"] if tag.strip()
            ]
            pin.tags = await self.tag_service.get_or_create_tag(update_data["tags"])
            after["tags"] = [tag.name for tag in pin.tags]
            changed_fields.append("tags")
            del update_data["tags"]
        if (
            update_data.get("description") is not None
            and not update_data["description"].strip()
        ):
            update_data["description"] = None
        before.update(
            {field: getattr(pin, field) for field in update_data if hasattr(pin, field)}
        )
        try:
            updated_pin = await self.repo.update_pin(pin, update_data)
            after.update(
                {
                    field: getattr(updated_pin, field)
                    for field in update_data
                    if hasattr(updated_pin, field)
                }
            )
            changed_fields.extend(update_data.keys())
            if changed_fields:
                await self.repo.add_pin_edit_history(
                    pin.id,
                    actor_user_id=current_user.id,
                    source=PinEditSource.USER,
                    changed_fields=changed_fields,
                    before=before,
                    after=after,
                    reason="pin_updated",
                )
            await self.db.commit()
            return updated_pin
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to update pin")

    async def retry_pin_processing(
        self, pin: PinModel, current_user: UserModel
    ) -> PinModel:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        if pin.processing_state != PinProcessingState.FAILED:
            raise BadRequestError("Only failed pins can be retried")
        if pin.is_duplicate:
            raise BadRequestError("Duplicate pins cannot be indexed")

        try:
            image_bytes = await self.s3_service.download_bytes_from_url(pin.image_url)
            base64_thumb = self._build_base64_thumbnail(image_bytes)
            before = {
                "processing_state": pin.processing_state.value,
                "moderation_status": pin.moderation_status.value,
                "last_processing_error": pin.last_processing_error,
            }
            retry_tagging = pin.tagged_at is None
            pin.processing_state = (
                PinProcessingState.UPLOADED
                if retry_tagging
                else PinProcessingState.TAGGED
            )
            pin.moderation_status = PinModerationStatus.PENDING
            pin.last_processing_error = None
            await self.repo.add_pin_edit_history(
                pin.id,
                actor_user_id=current_user.id,
                source=PinEditSource.USER,
                changed_fields=[
                    "processing_state",
                    "moderation_status",
                    "last_processing_error",
                ],
                before=before,
                after={
                    "processing_state": pin.processing_state.value,
                    "moderation_status": pin.moderation_status.value,
                    "last_processing_error": pin.last_processing_error,
                },
                reason="pin_processing_retry_requested",
            )
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to retry pin processing")

        if pin.tagged_at is None:
            tag_pin_image_task.delay(str(pin.id), base64_thumb, False)
        else:
            index_image_task.delay(str(pin.id), base64_thumb)
        return pin

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

    async def get_pin_history(
        self, pin_id: uuid.UUID, user: UserModel
    ) -> List[PinEditHistoryModel]:
        try:
            pin = await self.repo.get_pin_by_id(pin_id)
            if not pin:
                raise NotFoundError(detail="Pin not found")
            if pin.owner_id != user.id:
                raise ForbiddenError(detail="Not the pin owner")
            pin_history = await self.repo.get_history(pin_id)
            return pin_history
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to get pin history")

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
