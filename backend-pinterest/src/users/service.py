from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.users.models import UserModel
from src.users.schemas import UserUpdate


async def get_user_by_id(db: AsyncSession, user_id) -> UserModel | None:
    try:
        result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        return result.scalar_one_or_none()
    except SQLAlchemyError:
        logger.error(f"Database error while fetching user: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user",
        )


async def update_user(db: AsyncSession, user: UserModel, data: UserUpdate) -> UserModel:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    try:
        await db.flush()
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update conflicts with an existing user",
        )
    except SQLAlchemyError:
        await db.rollback()
        logger.error(f"Database error while updating user: {user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while updating user",
        )
