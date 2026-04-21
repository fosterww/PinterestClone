import uuid

from boards.repository import BoardRepository
from pins.repository.pin import PinRepository
from search.schemas import BoardSearchResponse, SearchResponse, SearchTarget
from users.repository import UserRepository
from users.schemas import UserSearchResponse


class SearchService:
    def __init__(
        self,
        user_repository: UserRepository,
        board_repository: BoardRepository,
        pin_repository: PinRepository,
    ) -> None:
        self.user_repository = user_repository
        self.board_repository = board_repository
        self.pin_repository = pin_repository

    async def search(
        self,
        query: str,
        target: SearchTarget,
        limit: int = 20,
        offset: int = 0,
        current_user_id: uuid.UUID | None = None,
    ) -> SearchResponse:
        clean_query = query.strip()
        normalized_limit = min(max(limit, 1), 20)
        normalized_offset = max(offset, 0)

        if not clean_query:
            return SearchResponse(query="", target=target)

        users: list[UserSearchResponse] = []
        boards: list[BoardSearchResponse] = []
        pins = []

        if target in {SearchTarget.all, SearchTarget.users}:
            matched_users = await self.user_repository.search_public_profiles(
                clean_query, normalized_limit, normalized_offset
            )
            users = [UserSearchResponse.model_validate(user) for user in matched_users]

        if target in {SearchTarget.all, SearchTarget.boards}:
            matched_boards = await self.board_repository.search_boards(
                clean_query, normalized_limit, normalized_offset, current_user_id
            )
            boards = [
                BoardSearchResponse(
                    id=board.id,
                    title=board.title,
                    description=board.description,
                    visibility=board.visibility,
                    created_at=board.created_at,
                    owner_username=board.user.username,
                )
                for board in matched_boards
            ]

        if target in {SearchTarget.all, SearchTarget.pins}:
            matched_pins = await self.pin_repository.get_pins(
                offset=normalized_offset,
                limit=normalized_limit,
                search=clean_query,
                tags=[],
            )
            pins = [pin for pin in matched_pins]

        return SearchResponse(
            query=clean_query,
            target=target,
            users=users,
            boards=boards,
            pins=pins,
        )
