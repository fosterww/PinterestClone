from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from users.models import UserModel
from users.schemas import UserUpdate
from core.exception import AppError, ConflictError
from core.logger import logger


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: dict) -> UserModel:
        try:
            user = UserModel(**user_data)
            self.db.add(user)
            await self.db.flush()
            return user
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while creating user: {user_data.get('username')}"
            )
            raise AppError()

    async def get_user_by_id(self, user_id) -> UserModel | None:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching user by id: {user_id}")
            raise AppError()

    async def get_user_by_username_or_email(
        self, username: str, email: str
    ) -> UserModel | None:
        try:
            result = await self.db.execute(
                select(UserModel).where(
                    or_(UserModel.username == username, UserModel.email == email)
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching user: {username}, {email}")
            raise AppError()

    async def get_user_by_google_id_or_email(
        self, google_id: str, email: str
    ) -> UserModel | None:
        try:
            result = await self.db.execute(
                select(UserModel).where(
                    or_(UserModel.google_id == google_id, UserModel.email == email)
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching user: {google_id}, {email}")
            raise AppError()

    async def link_google_id(self, user_id, google_id: str) -> UserModel:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise AppError()
            user.google_id = google_id
            await self.db.flush()
            return user
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while linking google_id for user: {user_id}")
            raise AppError()

    async def update_user(self, user_id, data: UserUpdate) -> UserModel:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise AppError()
            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(user, field, value)
            await self.db.flush()
            return user
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while updating user: {user_id}")
            raise AppError()
