from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.core.auth import get_current_user
from src.users.models import UserModel
from src.users.service import update_user
from src.users.schemas import UserUpdate, UserResponse

router = APIRouter()


@router.get("/me")
async def read_current_user(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    return current_user


@router.patch("/me")
async def update_current_user(
    data: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    updated = await update_user(db, current_user, data)
    return updated
