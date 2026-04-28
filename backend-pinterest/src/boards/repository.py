import uuid
from typing import List

from sqlalchemy import select, delete, insert as sa_insert, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from core.exception import AppError, ConflictError
from core.logger import logger

from boards.models import BoardModel, PinModel, PinCommentModel, board_pin_association
from users.models import UserModel
from boards.schemas import BoardCreate, BoardUpdate, BoardVisibility


class BoardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner: UserModel, data: BoardCreate) -> BoardModel:
        try:
            board_data = data.model_dump(exclude_unset=True)
            board = BoardModel(**board_data, owner_id=owner.id)
            self.db.add(board)
            await self.db.flush()
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board.id)
                .options(selectinload(BoardModel.user))
            )
            return result.scalar_one()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Board conflicts with existing data")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while creating board: {owner.id}")
            raise AppError()

    async def get_by_owner_id(self, user_id: uuid.UUID) -> List[BoardModel]:
        try:
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.owner_id == user_id)
                .options(selectinload(BoardModel.user))
                .order_by(BoardModel.updated_at.desc())
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching boards: {user_id}")
            raise AppError()

    async def get_public_by_owner_id(self, user_id: uuid.UUID) -> List[BoardModel]:
        try:
            result = await self.db.execute(
                select(BoardModel)
                .where(
                    BoardModel.owner_id == user_id,
                    BoardModel.visibility == BoardVisibility.PUBLIC,
                )
                .options(selectinload(BoardModel.user))
                .order_by(BoardModel.updated_at.desc())
            )
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching public boards: {user_id}")
            raise AppError()

    async def get_by_id(self, board_id: uuid.UUID) -> BoardModel | None:
        try:
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board_id)
                .options(
                    joinedload(BoardModel.user),
                    selectinload(BoardModel.pins).selectinload(PinModel.tags),
                    selectinload(BoardModel.pins).selectinload(PinModel.user),
                    selectinload(BoardModel.pins)
                    .selectinload(PinModel.comments)
                    .selectinload(PinCommentModel.user),
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching board: {board_id}")
            raise AppError()

    async def search_boards(
        self,
        query: str,
        limit: int,
        offset: int,
        current_user_id: uuid.UUID | None = None,
    ) -> List[BoardModel]:
        try:
            stmt = (
                select(BoardModel)
                .where(BoardModel.title.ilike(f"%{query}%"))
                .options(selectinload(BoardModel.user))
                .order_by(BoardModel.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )

            if current_user_id is None:
                stmt = stmt.where(BoardModel.visibility == BoardVisibility.PUBLIC)
            else:
                stmt = stmt.where(
                    or_(
                        BoardModel.visibility == BoardVisibility.PUBLIC,
                        BoardModel.owner_id == current_user_id,
                    )
                )

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError:
            logger.error(f"Database error while searching boards: {query}")
            raise AppError()

    async def update_board(self, board: BoardModel, data: BoardUpdate) -> BoardModel:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(board, field, value)
        try:
            await self.db.flush()
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board.id)
                .options(selectinload(BoardModel.user))
            )
            return result.scalar_one()
        except IntegrityError:
            await self.db.rollback()
            logger.error(f"Board update conflicts with existing data: {board.id}")
            raise ConflictError("Board update conflicts with existing data")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while updating board: {board.id}")
            raise AppError()

    async def add_pin_to_board(self, board: BoardModel, pin: PinModel) -> None:
        try:
            values = {"board_id": board.id, "pin_id": pin.id}
            dialect_name = self.db.get_bind().dialect.name
            if dialect_name == "postgresql":
                stmt = pg_insert(board_pin_association).values(**values)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["board_id", "pin_id"]
                )
            elif dialect_name == "sqlite":
                stmt = sqlite_insert(board_pin_association).values(**values)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["board_id", "pin_id"]
                )
            else:
                stmt = sa_insert(board_pin_association).values(**values)
            result = await self.db.execute(stmt)
            if result.rowcount == 0:
                raise ConflictError("Pin is already on this board")
            pin.saves_count += 1
            await self.db.flush()
            self.db.expire(board, ["pins"])
        except ConflictError:
            raise
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Pin is already on this board")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while adding pin to board: {board.id}, {pin.id}"
            )
            raise AppError()

    async def remove_pin_from_board(self, board: BoardModel, pin: PinModel) -> None:
        try:
            stmt = delete(board_pin_association).where(
                board_pin_association.c.board_id == board.id,
                board_pin_association.c.pin_id == pin.id,
            )
            result = await self.db.execute(stmt)
            if result.rowcount:
                pin.saves_count = max(pin.saves_count - 1, 0)
            await self.db.flush()
            self.db.expire(board, ["pins"])
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while removing pin from board: {board.id}, {pin.id}"
            )
            raise AppError()
