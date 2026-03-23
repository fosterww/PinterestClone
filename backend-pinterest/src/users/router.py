from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.limiter import limiter
from src.database import get_db
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.users.service import update_user
from src.users.schemas import UserUpdate, UserResponse

router = APIRouter()


@router.get("/me")
@limiter.limit("10/minute")
async def read_current_user(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    return current_user


@router.patch("/me")
@limiter.limit("5/minute")
async def update_current_user(
    request: Request,
    data: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    updated = await update_user(db, current_user, data)
    return updated
