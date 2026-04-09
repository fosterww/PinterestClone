import uuid

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exception import AppError
from core.logger import logger
from boards.models import PinModel, pin_tag_association


class DiscoverRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_related_by_tags(
        self, exclude_pin_id: uuid.UUID, tag_ids: list[uuid.UUID], limit: int
    ) -> list[PinModel]:
        try:
            query = (
                select(PinModel)
                .join(pin_tag_association)
                .where(pin_tag_association.c.tag_id.in_(tag_ids))
                .where(PinModel.id != exclude_pin_id)
                .group_by(PinModel.id)
                .order_by(
                    func.count(pin_tag_association.c.tag_id).desc(),
                    PinModel.created_at.desc(),
                )
                .options(selectinload(PinModel.tags))
                .limit(limit)
            )
            result = await self.db.execute(query)
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(
                f"Database error while fetching related pins: {exclude_pin_id}, {tag_ids}, {limit}"
            )
            raise AppError()

    async def get_personalized_feed(
        self, tag_ids: list[uuid.UUID], limit: int = 20
    ) -> list[PinModel]:
        try:
            if not tag_ids:
                query = (
                    select(PinModel)
                    .options(selectinload(PinModel.tags))
                    .order_by(PinModel.created_at.desc())
                    .limit(limit)
                )
                result = await self.db.execute(query)
                return list(result.scalars().all())

            query = (
                select(PinModel)
                .join(pin_tag_association)
                .where(pin_tag_association.c.tag_id.in_(tag_ids))
                .group_by(PinModel.id)
                .order_by(
                    func.count(pin_tag_association.c.tag_id).desc(),
                    PinModel.created_at.desc(),
                )
                .options(selectinload(PinModel.tags))
                .limit(limit)
            )
            result = await self.db.execute(query)
            pins = list(result.scalars().all())

            if len(pins) < limit:
                remaining = limit - len(pins)
                exclude_ids = [pin.id for pin in pins]
                fill_query = select(PinModel).options(selectinload(PinModel.tags))
                if exclude_ids:
                    fill_query = fill_query.where(PinModel.id.notin_(exclude_ids))
                fill_query = fill_query.order_by(PinModel.created_at.desc()).limit(
                    remaining
                )
                fill_result = await self.db.execute(fill_query)
                pins.extend(fill_result.scalars().all())

            return pins
        except SQLAlchemyError:
            logger.error(f"Database error while fetching personalized feed: {tag_ids}")
            raise AppError()
