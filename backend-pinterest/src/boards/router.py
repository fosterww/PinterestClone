import uuid
from typing import List

from fastapi import APIRouter, Depends, status, Request

from core.security.limiter import limiter
from core.security.auth import get_current_user
from users.models import UserModel
from boards.schemas import (
    BoardCreate,
    BoardUpdate,
    BoardResponse,
    BoardPinsResponse,
)
from boards.service import BoardService
from core.dependencies import get_board_service

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_new_board(
    request: Request,
    data: BoardCreate,
    current_user: UserModel = Depends(get_current_user),
    board_service: BoardService = Depends(get_board_service),
) -> BoardResponse:
    return await board_service.create_board(current_user, data)


@router.get("/")
@limiter.limit("10/minute")
async def list_boards(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    board_service: BoardService = Depends(get_board_service),
) -> List[BoardResponse]:
    return await board_service.get_user_boards(current_user.id)


@router.get("/{board_id}")
@limiter.limit("10/minute")
async def read_board(
    request: Request,
    board_id: uuid.UUID,
    board_service: BoardService = Depends(get_board_service),
) -> BoardPinsResponse:
    return await board_service.get_board_by_id(board_id)


@router.patch("/{board_id}")
@limiter.limit("5/minute")
async def patch_board(
    request: Request,
    board_id: uuid.UUID,
    data: BoardUpdate,
    current_user: UserModel = Depends(get_current_user),
    board_service: BoardService = Depends(get_board_service),
) -> BoardResponse:
    return await board_service.update_board(board_id, data, current_user)


@router.post("/{board_id}/pins/{pin_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def add_pin(
    request: Request,
    board_id: uuid.UUID,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    board_service: BoardService = Depends(get_board_service),
):
    await board_service.add_pin_to_board(board_id, pin_id, current_user)


@router.delete("/{board_id}/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def remove_pin(
    request: Request,
    board_id: uuid.UUID,
    pin_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    board_service: BoardService = Depends(get_board_service),
):
    return await board_service.remove_pin_from_board(board_id, pin_id, current_user)
