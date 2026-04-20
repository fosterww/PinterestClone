import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import AppError
from users.models import UserModel
from users.repository import UserRepository


class UserService:
    def __init__(self, db: AsyncSession, repository: UserRepository):
        self.db = db
        self.repository = repository

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
            raise AppError()

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
            raise AppError()

    async def get_followers(self, username: str) -> list[UserModel]:
        return await self.repository.get_followers(username)

    async def get_following(self, username: str) -> list[UserModel]:
        return await self.repository.get_following(username)

    async def get_followed_user_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self.repository.get_followed_user_ids(user_id)
