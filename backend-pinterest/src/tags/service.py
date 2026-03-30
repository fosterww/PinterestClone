import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.boards.models import TagModel
from src.core.exception import AppError


class TagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_tag(self, tag_names: list[str]) -> list[TagModel]:
        if not tag_names:
            return []
        try:
            query = select(TagModel).where(TagModel.name.in_(tag_names))
            result = await self.db.execute(query)
            existing_tags = result.scalars().all()
            existing_names = {tag.name for tag in existing_tags}

            new_tags = [
                TagModel(id=uuid.uuid4(), name=name)
                for name in tag_names
                if name not in existing_names
            ]

            if new_tags:
                self.db.add_all(new_tags)
                await self.db.flush()

            return existing_tags + new_tags
        except SQLAlchemyError:
            logger.error(f"Database error while processing tags: {tag_names}")
            raise AppError()
