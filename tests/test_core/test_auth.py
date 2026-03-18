import pytest
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.core.auth import get_current_user
from src.core.security import create_access_token
from src.core.config import settings
from src.auth.service import register_user
from src.users.schemas import UserCreate


@pytest.mark.asyncio
async def test_get_current_user_success(db_session: AsyncSession):
    user_data = UserCreate(
        username="auth_core_user",
        email="auth_core@example.com",
        password="password123"
    )
    created_user = await register_user(db_session, user_data)

    token = create_access_token({"sub": created_user.username})
    user = await get_current_user(token=token, db=db_session)

    assert user is not None
    assert user.id == created_user.id
    assert user.username == "auth_core_user"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session: AsyncSession):
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token="totally.invalid.token", db=db_session)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_no_subject(db_session: AsyncSession):
    token = jwt.encode({"data": "no_sub"}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token=token, db=db_session)
    assert excinfo.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_nonexistent_user(db_session: AsyncSession):
    token = create_access_token({"sub": "ghost_user_does_not_exist"})
    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token=token, db=db_session)
    assert excinfo.value.status_code == 401
