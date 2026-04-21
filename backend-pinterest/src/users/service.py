import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import AppError, NotFoundError
from users.models import UserModel
from users.repository import UserRepository
from users.schemas import (
    PublicUserResponse,
    UserResponse,
    UserUpdate,
)


class UserService:
    def __init__(self, db: AsyncSession, repository: UserRepository):
        self.db = db
        self.repository = repository

    async def get_public_user_profile(self, username: str) -> PublicUserResponse:
        try:
            profile = await self.repository.get_public_user_profile(username)
            if profile is None:
                raise NotFoundError("User not found")
            return PublicUserResponse.model_validate(profile)
        except AppError:
            raise
        except Exception:
            raise AppError(detail="Failed to fetch public user profile")

    async def update_current_user(
        self, user_id: uuid.UUID, data: UserUpdate
    ) -> UserResponse:
        try:
            updated_user = await self.repository.update_user(user_id, data)
            await self.db.commit()
            return UserResponse.model_validate(updated_user)
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to update user")

    async def follow_user(self, follower_id: uuid.UUID, followed_username: str) -> None:
        try:
            if await self.repository.is_following(follower_id, followed_username):
                return None
            await self.repository.follow_user(follower_id, followed_username)
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to follow user")

    async def unfollow_user(
        self, follower_id: uuid.UUID, followed_username: str
    ) -> None:
        try:
            await self.repository.unfollow_user(follower_id, followed_username)
            await self.db.commit()
        except AppError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise AppError(detail="Failed to unfollow user")

    async def get_followers(self, username: str) -> list[UserModel]:
        try:
            return await self.repository.get_followers(username)
        except AppError:
            raise
        except Exception:
            raise AppError(detail="Failed to fetch followers")

    async def get_following(self, username: str) -> list[UserModel]:
        try:
            return await self.repository.get_following(username)
        except AppError:
            raise
        except Exception:
            raise AppError(detail="Failed to fetch following")

    async def get_followed_user_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        try:
            return await self.repository.get_followed_user_ids(user_id)
        except AppError:
            raise
        except Exception:
            raise AppError(detail="Failed to fetch followed user ids")
