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

from auth.repository import AuthRepository
from boards.repository import BoardRepository
from auth.service import AuthService
from boards.service import BoardService
from database import Base, get_db
from main import app
from core.security.limiter import limiter
from core.dependencies import (
    get_session_service,
    get_s3_service,
    get_comment_filter,
)
from notification.service import NotificationService
from pins.repository.pin import PinRepository
from pins.service.pin import PinService
from tags.service import TagService
from pins.service.comment import CommentService
from pins.repository.comment import CommentRepository
from pins.service.discovery import DiscoveryService
from pins.repository.discover import DiscoverRepository
from users.repository import UserRepository
from users.service import UserService


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

        async def get(self, key):
            return None

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

        async def upload_bytes_to_s3(
            self,
            content: bytes,
            content_type: str = "image/png",
            folder: str = "generated",
            extension: str = "png",
        ):
            return f"http://mock-s3-url.com/{folder}/image.{extension}"

        async def download_bytes_from_url(self, url: str):
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c"
                b"\x60\x00\x02\x00\x00\x05\x00\x01^\xf3*:\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        async def delete_bytes_from_s3(self, url: str):
            pass

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

            def generate_description(self, image_bytes, title):
                return f"AI description for {title}"

        return MockGeminiService()

    def override_get_comment_filter():
        class MockCommentFilter:
            def filter_comment_text(self, text: str) -> bool:
                return True

        return MockCommentFilter()

    def override_get_openai_client():
        class MockOpenAIClient:
            def generate_image(
                self,
                prompt: str,
                number_of_images: int = 1,
                aspect_ratio: str | None = "1:1",
            ):
                one_pixel_png = (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUA"
                    "AV7zKjoAAAAASUVORK5CYII="
                )
                return [{"b64_json": one_pixel_png} for _ in range(number_of_images)]

        return MockOpenAIClient()

    from core.dependencies import (
        get_cache_service,
        get_gemini_service,
        get_openai_client,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_service] = override_get_session_service
    app.dependency_overrides[get_cache_service] = override_get_cache_service
    app.dependency_overrides[get_s3_service] = override_get_s3_service
    app.dependency_overrides[get_gemini_service] = override_get_gemini_service
    app.dependency_overrides[get_openai_client] = override_get_openai_client
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
        patch("pins.task.tag_pin_image_task.delay"),
        patch("pins.task.delete_image_task.delay") as mock_delete,
        patch("notification.task.send_notification_email_task.delay"),
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

        def generate_description(self, image_bytes, title):
            return f"AI description for {title}"

    return MockGeminiService()


@pytest.fixture
def mock_openai_service():
    class MockOpenAIService:
        def generate_image(
            self,
            prompt: str,
            number_of_images: int = 1,
            aspect_ratio: str | None = "1:1",
        ):
            one_pixel_png = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNgAAIAAAUA"
                "AV7zKjoAAAAASUVORK5CYII="
            )
            return [{"b64_json": one_pixel_png} for _ in range(number_of_images)]

    return MockOpenAIService()


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
    return CommentService(pin_repo, comment_repo, comment_filter, db_session)


@pytest.fixture
def discovery_svc(
    db_session: AsyncSession,
    mock_cache_service,
):
    pin_repo = PinRepository(db_session)
    discover_repo = DiscoverRepository(db_session)
    user_repo = UserRepository(db_session)
    return DiscoveryService(pin_repo, discover_repo, mock_cache_service, user_repo)


@pytest.fixture
def auth_svc(db_session: AsyncSession, mock_session_service):
    user_repo = UserRepository(db_session)
    auth_repo = AuthRepository(db_session)
    return AuthService(db_session, mock_session_service, user_repo, auth_repo)


@pytest.fixture
def notification_svc(db_session: AsyncSession):
    return NotificationService(db_session)


@pytest.fixture
def user_svc(db_session: AsyncSession, notification_svc: NotificationService):
    user_repo = UserRepository(db_session)
    return UserService(db_session, user_repo, notification_svc)


@pytest.fixture
def board_svc(
    db_session: AsyncSession,
    mock_session_service,
    pin_svc,
    notification_svc: NotificationService,
):

    board_repo = BoardRepository(db_session)
    user_repo = UserRepository(db_session)
    return BoardService(
        db_session,
        mock_session_service,
        board_repo,
        pin_svc,
        user_repo,
        notification_svc,
    )
