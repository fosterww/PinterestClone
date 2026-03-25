import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.auth.service import register_user, authenticate_user
from src.users.schemas import UserCreate
from src.core.security import verify_password


@pytest.mark.asyncio
async def test_register_user(db_session: AsyncSession):
    user_data = UserCreate(
        username="auth_svc_tester",
        email="auth_svc@example.com",
        password="securepassword",
    )
    user = await register_user(db_session, user_data)

    assert user is not None
    assert user.username == "auth_svc_tester"
    assert user.email == "auth_svc@example.com"
    assert verify_password("securepassword", user.hashed_password)


@pytest.mark.asyncio
async def test_register_user_duplicate_error(db_session: AsyncSession):
    user_data = UserCreate(
        username="auth_svc_dup",
        email="auth_svc_dup@example.com",
        password="securepassword",
    )
    await register_user(db_session, user_data)

    with pytest.raises(HTTPException) as excinfo:
        await register_user(db_session, user_data)

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "username already taken"


@pytest.mark.asyncio
async def test_authenticate_user_success(db_session: AsyncSession):
    user_data = UserCreate(
        username="auth_svc_login",
        email="auth_svc_login@example.com",
        password="right_password",
    )
    await register_user(db_session, user_data)

    user = await authenticate_user(db_session, "auth_svc_login", "right_password")
    assert user is not None
    assert user.username == "auth_svc_login"


@pytest.mark.asyncio
async def test_authenticate_user_invalid(db_session: AsyncSession):
    user_data = UserCreate(
        username="auth_svc_login_fail",
        email="auth_svc_login_fail@example.com",
        password="right_password",
    )
    await register_user(db_session, user_data)

    user = await authenticate_user(db_session, "auth_svc_login_fail", "wrong_password")
    assert user is None

    user = await authenticate_user(db_session, "non_existent_user", "right_password")
    assert user is None
