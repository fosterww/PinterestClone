import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password, verify_password, create_access_token
from src.users.models import UserModel
from src.users.schemas import UserCreate


async def register_user(db: AsyncSession, data: UserCreate) -> UserModel:
    result = await db.execute(
        select(UserModel).where(
            or_(UserModel.username == data.username, UserModel.email == data.email)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        field = "username" if existing.username == data.username else "email"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{field} already taken",
        )

    try:
        user = UserModel(
            id=uuid.uuid4(),
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            bio=data.bio,
            avatar_url=data.avatar_url,
        )
        db.add(user)
        await db.flush()
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this username or email already exists",
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during registration",
        )


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> UserModel | None:
    try:
        result = await db.execute(
            select(UserModel).where(UserModel.username == username)
        )
        user = result.scalar_one_or_none()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during authentication",
        )
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def create_user_token(user: UserModel) -> str:
    return create_access_token({"sub": user.username})
