import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exception import NotFoundError, ForbiddenError
from core.security.session import SessionService
from boards.models import BoardModel
from users.models import UserModel
from boards.schemas import BoardCreate, BoardUpdate, BoardResponse
from boards.repository import BoardRepository
from pins.service import PinService


class BoardService:
    def __init__(
        self,
        db: AsyncSession,
        session_service: SessionService,
        board_repository: BoardRepository,
        pin_service: PinService,
    ) -> None:
        self.db = db
        self.session_service = session_service
        self.board_repository = board_repository
        self.pin_service = pin_service

    async def create_board(self, owner: UserModel, data: BoardCreate) -> BoardResponse:
        return await self.board_repository.create(owner, data)

    async def get_user_boards(self, user_id: uuid.UUID) -> list[BoardResponse]:
        return await self.board_repository.get_by_owner_id(user_id)

    async def get_board_by_id(self, board_id: uuid.UUID) -> BoardModel | None:
        result = await self.board_repository.get_by_id(board_id)
        if result is None:
            raise NotFoundError("Board not found")
        return result

    async def update_board(
        self,
        board_id: uuid.UUID,
        data: BoardUpdate,
        current_user: UserModel,
    ) -> BoardResponse:
        board = await self.board_repository.get_by_id(board_id)
        if board is None:
            raise NotFoundError("Board not found")
        if board.owner_id != current_user.id:
            raise ForbiddenError("Not the board owner")
        return await self.board_repository.update_board(board, data)

    async def add_pin_to_board(
        self,
        board_id: uuid.UUID,
        pin_id: uuid.UUID,
        current_user: UserModel,
    ) -> None:
        board = await self.board_repository.get_by_id(board_id)
        pin = await self.pin_service.get_pin_by_id(pin_id)
        if board is None:
            raise NotFoundError("Board not found")
        if pin is None:
            raise NotFoundError("Pin not found")
        if board.owner_id != current_user.id:
            raise ForbiddenError("Not the board owner")
        return await self.board_repository.add_pin_to_board(board, pin)

    async def remove_pin_from_board(
        self,
        board_id: uuid.UUID,
        pin_id: uuid.UUID,
        current_user: UserModel,
    ) -> None:
        board = await self.board_repository.get_by_id(board_id)
        pin = await self.pin_service.get_pin_by_id(pin_id)
        if board is None:
            raise NotFoundError("Board not found")
        if pin is None:
            raise NotFoundError("Pin not found")
        if board.owner_id != current_user.id:
            raise ForbiddenError("Not the board owner")
        return await self.board_repository.remove_pin_from_board(board, pin)
