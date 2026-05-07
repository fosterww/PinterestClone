from fastapi import APIRouter, Depends, Request

from boards.schemas import BoardResponse
from boards.service import BoardService
from core.dependencies import get_board_service, get_user_service
from core.security.auth import get_current_user, get_optional_current_user
from core.security.limiter import limiter
from users.models import UserModel
from users.schemas import PublicUserResponse, UserResponse, UserUpdate
from users.service import UserService

router = APIRouter()


@router.get("/")
@limiter.limit("10/minute")
async def read_current_user(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """Get the current user."""
    return current_user


@router.patch("/")
@limiter.limit("5/minute")
async def update_current_user(
    request: Request,
    data: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update current user."""
    return await user_service.update_current_user(current_user.id, data)


@router.get("/{username}")
@limiter.limit("10/minute")
async def read_public_user(
    request: Request,
    username: str,
    user_service: UserService = Depends(get_user_service),
) -> PublicUserResponse:
    """Get a public user profile by username."""
    return await user_service.get_public_user_profile(username)


@router.get("/{username}/boards")
@limiter.limit("10/minute")
async def read_user_boards(
    request: Request,
    username: str,
    current_user: UserModel | None = Depends(get_optional_current_user),
    board_service: BoardService = Depends(get_board_service),
) -> list[BoardResponse]:
    """Get boards visible to the requester for the given user."""
    return await board_service.get_visible_boards_for_user(username, current_user)


@router.get("/{username}/followers")
@limiter.limit("10/minute")
async def read_user_followers(
    request: Request,
    username: str,
    user_service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    """Get followers for the given user."""
    return await user_service.get_followers(username)


@router.get("/{username}/following")
@limiter.limit("10/minute")
async def read_user_following(
    request: Request,
    username: str,
    user_service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    """Get following for the given user."""
    return await user_service.get_following(username)


@router.post("/{username}/follow")
@limiter.limit("10/minute")
async def follow_user(
    request: Request,
    username: str,
    current_user: UserModel = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """Follow the given user."""
    await user_service.follow_user(current_user.id, username)
    return {"detail": "Followed successfully"}


@router.delete("/{username}/unfollow")
@limiter.limit("10/minute")
async def unfollow_user(
    request: Request,
    username: str,
    current_user: UserModel = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """Unfollow the given user."""
    await user_service.unfollow_user(current_user.id, username)
    return {"detail": "Unfollowed successfully"}
