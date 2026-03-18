import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.boards.models import PinModel
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pin conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pin update conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete pin — it is still referenced",
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting pin",
        )
