from sqlalchemy.orm import selectinload, joinedload
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.boards.models import BoardModel, PinModel, board_pin_association
from src.users.models import UserModel
from src.boards.schemas import BoardCreate, BoardUpdate


async def create_board(
    db: AsyncSession, owner: UserModel, data: BoardCreate
) -> BoardModel:
    try:
        board = BoardModel(
            id=uuid.uuid4(),
            owner_id=owner.id,
            title=data.title,
            description=data.description,
            visibility=data.visibility,
        )
        db.add(board)
        await db.flush()
        return board
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Board conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating board",
        )


async def get_user_boards(
    db: AsyncSession, user_id: uuid.UUID
) -> list[BoardModel]:
    try:
        result = await db.execute(
            select(BoardModel)
            .where(BoardModel.owner_id == user_id)
            .options(selectinload(BoardModel.user))
            .order_by(BoardModel.updated_at.desc())
        )
        return list(result.scalars().all())
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching boards",
        )


async def get_board_by_id(
    db: AsyncSession, board_id: uuid.UUID
) -> BoardModel | None:
    try:
        result = await db.execute(
            select(BoardModel).where(BoardModel.id == board_id)
            .options(joinedload(BoardModel.user), selectinload(BoardModel.pins))
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching board",
        )


async def update_board(
    db: AsyncSession,
    board: BoardModel,
    data: BoardUpdate,
    current_user: UserModel,
) -> BoardModel:
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the board owner",
        )
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(board, field, value)
    try:
        await db.flush()
        return board
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Board update conflicts with existing data",
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while updating board",
        )


async def add_pin_to_board(
    db: AsyncSession,
    board: BoardModel,
    pin: PinModel,
    current_user: UserModel,
) -> None:
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the board owner",
        )
    try:
        check_stmt = select(board_pin_association).where(
            (board_pin_association.c.board_id == board.id) &
            (board_pin_association.c.pin_id == pin.id)
        )
        result = await db.execute(check_stmt)
        if result.first():
            return
        stmt = board_pin_association.insert().values(
            board_id=board.id, pin_id=pin.id
        )
        await db.execute(stmt)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pin is already on this board",
        )
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while adding pin to board",
        )


async def remove_pin_from_board(
    db: AsyncSession,
    board: BoardModel,
    pin: PinModel,
    current_user: UserModel,
) -> None:
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin not found")
    if board.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not the board owner",
        )
    try:
        stmt = board_pin_association.delete().where(
            (board_pin_association.c.board_id == board.id)
            & (board_pin_association.c.pin_id == pin.id)
        )
        await db.execute(stmt)
        await db.flush()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while removing pin from board",
        )
