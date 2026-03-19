from fastapi import HTTPException, status
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.boards.models import TagModel

async def get_or_create_tag(db: AsyncSession, tag_names: list[str]) -> list[TagModel]:
    if not tag_names:
        return []
    try:
        query = select(TagModel).where(TagModel.name.in_(tag_names))
        result = await db.execute(query)
        existing_tags = result.scalars().all()
        existing_names = {tag.name for tag in existing_tags}

        new_tags = [
            TagModel(id=uuid.uuid4(), name=name)
            for name in tag_names
            if name not in existing_names
        ]

        if new_tags:
            db.add_all(new_tags)
            await db.flush()

        return existing_tags + new_tags
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error while processing tags")
    