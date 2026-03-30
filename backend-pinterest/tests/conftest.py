import pytest
import pytest_asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from src.database import Base, get_db
from src.main import app
from src.core.limiter import limiter
from src.core.dependencies import get_session_service

limiter.enabled = False


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        nested = await connection.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def reopen_nested(session_sync, transaction_sync):
            nonlocal nested
            if not nested.is_active:
                nested = connection.sync_connection.begin_nested()

        yield session

        await session.close()
        await transaction.rollback()


@pytest.fixture
def mock_session_service():
    class MockSessionService:
        async def create_session(self, user_id):
            return "mock_session_id"

        async def validate_session(self, session_id):
            return "mock_user_id"

        async def delete_session(self, session_id):
            pass

        async def refresh_session_ttl(self, session_id):
            pass

    return MockSessionService()


@pytest.fixture
def mock_cache_service():
    class MockCacheService:
        async def get_pattern(self, pattern):
            return []

        async def set(self, key, value, ttl=None):
            pass

        async def delete_pattern(self, pattern):
            pass

    return MockCacheService()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, mock_session_service
) -> AsyncGenerator[AsyncClient, None]:

    async def override_get_db():
        yield db_session

    def override_get_session_service():
        return mock_session_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_service] = override_get_session_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with (
        patch("src.pins.router.index_image_task.delay") as mock_index,
        patch("src.pins.router.delete_image_task.delay") as mock_delete,
    ):
        yield mock_index, mock_delete
