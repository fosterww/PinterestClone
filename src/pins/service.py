import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.boards.models import PinModel
from src.users.models import UserModel
from src.pins.schemas import PinCreate, PinUpdate


async def create_pin(
    db: AsyncSession, owner: UserModel, data: PinCreate, image_url: str
) -> PinModel:
    try:
        pin = PinModel(
            id=uuid.uuid4(),
            owner_id=owner.id,
            title=data.title,
            description=data.description,
            image_url=image_url,
            link_url=data.link_url,
        )
        db.add(pin)
        await db.flush()
        return pin
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
    for field, value in update_data.items():
        setattr(pin, field, value)
    try:
        await db.flush()
        await db.refresh(pin)
        return pin
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
