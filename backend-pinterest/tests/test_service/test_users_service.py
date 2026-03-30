import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.auth.service import AuthService
from src.users.repository import UserRepository
from src.users.schemas import UserCreate, UserUpdate
from src.auth.repository import AuthRepository


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


@pytest.fixture
def user_repo(db_session: AsyncSession):
    return UserRepository(db_session)


@pytest.fixture
def base_user_data():
    return UserCreate(
        username="user_svc_tester",
        email="users_svc@example.com",
        password="securepassword",
    )


@pytest.mark.asyncio
async def test_get_user_by_id(
    auth_svc: AuthService, user_repo: UserRepository, base_user_data: UserCreate
):
    created_user = await auth_svc.register_user(base_user_data)

    fetched_user = await user_repo.get_user_by_id(created_user.id)
    assert fetched_user is not None
    assert fetched_user.id == created_user.id
    assert fetched_user.username == "user_svc_tester"

    missing_user = await user_repo.get_user_by_id(uuid.uuid4())
    assert missing_user is None


@pytest.mark.asyncio
async def test_update_user(
    auth_svc: AuthService, user_repo: UserRepository, base_user_data: UserCreate
):
    base_user_data.username = "user_svc_updater"
    base_user_data.email = "updater@example.com"
    user = await auth_svc.register_user(base_user_data)

    update_data = UserUpdate(full_name="Updated Name", bio="New bio...")
    updated_user = await user_repo.update_user(user.id, update_data)

    assert updated_user.id == user.id
    assert updated_user.full_name == "Updated Name"
    assert updated_user.bio == "New bio..."

    fetched_user = await user_repo.get_user_by_id(user.id)
    assert fetched_user.full_name == "Updated Name"
    assert fetched_user.bio == "New bio..."
