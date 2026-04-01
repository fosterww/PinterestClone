import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from src.auth.service import AuthService
from src.users.schemas import UserCreate
from src.core.security.security import verify_password
from src.users.repository import UserRepository
from src.auth.repository import AuthRepository


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


@pytest.mark.asyncio
async def test_register_user(auth_svc: AuthService):
    user_data = UserCreate(
        username="auth_svc_tester",
        email="auth_svc@example.com",
        password="securepassword",
    )
    user = await auth_svc.register_user(user_data)

    assert user is not None
    assert user.username == "auth_svc_tester"
    assert user.email == "auth_svc@example.com"
    assert verify_password("securepassword", user.hashed_password)


@pytest.mark.asyncio
async def test_register_user_duplicate_error(auth_svc: AuthService):
    user_data = UserCreate(
        username="auth_svc_dup",
        email="auth_svc_dup@example.com",
        password="securepassword",
    )
    await auth_svc.register_user(user_data)

    with pytest.raises(HTTPException) as excinfo:
        await auth_svc.register_user(user_data)

    assert excinfo.value.status_code == 409
    assert "already taken" in excinfo.value.detail


@pytest.mark.asyncio
async def test_authenticate_user_success(auth_svc: AuthService):
    user_data = UserCreate(
        username="auth_svc_login",
        email="auth_svc_login@example.com",
        password="right_password",
    )
    await auth_svc.register_user(user_data)

    user = await auth_svc.authenticate_user("auth_svc_login", "right_password")
    assert user is not None
    assert user.username == "auth_svc_login"


@pytest.mark.asyncio
async def test_authenticate_user_invalid(auth_svc: AuthService):
    user_data = UserCreate(
        username="auth_svc_login_fail",
        email="auth_svc_login_fail@example.com",
        password="right_password",
    )
    await auth_svc.register_user(user_data)

    user = await auth_svc.authenticate_user("auth_svc_login_fail", "wrong_password")
    assert user is None

    user = await auth_svc.authenticate_user("non_existent_user", "right_password")
    assert user is None
