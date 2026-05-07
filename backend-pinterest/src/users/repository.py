import uuid

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from boards.models import BoardModel, BoardVisibility, PinModel
from core.exception import AppError, ConflictError, NotFoundError
from core.logger import logger
from users.models import UserModel, user_follow_association
from users.schemas import UserUpdate


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

    async def get_user_by_username(self, username: str) -> UserModel | None:
        try:
            result = await self.db.execute(
                select(UserModel).where(UserModel.username == username)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching user by username: {username}")
            raise AppError()

    async def search_public_profiles(
        self, query: str, limit: int, offset: int
    ) -> list[UserModel]:
        try:
            result = await self.db.execute(
                select(UserModel)
                .where(
                    or_(
                        UserModel.username.ilike(f"%{query}%"),
                        UserModel.full_name.ilike(f"%{query}%"),
                    )
                )
                .order_by(UserModel.username.asc())
                .limit(limit)
                .offset(offset)
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while searching users by username: {query}")
            raise AppError()

    async def get_public_user_profile(self, username: str) -> dict | None:
        try:
            user = await self.get_user_by_username(username)
            if user is None:
                return None

            pins_count = await self.db.scalar(
                select(func.count())
                .select_from(PinModel)
                .where(PinModel.owner_id == user.id)
            )
            boards_count = await self.db.scalar(
                select(func.count())
                .select_from(BoardModel)
                .where(
                    BoardModel.owner_id == user.id,
                    BoardModel.visibility == BoardVisibility.PUBLIC,
                )
            )

            return {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "bio": user.bio,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at,
                "pins_count": pins_count or 0,
                "boards_count": boards_count or 0,
            }
        except SQLAlchemyError:
            logger.error(
                f"Database error while fetching public profile for username: {username}"
            )
            raise AppError()

    async def get_followers(self, username: str) -> list[UserModel]:
        try:
            user = await self.get_user_by_username(username)
            if user is None:
                raise NotFoundError("User not found")
            result = await self.db.execute(
                select(UserModel)
                .join(
                    user_follow_association,
                    UserModel.id == user_follow_association.c.follower_id,
                )
                .where(user_follow_association.c.followed_id == user.id)
            )
            return result.scalars().all()
        except NotFoundError:
            raise
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while getting followers for user: {username}")
            raise AppError()

    async def get_following(self, username: str) -> list[UserModel]:
        try:
            user = await self.get_user_by_username(username)
            if user is None:
                raise NotFoundError("User not found")
            result = await self.db.execute(
                select(UserModel)
                .join(
                    user_follow_association,
                    UserModel.id == user_follow_association.c.followed_id,
                )
                .where(user_follow_association.c.follower_id == user.id)
            )
            return result.scalars().all()
        except NotFoundError:
            raise
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while getting following for user: {username}")
            raise AppError()

    async def follow_user(self, follower_id: uuid.UUID, followed_username: str) -> None:
        try:
            followed_user = await self.get_user_by_username(followed_username)
            if followed_user is None:
                raise NotFoundError("User not found")
            if follower_id == followed_user.id:
                raise ConflictError("Cannot follow yourself")
            query = insert(user_follow_association).values(
                follower_id=follower_id,
                followed_id=followed_user.id,
            )
            await self.db.execute(query)
            await self.db.flush()
        except ConflictError:
            raise
        except NotFoundError:
            raise
        except IntegrityError:
            await self.db.rollback()
            logger.error(
                f"Integrity error while following user: {follower_id} -> {followed_username}"
            )
            raise ConflictError("Already following user")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while following user: {follower_id} -> {followed_username}"
            )
            raise AppError()

    async def unfollow_user(
        self, follower_id: uuid.UUID, followed_username: str
    ) -> None:
        try:
            followed_user = await self.get_user_by_username(followed_username)
            if followed_user is None:
                raise NotFoundError("User not found")
            query = delete(user_follow_association).where(
                user_follow_association.c.follower_id == follower_id,
                user_follow_association.c.followed_id == followed_user.id,
            )
            result = await self.db.execute(query)
            if result.rowcount == 0:
                raise NotFoundError("Follow relationship not found")
            await self.db.flush()
        except NotFoundError:
            raise
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while unfollowing user: {follower_id} -> {followed_username}"
            )
            raise AppError()

    async def is_following(
        self, follower_id: uuid.UUID, followed_username: str
    ) -> bool:
        try:
            followed_user = await self.get_user_by_username(followed_username)
            if followed_user is None:
                return False
            result = await self.db.execute(
                select(user_follow_association.c.follower_id).where(
                    user_follow_association.c.follower_id == follower_id,
                    user_follow_association.c.followed_id == followed_user.id,
                )
            )
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError:
            logger.error(
                f"Database error while checking follow status: {follower_id} -> {followed_username}"
            )
            raise AppError()

    async def get_followed_user_ids(self, follower_id: uuid.UUID) -> list[uuid.UUID]:
        try:
            result = await self.db.execute(
                select(user_follow_association.c.followed_id).where(
                    user_follow_association.c.follower_id == follower_id
                )
            )
            return list(result.scalars().all())
        except SQLAlchemyError:
            logger.error(
                f"Database error while fetching followed users for follower: {follower_id}"
            )
            raise AppError()

    async def get_followers_count(self, user_id: uuid.UUID) -> int:
        try:
            result = await self.db.scalar(
                select(func.count())
                .select_from(user_follow_association)
                .where(user_follow_association.c.followed_id == user_id)
            )
            return int(result or 0)
        except SQLAlchemyError:
            logger.error(f"Database error while counting followers for user: {user_id}")
            raise AppError()

    async def get_following_count(self, user_id: uuid.UUID) -> int:
        try:
            result = await self.db.scalar(
                select(func.count())
                .select_from(user_follow_association)
                .where(user_follow_association.c.follower_id == user_id)
            )
            return int(result or 0)
        except SQLAlchemyError:
            logger.error(f"Database error while counting following for user: {user_id}")
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
