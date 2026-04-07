from fastapi import APIRouter, Depends, Request

from core.security.limiter import limiter
from core.security.auth import get_current_user
from users.models import UserModel
from users.schemas import UserUpdate, UserResponse
from core.dependencies import get_user_repository
from users.repository import UserRepository

router = APIRouter()


@router.get("/")
@limiter.limit("10/minute")
async def read_current_user(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    return current_user


@router.patch("/")
@limiter.limit("5/minute")
async def update_current_user(
    request: Request,
    data: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    return await user_repository.update_user(current_user.id, data)
