from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.exception import AppError
from core.logger import logger
from users.models import RefreshTokenModel


class AuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_refresh_token(self, token: str) -> RefreshTokenModel | None:
        try:
            result = await self.db.execute(
                select(RefreshTokenModel)
                .options(joinedload(RefreshTokenModel.user))
                .where(RefreshTokenModel.token == token)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error("Database error while fetching refresh token")
            raise AppError()

    async def save_refresh_token(
        self, token_model: RefreshTokenModel
    ) -> RefreshTokenModel:
        try:
            self.db.add(token_model)
            await self.db.flush()
            return token_model
        except SQLAlchemyError:
            logger.error("Database error while creating refresh token")
            raise AppError()
