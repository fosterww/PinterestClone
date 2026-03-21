import uuid

from fastapi import HTTPException, status, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.core.cache import get_cache_service
from src.boards.models import PinModel, pin_tag_association
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate
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
            tags=tags
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
    db: AsyncSession, offset: int = 0, limit: int = 20
) -> list[PinModel]:
    try:
        result = await db.execute(
            select(PinModel)
            .order_by(PinModel.created_at.desc())
            .options(selectinload(PinModel.tags))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
    except SQLAlchemyError:
        logger.error(f"Database error while fetching pins: {offset}, {limit}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching pins",
        )


async def get_pin_by_id(db: AsyncSession, pin_id: uuid.UUID) -> PinModel:
    try:
        result = await db.execute(
            select(PinModel).where(PinModel.id == pin_id)
            .options(selectinload(PinModel.tags))
        )
        pin = result.scalar_one_or_none()
        if pin is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
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


async def delete_pin(
    db: AsyncSession, pin: PinModel, current_user: UserModel
) -> None:
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
    cache_service = Depends(get_cache_service)
) -> list[PinModel]:
    try:
        cached_pins = await cache_service.get(f"related_pins:{pin_id}")
        if cached_pins:
            return cached_pins
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
            .order_by(func.count(pin_tag_association.c.tag_id).desc(), PinModel.created_at.desc())
            .options(selectinload(PinModel.tags))
            .limit(limit)
        )
        cache_params = {
            "key": f"related_pins:{pin_id}",
            "value": list(related_result.scalars().all()),
            "ttl": 3600
        }
        await cache_service.set(**cache_params)
        return list(related_result.scalars().all())
    except SQLAlchemyError:
        logger.error(f"Database error while fetching related pins: {pin_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching related pins",
        )


async def get_pins_by_ids(
    db: AsyncSession, pin_ids: list[str]
) -> list[PinModel]:
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
