import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from auth.service import AuthService
from users.repository import UserRepository
from users.schemas import UserCreate, UserUpdate
from auth.repository import AuthRepository


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


@pytest_asyncio.fixture
async def first_user(auth_svc: AuthService):
    return await auth_svc.register_user(
        UserCreate(
            username="follow_user_1",
            email="follow_user_1@example.com",
            password="securepassword",
        )
    )


@pytest_asyncio.fixture
async def second_user(auth_svc: AuthService):
    return await auth_svc.register_user(
        UserCreate(
            username="follow_user_2",
            email="follow_user_2@example.com",
            password="securepassword",
        )
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


@pytest.mark.asyncio
async def test_follow_user_and_status(
    user_repo: UserRepository, first_user, second_user
):
    await user_repo.follow_user(first_user.id, second_user.username)

    assert await user_repo.is_following(first_user.id, second_user.username) is True
    assert await user_repo.is_following(second_user.id, first_user.username) is False


@pytest.mark.asyncio
async def test_get_followed_user_ids(
    user_repo: UserRepository, first_user, second_user
):
    await user_repo.follow_user(first_user.id, second_user.username)

    followed_ids = await user_repo.get_followed_user_ids(first_user.id)
    assert followed_ids == [second_user.id]


@pytest.mark.asyncio
async def test_followers_and_following_counts(
    user_repo: UserRepository, first_user, second_user
):
    await user_repo.follow_user(first_user.id, second_user.username)

    followers_count = await user_repo.get_followers_count(second_user.id)
    following_count = await user_repo.get_following_count(first_user.id)

    assert followers_count == 1
    assert following_count == 1


@pytest.mark.asyncio
async def test_unfollow_user(user_repo: UserRepository, first_user, second_user):
    await user_repo.follow_user(first_user.id, second_user.username)
    await user_repo.unfollow_user(first_user.id, second_user.username)

    assert await user_repo.is_following(first_user.id, second_user.username) is False
    assert await user_repo.get_followers_count(second_user.id) == 0
    assert await user_repo.get_following_count(first_user.id) == 0


@pytest.mark.asyncio
async def test_duplicate_follow_raises_conflict(
    user_repo: UserRepository, first_user, second_user
):
    await user_repo.follow_user(first_user.id, second_user.username)

    with pytest.raises(HTTPException) as excinfo:
        await user_repo.follow_user(first_user.id, second_user.username)

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_self_follow_raises_conflict(user_repo: UserRepository, first_user):
    with pytest.raises(HTTPException) as excinfo:
        await user_repo.follow_user(first_user.id, first_user.username)

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_unfollow_missing_relationship_raises_not_found(
    user_repo: UserRepository, first_user, second_user
):
    with pytest.raises(HTTPException) as excinfo:
        await user_repo.unfollow_user(first_user.id, second_user.username)

    assert excinfo.value.status_code == 404
