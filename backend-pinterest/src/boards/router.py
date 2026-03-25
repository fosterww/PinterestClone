import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.limiter import limiter
from src.database import get_db
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.boards.schemas import (
    BoardCreate,
    BoardUpdate,
    BoardResponse,
    BoardPinsResponse,
)
from src.pins.schemas import PinResponse
from src.boards.service import (
    create_board,
    get_user_boards,
    get_board_by_id,
    update_board,
    add_pin_to_board,
    remove_pin_from_board,
)
from src.pins.service import get_pin_by_id

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_new_board(
    request: Request,
    data: BoardCreate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    board = await create_board(db, current_user, data)
    return board


@router.get("/")
@limiter.limit("10/minute")
async def list_boards(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BoardResponse]:
    return await get_user_boards(db, current_user.id)


@router.get("/{board_id}")
@limiter.limit("10/minute")
async def read_board(
    request: Request, board_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BoardPinsResponse:
    board = await get_board_by_id(db, board_id)
    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )
    return board


@router.patch("/{board_id}")
@limiter.limit("5/minute")
async def patch_board(
    request: Request,
    board_id: uuid.UUID,
    data: BoardUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    board = await get_board_by_id(db, board_id)
    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )
    return await update_board(db, board, data, current_user)


@router.post("/{board_id}/pins/{pin_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def add_pin(
    request: Request,
    board_id: uuid.UUID,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PinResponse:
    board = await get_board_by_id(db, board_id)
    pin = await get_pin_by_id(db, pin_id)
    await add_pin_to_board(db, board, pin, current_user)
    return pin


@router.delete("/{board_id}/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def remove_pin(
    request: Request,
    board_id: uuid.UUID,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    board = await get_board_by_id(db, board_id)
    pin = await get_pin_by_id(db, pin_id)
    await remove_pin_from_board(db, board, pin, current_user)
