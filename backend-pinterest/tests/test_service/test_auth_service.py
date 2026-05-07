import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.repository import AuthRepository
from auth.service import AuthService
from core.security.security import verify_password
from users.repository import UserRepository
from users.schemas import UserCreate


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


@pytest.mark.asyncio
async def test_authenticate_google_only_user_returns_none(auth_svc: AuthService):
    google_user = await auth_svc.get_or_create_google_user(
        {
            "sub": "google-only-sub",
            "email": "google_only@example.com",
            "name": "Google Only",
            "picture": "https://example.com/avatar.png",
        }
    )

    user = await auth_svc.authenticate_user(google_user.username, "any_password")

    assert user is None


def make_auth_svc_with_mocks():
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    session_service = SimpleNamespace(
        create_session=AsyncMock(return_value="mock_session_id"),
        validate_session=AsyncMock(return_value=True),
        delete_session=AsyncMock(),
    )
    user_repo = SimpleNamespace()
    auth_repo = SimpleNamespace(
        save_refresh_token=AsyncMock(),
        get_refresh_token=AsyncMock(),
    )
    service = AuthService(db, session_service, user_repo, auth_repo)
    return service, db, session_service, auth_repo


@pytest.mark.asyncio
async def test_create_user_session_and_tokens_commits():
    auth_svc, db, session_service, auth_repo = make_auth_svc_with_mocks()
    user = SimpleNamespace(id=uuid.uuid4(), username="session_user")

    tokens = await auth_svc.create_user_session_and_tokens(user)

    assert tokens["token_type"] == "bearer"
    assert tokens["session_id"] == "mock_session_id"
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    session_service.create_session.assert_awaited_once_with(user.id)
    auth_repo.save_refresh_token.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_user_session_and_tokens_rolls_back_on_error():
    auth_svc, db, _, auth_repo = make_auth_svc_with_mocks()
    auth_repo.save_refresh_token.side_effect = RuntimeError("save failed")
    user = SimpleNamespace(id=uuid.uuid4(), username="session_user")

    with pytest.raises(HTTPException) as excinfo:
        await auth_svc.create_user_session_and_tokens(user)

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Failed to create user session"
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_user_token_commits():
    auth_svc, db, session_service, auth_repo = make_auth_svc_with_mocks()
    user = SimpleNamespace(id=uuid.uuid4(), username="refresh_user")
    token = SimpleNamespace(
        token="old_refresh_token",
        session_id="existing_session_id",
        is_expired=False,
        user=user,
    )
    auth_repo.get_refresh_token.return_value = token

    tokens = await auth_svc.refresh_user_token("old_refresh_token")

    assert tokens["token_type"] == "bearer"
    assert "access_token" in tokens
    assert token.token == tokens["refresh_token"]
    assert token.session_id == "existing_session_id"
    session_service.validate_session.assert_awaited_once_with("existing_session_id")
    auth_repo.save_refresh_token.assert_awaited_once_with(token)
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_user_token_rolls_back_on_error():
    auth_svc, db, _, auth_repo = make_auth_svc_with_mocks()
    user = SimpleNamespace(id=uuid.uuid4(), username="refresh_user")
    token = SimpleNamespace(
        token="old_refresh_token",
        session_id="existing_session_id",
        is_expired=False,
        user=user,
    )
    auth_repo.get_refresh_token.return_value = token
    auth_repo.save_refresh_token.side_effect = RuntimeError("save failed")

    with pytest.raises(HTTPException) as excinfo:
        await auth_svc.refresh_user_token("old_refresh_token")

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Failed to refresh token"
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
