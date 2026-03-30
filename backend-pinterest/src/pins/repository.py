import uuid
from typing import List
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exception import AppError, ConflictError
from src.core.logger import logger
from src.boards.models import PinModel, PinLikeModel, TagModel, pin_tag_association
from src.users.models import UserModel
from src.pins.schemas import (
    CreatedAt,
    Popularity,
    PinCreate,
    PinResponse,
    PinLikeResponse,
)
from sqlalchemy import func


class PinRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pin(
        self, owner: UserModel, data: PinCreate, image_url: str, tags: list[TagModel]
    ) -> PinResponse:
        try:
            create_data = data.model_dump(exclude_unset=True)
            if "tags" in create_data:
                del create_data["tags"]
            pin = PinModel(
                owner_id=owner.id,
                **create_data,
                image_url=image_url,
                tags=tags,
            )
            self.db.add(pin)
            await self.db.flush()
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin.id)
                .options(selectinload(PinModel.tags))
            )
            return PinResponse.model_validate(result.scalar_one())
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while creating pin: {owner.id}")
            raise AppError()

    async def get_pins(
        self,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        tags: list[str] = [],
        created_at: CreatedAt | None = None,
        popularity: Popularity | None = None,
    ) -> list[PinResponse]:
        try:
            query = select(PinModel).options(selectinload(PinModel.tags))

            if search:
                query = query.where(PinModel.title.icontains(search))

            if tags:
                query = query.where(PinModel.tags.any(TagModel.name.in_(tags)))

            if created_at == CreatedAt.newest:
                query = query.order_by(PinModel.created_at.desc())
            elif created_at == CreatedAt.oldest:
                query = query.order_by(PinModel.created_at.asc())

            if popularity == Popularity.most_popular:
                query = query.order_by(PinModel.likes_count.desc())
            elif popularity == Popularity.least_popular:
                query = query.order_by(PinModel.likes_count.asc())

            result = await self.db.execute(query.offset(offset).limit(limit))
            return [PinResponse.model_validate(pin) for pin in result.scalars().all()]
        except SQLAlchemyError:
            logger.error(f"Database error while fetching pins: {offset}, {limit}")
            raise AppError()

    async def get_pin_by_id(self, pin_id: uuid.UUID) -> PinModel | None:
        try:
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin_id)
                .options(selectinload(PinModel.tags))
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching pin: {pin_id}")
            raise AppError()

    async def get_pins_by_ids(self, pin_ids: list[str]) -> list[PinResponse]:
        try:
            uuids = []
            for pid in pin_ids:
                try:
                    uuids.append(uuid.UUID(pid))
                except ValueError:
                    continue
            if not uuids:
                return []
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id.in_(uuids))
                .options(selectinload(PinModel.tags))
            )
            return [PinResponse.model_validate(pin) for pin in result.scalars().all()]
        except SQLAlchemyError:
            logger.error(f"Database error while fetching pins by IDs: {pin_ids}")
            raise AppError()

    async def get_user_pins(self, username: str) -> List[PinResponse]:
        try:
            result = await self.db.execute(
                select(PinModel)
                .join(UserModel)
                .where(UserModel.username == username)
                .options(selectinload(PinModel.tags))
                .order_by(PinModel.created_at.desc())
            )
            return [PinResponse.model_validate(pin) for pin in result.scalars().all()]
        except SQLAlchemyError:
            logger.error(f"Database error while fetching user pins: {username}")
            raise AppError()

    async def get_like(
        self, pin_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinLikeModel | None:
        try:
            result = await self.db.execute(
                select(PinLikeModel)
                .where(PinLikeModel.pin_id == pin_id)
                .where(PinLikeModel.user_id == user_id)
                .options(
                    selectinload(PinLikeModel.user),
                    selectinload(PinLikeModel.pin).selectinload(PinModel.tags),
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching pin like: {pin_id}, {user_id}")
            raise AppError()

    async def add_like(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinLikeResponse:
        try:
            like = PinLikeModel(pin_id=pin_id, user_id=user_id)
            self.db.add(like)
            await self.db.flush()
            result = await self.db.execute(
                select(PinLikeModel)
                .where(PinLikeModel.pin_id == pin_id)
                .where(PinLikeModel.user_id == user_id)
                .options(
                    selectinload(PinLikeModel.user),
                    selectinload(PinLikeModel.pin).selectinload(PinModel.tags),
                )
            )
            return PinLikeResponse.model_validate(result.scalar_one())
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while adding pin like: {pin_id}, {user_id}")
            raise AppError()

    async def delete_like(self, pin_like: PinLikeModel) -> None:
        try:
            await self.db.delete(pin_like)
            await self.db.flush()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while deleting pin like: {pin_like.pin_id}, {pin_like.user_id}"
            )
            raise AppError()

    async def update_pin(self, pin: PinModel, data: dict) -> PinResponse:
        for field, value in data.items():
            setattr(pin, field, value)
        try:
            await self.db.flush()
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin.id)
                .options(selectinload(PinModel.tags))
            )
            return PinResponse.model_validate(result.scalar_one())
        except IntegrityError:
            await self.db.rollback()
            logger.error(f"Database error while updating pin: {pin.id}")
            raise ConflictError("Cannot update pin — it is still referenced")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while updating pin: {pin.id}")
            raise AppError()

    async def delete_pin(self, pin: PinModel) -> None:
        try:
            await self.db.delete(pin)
            await self.db.flush()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while deleting pin: {pin.id}")
            raise AppError()

    async def get_related_by_tags(
        self, exclude_pin_id: uuid.UUID, tag_ids: list[uuid.UUID], limit: int
    ) -> list[PinResponse]:
        try:
            query = (
                select(PinModel)
                .join(pin_tag_association)
                .where(pin_tag_association.c.tag_id.in_(tag_ids))
                .where(PinModel.id != exclude_pin_id)
                .group_by(PinModel.id)
                .order_by(
                    func.count(pin_tag_association.c.tag_id).desc(),
                    PinModel.created_at.desc(),
                )
                .options(selectinload(PinModel.tags))
                .limit(limit)
            )
            result = await self.db.execute(query)
            return [PinResponse.model_validate(pin) for pin in result.scalars().all()]
        except SQLAlchemyError:
            logger.error(
                f"Database error while fetching related pins: {exclude_pin_id}, {tag_ids}, {limit}"
            )
            raise AppError()
