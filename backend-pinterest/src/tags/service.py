from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import logger
from boards.models import TagModel
from core.exception import AppError


class TagService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_tag(self, tag_names: list[str]) -> list[TagModel]:
        if not tag_names:
            return []
        try:
            unique_names = list(dict.fromkeys(tag_names))
            query = (
                insert(TagModel)
                .values([{"name": name} for name in unique_names])
                .on_conflict_do_nothing(index_elements=[TagModel.name])
            )
            await self.db.execute(query)

            result = await self.db.execute(
                select(TagModel).where(TagModel.name.in_(unique_names))
            )
            tags = result.scalars().all()

            tags_by_name = {tag.name: tag for tag in tags}
            return [tags_by_name[name] for name in unique_names if name in tags_by_name]

        except SQLAlchemyError:
            logger.error(f"Database error while processing tags: {tag_names}")
            raise AppError()
