import uuid
from typing import List
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exception import AppError, BadRequestError, ConflictError, NotFoundError
from core.logger import logger
from boards.models import (
    GeneratedPinModel,
    PinModel,
    PinLikeModel,
    TagModel,
)
from users.models import UserModel
from pins.schemas import (
    CreatedAt,
    Popularity,
    PinCreate,
)


class PinRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pin(
        self, owner: UserModel, data: PinCreate, image_url: str, tags: list[TagModel]
    ) -> PinModel:
        try:
            create_data = data.model_dump(exclude_unset=True)
            create_data.pop("tags", None)
            create_data.pop("generate_ai_description", None)
            create_data.pop("generated_pin_id", None)
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
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
            )
            return result.scalar_one()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while creating pin: {owner.id}")
            raise AppError()

    async def get_pins(
        self,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
        created_at: CreatedAt | None = None,
        popularity: Popularity | None = None,
    ) -> List[PinModel]:
        try:
            query = select(PinModel).options(
                selectinload(PinModel.user), selectinload(PinModel.tags)
            )

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
            return result.scalars().all()
        except SQLAlchemyError:
            logger.exception(f"Database error while fetching pins: {offset}, {limit}")
            raise AppError()

    async def get_pin_by_id(self, pin_id: uuid.UUID) -> PinModel | None:
        try:
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin_id)
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(f"Database error while fetching pin: {pin_id}")
            raise AppError()

    async def get_pins_by_ids(self, pin_ids: list[str]) -> List[PinModel]:
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
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.exception(f"Database error while fetching pins by IDs: {pin_ids}")
            raise AppError()

    async def get_pin_by_id_and_increment_views(
        self, pin_id: uuid.UUID
    ) -> PinModel | None:
        try:
            await self.db.execute(
                update(PinModel)
                .where(PinModel.id == pin_id)
                .values(views_count=PinModel.views_count + 1)
            )
            await self.db.flush()
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin_id)
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception(f"Database error while fetching pin: {pin_id}")
            raise AppError()

    async def get_user_pins(self, username: str) -> List[PinModel]:
        try:
            result = await self.db.execute(
                select(PinModel)
                .join(UserModel)
                .where(UserModel.username == username)
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
                .order_by(PinModel.created_at.desc())
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.exception(f"Database error while fetching user pins: {username}")
            raise AppError()

    async def add_like(self, pin_id: uuid.UUID, user_id: uuid.UUID):
        try:
            like = PinLikeModel(pin_id=pin_id, user_id=user_id)
            self.db.add(like)
            await self.db.execute(
                update(PinModel)
                .where(PinModel.id == pin_id)
                .values(likes_count=PinModel.likes_count + 1)
            )
            await self.db.flush()
        except IntegrityError:
            raise ConflictError("Like already exists")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while adding pin like: {pin_id}, {user_id}")
            raise AppError()

    async def delete_like(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> None:
        try:
            like = await self.db.execute(
                select(PinLikeModel)
                .where(PinLikeModel.pin_id == pin_id)
                .where(PinLikeModel.user_id == user_id)
            )
            like_obj = like.scalar_one_or_none()
            if not like_obj:
                raise NotFoundError("Like not found")
            await self.db.delete(like_obj)
            await self.db.execute(
                update(PinModel)
                .where(PinModel.id == pin_id)
                .values(likes_count=PinModel.likes_count - 1)
            )
            await self.db.flush()
        except NotFoundError:
            raise
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while deleting pin like: {pin_id}, {user_id}")
            raise AppError()

    async def update_pin(self, pin: PinModel, data: dict) -> PinModel:
        for field, value in data.items():
            setattr(pin, field, value)
        try:
            await self.db.flush()
            result = await self.db.execute(
                select(PinModel)
                .where(PinModel.id == pin.id)
                .options(selectinload(PinModel.user), selectinload(PinModel.tags))
            )
            return result.scalar_one()
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

    async def _get_generated_pin(
        self, generated_pin_id: uuid.UUID, owner_id: uuid.UUID
    ) -> GeneratedPinModel:
        result = await self.db.execute(
            select(GeneratedPinModel).where(
                GeneratedPinModel.id == generated_pin_id,
                GeneratedPinModel.user_id == owner_id,
            )
        )
        generated_pin = result.scalar_one_or_none()
        if generated_pin is None:
            raise NotFoundError("Generated image not found")
        expires_at = generated_pin.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise BadRequestError("Generated image has expired")
        return generated_pin
