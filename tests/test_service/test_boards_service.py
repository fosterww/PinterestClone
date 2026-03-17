import pytest
import pytest_asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
    
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select
from src.boards.models import BoardModel

from src.auth.service import register_user
from src.users.schemas import UserCreate
from src.pins.schemas import PinCreate
from src.pins.service import create_pin
from src.boards.schemas import BoardCreate, BoardUpdate
from src.boards.service import (
    create_board, get_user_boards, get_board_by_id, 
    update_board, add_pin_to_board, remove_pin_from_board
)

@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="board_svc_tester",
        email="board_svc@example.com",
        password="securepassword"
    )
    return await register_user(db_session, user_data)

@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="board_svc_other",
        email="board_svc_other@example.com",
        password="securepassword"
    )
    return await register_user(db_session, user_data)

@pytest_asyncio.fixture
async def sample_pin(db_session: AsyncSession, sample_user):
    pin_data = PinCreate(title="Test Pin for Board")
    return await create_pin(db_session, sample_user, pin_data, "http://image.jpg")

@pytest.mark.asyncio
async def test_create_and_get_board(db_session: AsyncSession, sample_user):
    board_data = BoardCreate(title="My Board", description="Board desc")
    board = await create_board(db_session, sample_user, board_data)
    
    assert board is not None
    assert board.title == "My Board"
    assert board.owner_id == sample_user.id
    
    fetched_board = await get_board_by_id(db_session, board.id)
    assert fetched_board is not None
    assert fetched_board.id == board.id

@pytest.mark.asyncio
async def test_get_user_boards(db_session: AsyncSession, sample_user):
    await create_board(db_session, sample_user, BoardCreate(title="Board 1"))
    await create_board(db_session, sample_user, BoardCreate(title="Board 2"))
    
    boards = await get_user_boards(db_session, sample_user.id)
    assert len(boards) == 2
    assert boards[0].title == "Board 1"
    assert boards[1].title == "Board 2"

@pytest.mark.asyncio
async def test_update_board_success_and_forbidden(db_session: AsyncSession, sample_user, another_user):
    board = await create_board(db_session, sample_user, BoardCreate(title="Old Title"))
    
    update_data = BoardUpdate(title="New Title")
    updated_board = await update_board(db_session, board, update_data, sample_user)
    assert updated_board.title == "New Title"
    
    with pytest.raises(HTTPException) as excinfo:
        await update_board(db_session, board, update_data, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"

@pytest.mark.asyncio
async def test_board_pin_associations(db_session: AsyncSession, sample_user, sample_pin):
    board = await create_board(db_session, sample_user, BoardCreate(title="Pin Board"))
    
    await add_pin_to_board(db_session, board, sample_pin, sample_user)

    board_id = board.id
    
    result = await db_session.execute(
        select(BoardModel)
        .where(BoardModel.id == board_id)
        .options(joinedload(BoardModel.user), selectinload(BoardModel.pins))
    )
    fetched_board = result.scalar_one_or_none()
    assert len(fetched_board.pins) == 1
    assert fetched_board.pins[0].id == sample_pin.id
    
    await remove_pin_from_board(db_session, board, sample_pin, sample_user)
    
    db_session.expire_all()
    result = await db_session.execute(
        select(BoardModel)
        .where(BoardModel.id == board_id)
        .options(joinedload(BoardModel.user), selectinload(BoardModel.pins))
    )
    fetched_board_after = result.scalar_one_or_none()
    assert fetched_board_after is not None
    assert len(fetched_board_after.pins) == 0

@pytest.mark.asyncio
async def test_board_pin_associations_forbidden(db_session: AsyncSession, sample_user, another_user, sample_pin):
    board = await create_board(db_session, sample_user, BoardCreate(title="Pin Board 2"))
    
    with pytest.raises(HTTPException) as excinfo:
        await add_pin_to_board(db_session, board, sample_pin, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"
    
    await add_pin_to_board(db_session, board, sample_pin, sample_user)
    
    with pytest.raises(HTTPException) as excinfo:
        await remove_pin_from_board(db_session, board, sample_pin, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"
