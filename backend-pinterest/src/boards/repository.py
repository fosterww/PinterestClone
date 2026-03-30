import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from src.core.exception import AppError, ConflictError
from src.core.logger import logger

from src.boards.models import BoardModel, PinModel
from src.users.models import UserModel
from src.boards.schemas import BoardCreate, BoardUpdate, BoardResponse


class BoardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner: UserModel, data: BoardCreate) -> BoardResponse:
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
            return BoardResponse.model_validate(result.scalar_one())
        except IntegrityError:
            await self.db.rollback()
            raise ConflictError("Board conflicts with existing data")
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(f"Database error while creating board: {owner.id}")
            raise AppError()

    async def get_by_owner_id(self, user_id: uuid.UUID) -> List[BoardResponse]:
        try:
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.owner_id == user_id)
                .options(selectinload(BoardModel.user))
                .order_by(BoardModel.updated_at.desc())
            )
            return [
                BoardResponse.model_validate(board) for board in result.scalars().all()
            ]
        except SQLAlchemyError:
            logger.error(f"Database error while fetching boards: {user_id}")
            raise AppError()

    async def get_by_id(self, board_id: uuid.UUID) -> BoardModel | None:
        try:
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board_id)
                .options(
                    joinedload(BoardModel.user),
                    selectinload(BoardModel.pins).selectinload(PinModel.tags),
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError:
            logger.error(f"Database error while fetching board: {board_id}")
            raise AppError()

    async def update_board(self, board: BoardModel, data: BoardUpdate) -> BoardResponse:
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
            return BoardResponse.model_validate(result.scalar_one())
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
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board.id)
                .options(selectinload(BoardModel.pins))
            )
            fresh_board = result.scalar_one()
            if pin not in fresh_board.pins:
                fresh_board.pins.append(pin)
            await self.db.flush()
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
            result = await self.db.execute(
                select(BoardModel)
                .where(BoardModel.id == board.id)
                .options(selectinload(BoardModel.pins))
            )
            fresh_board = result.scalar_one()
            if pin in fresh_board.pins:
                fresh_board.pins.remove(pin)
            await self.db.flush()
        except SQLAlchemyError:
            await self.db.rollback()
            logger.error(
                f"Database error while removing pin from board: {board.id}, {pin.id}"
            )
            raise AppError()
