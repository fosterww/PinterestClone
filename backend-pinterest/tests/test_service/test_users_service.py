import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.auth.service import register_user
from src.users.schemas import UserCreate, UserUpdate
from src.users.service import get_user_by_id, update_user


@pytest.fixture
def base_user_data():
    return UserCreate(
        username="user_svc_tester",
        email="users_svc@example.com",
        password="securepassword",
    )


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession, base_user_data: UserCreate):
    created_user = await register_user(db_session, base_user_data)

    fetched_user = await get_user_by_id(db_session, created_user.id)
    assert fetched_user is not None
    assert fetched_user.id == created_user.id
    assert fetched_user.username == "user_svc_tester"

    missing_user = await get_user_by_id(db_session, uuid.uuid4())
    assert missing_user is None


@pytest.mark.asyncio
async def test_update_user(db_session: AsyncSession, base_user_data: UserCreate):
    base_user_data.username = "user_svc_updater"
    base_user_data.email = "updater@example.com"
    user = await register_user(db_session, base_user_data)

    update_data = UserUpdate(full_name="Updated Name", bio="New bio...")
    updated_user = await update_user(db_session, user, update_data)

    assert updated_user.id == user.id
    assert updated_user.full_name == "Updated Name"
    assert updated_user.bio == "New bio..."

    fetched_user = await get_user_by_id(db_session, user.id)
    assert fetched_user.full_name == "Updated Name"
    assert fetched_user.bio == "New bio..."
