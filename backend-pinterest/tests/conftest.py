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

from database import Base, get_db
from main import app
from core.security.limiter import limiter
from core.dependencies import (
    get_session_service,
    get_s3_service,
    get_comment_filter,
)
from pins.repository.pin import PinRepository
from pins.service.pin import PinService
from tags.service import TagService
from pins.service.comment import CommentService
from pins.repository.comment import CommentRepository
from pins.service.discovery import DiscoveryService
from pins.repository.discover import DiscoverRepository


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
    from unittest.mock import AsyncMock, MagicMock

    class MockCacheService:
        def __init__(self):
            self.redis = MagicMock()
            self.redis.lrem = AsyncMock()
            self.redis.lpush = AsyncMock()
            self.redis.ltrim = AsyncMock()
            self.redis.lrange = AsyncMock(return_value=[])

        async def get_pattern(self, pattern):
            return []

        async def set(self, key, value, ttl=None):
            pass

        async def delete_pattern(self, pattern):
            pass

    return MockCacheService()


@pytest.fixture
def mock_s3_service():
    class MockS3Service:
        async def upload_image_to_s3(self, image):
            return "http://mock-s3-url.com/image.jpg"

    return MockS3Service()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, mock_session_service, mock_s3_service, mock_cache_service
) -> AsyncGenerator[AsyncClient, None]:

    async def override_get_db():
        yield db_session

    def override_get_session_service():
        return mock_session_service

    def override_get_cache_service():
        return mock_cache_service

    def override_get_s3_service():
        return mock_s3_service

    def override_get_gemini_service():
        class MockGeminiService:
            def generate_tags(self, image_bytes, title, description):
                return ["mock_tag1", "mock_tag2"]

        return MockGeminiService()

    def override_get_comment_filter():
        class MockCommentFilter:
            def filter_comment_text(self, text: str) -> bool:
                return True

        return MockCommentFilter()

    from core.dependencies import get_cache_service, get_gemini_service

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_service] = override_get_session_service
    app.dependency_overrides[get_cache_service] = override_get_cache_service
    app.dependency_overrides[get_s3_service] = override_get_s3_service
    app.dependency_overrides[get_gemini_service] = override_get_gemini_service
    app.dependency_overrides[get_comment_filter] = override_get_comment_filter

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with (
        patch("pins.task.index_image_task.delay") as mock_index,
        patch("pins.task.delete_image_task.delay") as mock_delete,
    ):
        yield mock_index, mock_delete


@pytest.fixture
def comment_filter():
    class MockCommentFilter:
        def filter_comment_text(self, text: str) -> bool:
            return "stupid" not in text.lower() and "toxic" not in text.lower()

    return MockCommentFilter()


@pytest.fixture(autouse=True)
def mock_pil_image_open():
    from unittest.mock import MagicMock

    mock_img = MagicMock()
    mock_img.size = (100, 100)
    mock_img.__enter__ = MagicMock(return_value=mock_img)
    mock_img.__exit__ = MagicMock(return_value=False)

    with patch("pins.service.pin.Image.open", return_value=mock_img):
        yield


@pytest.fixture
def mock_gemini_service():
    class MockGeminiService:
        def generate_tags(self, image_bytes, title, description):
            return ["mock_tag_fixture"]

    return MockGeminiService()


@pytest.fixture
def pin_svc(
    db_session: AsyncSession,
    mock_s3_service,
    mock_gemini_service,
):
    repo = PinRepository(db_session)
    tag_service = TagService(db_session)
    return PinService(
        db_session,
        repo,
        tag_service,
        mock_s3_service,
        mock_gemini_service,
    )


@pytest.fixture
def comment_svc(
    db_session: AsyncSession,
    comment_filter,
):
    pin_repo = PinRepository(db_session)
    comment_repo = CommentRepository(db_session)
    return CommentService(pin_repo, comment_repo, comment_filter)


@pytest.fixture
def discovery_svc(
    db_session: AsyncSession,
    mock_cache_service,
):
    pin_repo = PinRepository(db_session)
    discover_repo = DiscoverRepository(db_session)
    return DiscoveryService(pin_repo, discover_repo, mock_cache_service)
