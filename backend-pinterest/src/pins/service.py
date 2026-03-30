import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.core.cache import CacheService
from src.core.exception import ConflictError, NotFoundError, ForbiddenError
from src.boards.models import PinModel
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate, PinResponse
from src.tags.service import TagService
from src.pins.repository import PinRepository
from src.pins.schemas import CreatedAt, Popularity


class PinService:
    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService,
        repo: PinRepository,
        tag_service: TagService,
    ) -> None:
        self.db = db
        self.cache = cache
        self.repo = repo
        self.tag_service = tag_service

    async def _get_from_cache(self, pin_id: uuid.UUID):
        try:
            data = await self.cache.get_pattern(f"related_pins:{pin_id}:*")
            if data:
                return [PinResponse.model_validate_json(p) for p in data if p]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def _set_to_cache(self, pin_id: uuid.UUID, pins: list[PinModel]):
        try:
            for i, pin in enumerate(pins):
                pin_json = PinResponse.model_validate(pin).model_dump_json()
                await self.cache.set(f"related_pins:{pin_id}:{i}", pin_json, 600)
        except Exception as e:
            logger.error(f"Cache write error: {e}")

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
    ) -> List[PinResponse]:
        return await self.repo.get_pins(
            offset=offset,
            limit=limit,
            search=search,
            tags=tags,
            created_at=created_at,
            popularity=popularity,
        )

    async def get_pins_by_ids(self, pin_ids: list[str]) -> List[PinResponse]:
        return await self.repo.get_pins_by_ids(pin_ids)

    async def create_pin(
        self, owner: UserModel, data: PinCreate, image_url: str
    ) -> PinResponse:
        try:
            tags = await self.tag_service.get_or_create_tag(data.tags)
            return await self.repo.create_pin(owner, data, image_url, tags)
        except ConflictError:
            await self.db.rollback()
            logger.error(f"Pin conflicts with existing data: {owner.id}")
            raise ConflictError()

    async def update_pin(
        self, pin: PinModel, data: PinUpdate, current_user: UserModel
    ) -> PinResponse:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        try:
            update_data = data.model_dump(exclude_unset=True)
            if "tags" in update_data:
                pin.tags = await self.tag_service.get_or_create_tag(update_data["tags"])
                del update_data["tags"]
            return await self.repo.update_pin(pin, update_data)
        except ConflictError:
            logger.error(f"Error while updating pin: {pin.id}")
            raise ConflictError("Cannot update pin — it is still referenced")

    async def delete_pin(self, pin: PinModel, current_user: UserModel) -> None:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        try:
            await self.repo.delete_pin(pin)
        except ConflictError:
            logger.error(f"Error while deleting pin: {pin.id}")
            raise ConflictError("Cannot delete pin — it is still referenced")

    async def get_related_pins(
        self, pin_id: uuid.UUID, limit: int = 20
    ) -> List[PinResponse]:
        cached_pins = await self._get_from_cache(pin_id)
        if cached_pins:
            return cached_pins
        base_pin = await self.repo.get_pin_by_id(pin_id)
        if not base_pin or not base_pin.tags:
            return []

        tag_ids = [tag.id for tag in base_pin.tags]
        related_pins = await self.repo.get_related_by_tags(pin_id, tag_ids, limit)

        if related_pins:
            await self._set_to_cache(pin_id, related_pins)

        return [PinResponse.model_validate(pin) for pin in related_pins]

    async def like_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinResponse:
        like = await self.repo.get_like(pin_id, user_id)
        pin = await self.repo.get_pin_by_id(pin_id)
        if like:
            raise ConflictError("Like already exists")
        await self.repo.add_like(pin_id, user_id)
        if hasattr(pin, "likes_count"):
            pin.likes_count += 1
            await self.db.flush()
        return PinResponse.model_validate(pin)

    async def unlike_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinResponse:
        like = await self.repo.get_like(pin_id, user_id)
        pin = await self.repo.get_pin_by_id(pin_id)
        if not like:
            raise NotFoundError("Like not found")
        await self.repo.delete_like(like)
        if hasattr(pin, "likes_count") and pin.likes_count > 0:
            pin.likes_count -= 1
            await self.db.flush()
        return PinResponse.model_validate(pin)
