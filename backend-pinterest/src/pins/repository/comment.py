from typing import List
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import AppError, ConflictError
from core.logger import logger
from boards.models import PinCommentModel, PinCommentLikeModel


class CommentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_comments(self, pin_id: uuid.UUID) -> List[PinCommentModel]:
        try:
            result = await self.db.execute(
                select(PinCommentModel)
                .where(
                    PinCommentModel.pin_id == pin_id,
                    PinCommentModel.parent_id.is_(None),
                )
                .options(selectinload(PinCommentModel.user))
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching comments: {pin_id}")
            raise AppError()

    async def get_all_comments_flat(self, pin_id: uuid.UUID) -> List[PinCommentModel]:
        try:
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.pin_id == pin_id)
                .options(selectinload(PinCommentModel.user))
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching all comments flat: {pin_id}")
            raise AppError()

    async def get_comment_by_id(self, comment_id: uuid.UUID) -> PinCommentModel | None:
        try:
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.id == comment_id)
                .options(selectinload(PinCommentModel.user))
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching comment: {comment_id}")
            raise AppError()

    async def add_comment(
        self,
        pin_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
        parent_id: uuid.UUID | None = None,
    ) -> PinCommentModel:
        try:
            comment = PinCommentModel(
                pin_id=pin_id,
                user_id=user_id,
                comment=text,
                parent_id=parent_id,
            )
            self.db.add(comment)
            await self.db.flush()
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.id == comment.id)
                .options(
                    selectinload(PinCommentModel.user),
                    selectinload(PinCommentModel.replies).options(
                        selectinload(PinCommentModel.user),
                        selectinload(PinCommentModel.replies),
                    ),
                )
            )
            return result.scalar_one()
        except IntegrityError:
            await self.db.rollback()
            logger.error(f"Integrity error while adding comment: {pin_id}, {user_id}")
            raise ConflictError("Comment not added")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while adding comment: {pin_id}, {user_id}")
            raise AppError()

    async def get_comment_like(
        self, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentLikeModel | None:
        try:
            result = await self.db.execute(
                select(PinCommentLikeModel)
                .where(PinCommentLikeModel.comment_id == comment_id)
                .where(PinCommentLikeModel.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(
                f"Database error while fetching comment like: {comment_id}, {user_id}"
            )
            raise AppError()

    async def add_comment_like(
        self, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentModel:
        try:
            like = PinCommentLikeModel(comment_id=comment_id, user_id=user_id)
            self.db.add(like)
            await self.db.execute(
                update(PinCommentModel)
                .where(PinCommentModel.id == comment_id)
                .values(likes_count=PinCommentModel.likes_count + 1)
            )
            await self.db.flush()
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.id == comment_id)
                .options(
                    selectinload(PinCommentModel.user),
                    selectinload(PinCommentModel.replies).options(
                        selectinload(PinCommentModel.user),
                        selectinload(PinCommentModel.replies),
                    ),
                )
            )
            return result.scalar_one()
        except IntegrityError:
            await self.db.rollback()
            logger.error(f"Integrity error while adding comment like: {comment_id}")
            raise ConflictError("Comment like already exists")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while adding comment like: {comment_id}")
            raise AppError()

    async def delete_comment_like(self, like: PinCommentLikeModel) -> PinCommentModel:
        try:
            await self.db.delete(like)
            await self.db.execute(
                update(PinCommentModel)
                .where(PinCommentModel.id == like.comment_id)
                .values(likes_count=PinCommentModel.likes_count - 1)
            )
            await self.db.flush()
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.id == like.comment_id)
                .options(
                    selectinload(PinCommentModel.user),
                    selectinload(PinCommentModel.replies).options(
                        selectinload(PinCommentModel.user),
                        selectinload(PinCommentModel.replies),
                    ),
                )
            )
            return result.scalar_one()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while deleting comment like: {like.comment_id}"
            )
            raise AppError()

    async def update_comment(
        self, pin_comment: PinCommentModel, text: str
    ) -> PinCommentModel:
        try:
            pin_comment.comment = text
            await self.db.flush()
            result = await self.db.execute(
                select(PinCommentModel)
                .where(PinCommentModel.id == pin_comment.id)
                .options(
                    selectinload(PinCommentModel.user),
                    selectinload(PinCommentModel.replies).options(
                        selectinload(PinCommentModel.user),
                        selectinload(PinCommentModel.replies),
                    ),
                )
            )
            return result.scalar_one()
        except IntegrityError:
            await self.db.rollback()
            logger.error(f"Integrity error while updating comment: {pin_comment.id}")
            raise ConflictError("Comment not updated")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while updating comment: {pin_comment.id}")
            raise AppError()

    async def delete_comment(self, pin_comment: PinCommentModel) -> None:
        try:
            await self.db.delete(pin_comment)
            await self.db.flush()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while deleting comment: {pin_comment.id}")
            raise AppError()
