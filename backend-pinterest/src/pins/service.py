import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.core.cache import CacheService
from src.boards.models import PinModel, pin_tag_association, TagModel, PinLikeModel
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate, PinResponse, CreatedAt, Popularity
from src.tags.service import get_or_create_tag


async def create_pin(
    db: AsyncSession, owner: UserModel, data: PinCreate, image_url: str
) -> PinModel:
    try:
        tags = await get_or_create_tag(db, data.tags)
        pin = PinModel(
            id=uuid.uuid4(),
            owner_id=owner.id,
            title=data.title,
            description=data.description,
            image_url=image_url,
            link_url=data.link_url,
            tags=tags,
        )
        db.add(pin)
        await db.flush()
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin.id)
            .options(selectinload(PinModel.tags))
        )
        return result.scalar_one()
    except IntegrityError:
        await db.rollback()
        logger.error(f"Pin conflicts with existing data: {owner.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pin conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while creating pin: {owner.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating pin",
        )


async def get_pins(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    search: str | None = None,
    tags: list[str] = [],
    created_at: CreatedAt | None = None,
    popularity: Popularity | None = None,
) -> list[PinModel]:
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

        result = await db.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())
    except SQLAlchemyError:
        logger.error(f"Database error while fetching pins: {offset}, {limit}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching pins",
        )


async def get_user_pins(username: str, db: AsyncSession) -> List[PinModel]:
    try:
        result = await db.execute(
            select(PinModel)
            .join(UserModel)
            .where(UserModel.username == username)
            .options(selectinload(PinModel.tags))
            .order_by(PinModel.created_at.desc())
        )
        return list(result.scalars().all())
    except SQLAlchemyError:
        logger.error(f"Database error while fetching user pins: {username}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user pins",
        )


async def like_pin(db: AsyncSession, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
    try:
        result = await db.execute(
            select(PinLikeModel)
            .where(PinLikeModel.pin_id == pin_id)
            .where(PinLikeModel.user_id == user_id)
        )
        existing_like = result.scalar_one_or_none()
        if existing_like is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Pin like already exists"
            )
        pin = await get_pin_by_id(db, pin_id)
        pin.likes_count += 1
        pin_like = PinLikeModel(pin_id=pin_id, user_id=user_id)
        db.add(pin_like)
        await db.flush()
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin_id)
            .options(selectinload(PinModel.tags))
        )
        return result.scalar_one()
    except HTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while liking pin: {pin_id}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while liking pin",
        )


async def unlike_pin(
    db: AsyncSession, pin_id: uuid.UUID, user_id: uuid.UUID
) -> PinModel:
    try:
        result = await db.execute(
            select(PinLikeModel)
            .where(PinLikeModel.pin_id == pin_id)
            .where(PinLikeModel.user_id == user_id)
        )
        pin_like = result.scalar_one_or_none()
        if pin_like is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pin like not found"
            )
        pin = await get_pin_by_id(db, pin_id)
        pin.likes_count = max(0, pin.likes_count - 1)
        await db.delete(pin_like)
        await db.flush()
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin_id)
            .options(selectinload(PinModel.tags))
        )
        return result.scalar_one()
    except HTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while unliking pin: {pin_id}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while unliking pin",
        )


async def get_pin_by_id(db: AsyncSession, pin_id: uuid.UUID) -> PinModel:
    try:
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin_id)
            .options(selectinload(PinModel.tags))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found"
            )
        return pin
    except SQLAlchemyError:
        logger.error(f"Database error while fetching pin: {pin_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching pin",
        )


async def update_pin(
    db: AsyncSession, pin: PinModel, data: PinUpdate, current_user: UserModel
) -> PinModel:
    if pin.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the pin owner",
        )
    update_data = data.model_dump(exclude_unset=True)
    if "tags" in update_data:
        pin.tags = await get_or_create_tag(db, update_data["tags"])
        del update_data["tags"]
    for field, value in update_data.items():
        setattr(pin, field, value)
    try:
        await db.flush()
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin.id)
            .options(selectinload(PinModel.tags))
        )
        return result.scalar_one()
    except IntegrityError:
        await db.rollback()
        logger.error(f"Pin update conflicts with existing data: {pin.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pin update conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while updating pin: {pin.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while updating pin",
        )


async def delete_pin(db: AsyncSession, pin: PinModel, current_user: UserModel) -> None:
    if pin.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the pin owner",
        )
    try:
        await db.delete(pin)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.error(f"Error while deleting pin: {pin.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete pin — it is still referenced",
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while deleting pin: {pin.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting pin",
        )


async def get_related_pins_from_db(
    db: AsyncSession,
    pin_id: uuid.UUID,
    limit: int = 20,
    cache_service: CacheService | None = None,
) -> list[PinModel | PinResponse]:
    try:
        if cache_service:
            cached_pins = await cache_service.get_pattern(f"related_pins:{pin_id}:*")
            if cached_pins:
                return [PinResponse.model_validate_json(p) for p in cached_pins if p]
    except Exception:
        pass
    try:
        result = await db.execute(
            select(PinModel)
            .where(PinModel.id == pin_id)
            .options(selectinload(PinModel.tags))
        )
        pin = result.scalar_one_or_none()
        if not pin or not pin.tags:
            return []

        tag_ids = [tag.id for tag in pin.tags]

        related_result = await db.execute(
            select(PinModel)
            .join(pin_tag_association)
            .where(pin_tag_association.c.tag_id.in_(tag_ids))
            .where(PinModel.id != pin_id)
            .group_by(PinModel.id)
            .order_by(
                func.count(pin_tag_association.c.tag_id).desc(),
                PinModel.created_at.desc(),
            )
            .options(selectinload(PinModel.tags))
            .limit(limit)
        )
        items = list(related_result.scalars().all())
        if cache_service:
            for i, pin in enumerate(items):
                pin_json = PinResponse.model_validate(pin).model_dump_json()
                await cache_service.set(f"related_pins:{pin_id}:{i}", pin_json, 600)
        return items
    except SQLAlchemyError:
        logger.error(f"Database error while fetching related pins: {pin_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching related pins",
        )


async def get_pins_by_ids(db: AsyncSession, pin_ids: list[str]) -> list[PinModel]:
    try:
        uuids = []
        for pid in pin_ids:
            try:
                uuids.append(uuid.UUID(pid))
            except ValueError:
                continue

        if not uuids:
            return []

        result = await db.execute(
            select(PinModel)
            .where(PinModel.id.in_(uuids))
            .options(selectinload(PinModel.tags))
        )
        return list(result.scalars().all())
    except SQLAlchemyError:
        logger.error(f"Database error while fetching pins by IDs: {pin_ids}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching pins by IDs",
        )
