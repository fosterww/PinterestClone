import pytest

from fastapi import UploadFile
import io


import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select
from src.boards.models import BoardModel

from src.users.schemas import UserCreate
from src.pins.schemas import PinCreate
from src.boards.schemas import BoardCreate, BoardUpdate

from src.auth.service import AuthService
from src.pins.service import PinService
from src.pins.repository import PinRepository
from src.boards.service import BoardService
from src.boards.repository import BoardRepository
from src.users.repository import UserRepository
from src.auth.repository import AuthRepository
from src.tags.service import TagService


def mock_image_file():
    content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c\x60\x00\x02\x00\x00\x05\x00\x01^\xf3*:\x00\x00\x00\x00IEND\xaeB`\x82"
    return UploadFile(
        filename="test.png",
        file=io.BytesIO(content),
        headers={"content-type": "image/png"},
    )


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


@pytest.fixture
def pin_svc(db_session: AsyncSession, mock_cache_service, mock_s3_service):
    repo = PinRepository(db_session)
    tag_service = TagService(db_session)
    return PinService(
        db_session, mock_cache_service, repo, tag_service, mock_s3_service
    )


@pytest.fixture
def board_svc(db_session: AsyncSession, mock_session_service, pin_svc: PinService):
    repo = BoardRepository(db_session)
    return BoardService(db_session, mock_session_service, repo, pin_svc)


@pytest_asyncio.fixture
async def sample_user(auth_svc: AuthService):
    user_data = UserCreate(
        username="board_svc_tester",
        email="board_svc@example.com",
        password="securepassword",
    )
    return await auth_svc.register_user(user_data)


@pytest_asyncio.fixture
async def another_user(auth_svc: AuthService):
    user_data = UserCreate(
        username="board_svc_other",
        email="board_svc_other@example.com",
        password="securepassword",
    )
    return await auth_svc.register_user(user_data)


@pytest_asyncio.fixture
async def sample_pin(pin_svc: PinService, sample_user):
    pin_data = PinCreate(title="Test Pin for Board")
    return await pin_svc.create_pin(mock_image_file(), sample_user, pin_data)


@pytest.mark.asyncio
async def test_create_and_get_board(board_svc: BoardService, sample_user):
    board_data = BoardCreate(title="My Board", description="Board desc")
    board = await board_svc.create_board(sample_user, board_data)

    assert board is not None
    assert board.title == "My Board"
    assert board.user.id == sample_user.id

    fetched_board = await board_svc.get_board_by_id(board.id)
    assert fetched_board is not None
    assert fetched_board.id == board.id


@pytest.mark.asyncio
async def test_get_user_boards(board_svc: BoardService, sample_user):
    await board_svc.create_board(sample_user, BoardCreate(title="Board 1"))
    await board_svc.create_board(sample_user, BoardCreate(title="Board 2"))

    boards = await board_svc.get_user_boards(sample_user.id)
    assert len(boards) == 2
    titles = {b.title for b in boards}
    assert titles == {"Board 1", "Board 2"}


@pytest.mark.asyncio
async def test_update_board_success_and_forbidden(
    board_svc: BoardService, sample_user, another_user
):
    board = await board_svc.create_board(sample_user, BoardCreate(title="Old Title"))

    update_data = BoardUpdate(title="New Title")
    updated_board = await board_svc.update_board(board.id, update_data, sample_user)
    assert updated_board.title == "New Title"

    with pytest.raises(HTTPException) as excinfo:
        await board_svc.update_board(board.id, update_data, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"


@pytest.mark.asyncio
async def test_board_pin_associations(
    db_session: AsyncSession, board_svc: BoardService, sample_user, sample_pin
):
    board = await board_svc.create_board(sample_user, BoardCreate(title="Pin Board"))

    await board_svc.add_pin_to_board(board.id, sample_pin.id, sample_user)

    board_id = board.id

    result = await db_session.execute(
        select(BoardModel)
        .where(BoardModel.id == board_id)
        .options(joinedload(BoardModel.user), selectinload(BoardModel.pins))
    )
    fetched_board = result.scalar_one_or_none()
    assert len(fetched_board.pins) == 1
    assert fetched_board.pins[0].id == sample_pin.id

    await board_svc.remove_pin_from_board(board.id, sample_pin.id, sample_user)

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
async def test_board_pin_associations_forbidden(
    board_svc: BoardService, sample_user, another_user, sample_pin
):
    board = await board_svc.create_board(sample_user, BoardCreate(title="Pin Board 2"))

    with pytest.raises(HTTPException) as excinfo:
        await board_svc.add_pin_to_board(board.id, sample_pin.id, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"

    await board_svc.add_pin_to_board(board.id, sample_pin.id, sample_user)

    with pytest.raises(HTTPException) as excinfo:
        await board_svc.remove_pin_from_board(board.id, sample_pin.id, another_user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Not the board owner"
