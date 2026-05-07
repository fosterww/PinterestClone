from functools import lru_cache

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ai.service import OpenAIService
from auth.repository import AuthRepository
from auth.service import AuthService
from boards.repository import BoardRepository
from boards.service import BoardService
from core.config import settings
from core.infra.cache import CacheService
from core.infra.comment_filter import CommentFilter
from core.infra.gemini import GeminiService
from core.infra.openai import OpenAIClient
from core.infra.s3 import S3Service
from core.security.session import SessionService
from database import get_db
from notification.service import NotificationService
from pins.repository.comment import CommentRepository
from pins.repository.discover import DiscoverRepository
from pins.repository.pin import PinRepository
from pins.service.comment import CommentService
from pins.service.discovery import DiscoveryService
from pins.service.pin import PinService
from search.service import SearchService
from tags.service import TagService
from users.repository import UserRepository
from users.service import UserService


def get_board_repository(db: AsyncSession = Depends(get_db)) -> BoardRepository:
    return BoardRepository(db)


def get_pin_repository(db: AsyncSession = Depends(get_db)) -> PinRepository:
    return PinRepository(db)


def get_comment_repository(db: AsyncSession = Depends(get_db)) -> CommentRepository:
    return CommentRepository(db)


def get_discover_repository(db: AsyncSession = Depends(get_db)) -> DiscoverRepository:
    return DiscoverRepository(db)


def get_auth_repository(db: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_tag_service(db: AsyncSession = Depends(get_db)) -> TagService:
    return TagService(db)


@lru_cache()
def get_gemini_service() -> GeminiService:
    return GeminiService()


@lru_cache()
def get_comment_filter() -> CommentFilter:
    return CommentFilter()


def get_redis(request: Request) -> Redis:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RuntimeError("Redis client is not initialized in app state")
    return redis


def get_session_service(redis: Redis = Depends(get_redis)) -> SessionService:
    return SessionService(redis)


def get_cache_service(redis: Redis = Depends(get_redis)) -> CacheService:
    return CacheService(redis)


async def get_s3_service() -> S3Service:
    return S3Service()


@lru_cache()
def get_openai_client() -> OpenAIClient:
    return OpenAIClient(settings.openai_api_key)


def get_ai_service(
    db: AsyncSession = Depends(get_db),
    s3_service: S3Service = Depends(get_s3_service),
    openai_client: OpenAIClient = Depends(get_openai_client),
) -> OpenAIService:
    return OpenAIService(s3_service, openai_client, db)


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    return NotificationService(db)


async def get_user_service(
    db: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
    notification_service: NotificationService = Depends(get_notification_service),
) -> UserService:
    return UserService(db, repo, notification_service)


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> AuthService:
    return AuthService(db, session_service, user_repo, auth_repo)


def get_pin_service(
    db: AsyncSession = Depends(get_db),
    repo: PinRepository = Depends(get_pin_repository),
    tag_service: TagService = Depends(get_tag_service),
    s3_service: S3Service = Depends(get_s3_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
) -> PinService:
    return PinService(db, repo, tag_service, s3_service, gemini_service)


def get_comment_service(
    pin_repo: PinRepository = Depends(get_pin_repository),
    comment_repo: CommentRepository = Depends(get_comment_repository),
    comment_filter: CommentFilter = Depends(get_comment_filter),
    db: AsyncSession = Depends(get_db),
    notification_service: NotificationService = Depends(get_notification_service),
) -> CommentService:
    return CommentService(
        pin_repo, comment_repo, comment_filter, db, notification_service
    )


def get_discovery_service(
    pin_repo: PinRepository = Depends(get_pin_repository),
    discover_repo: DiscoverRepository = Depends(get_discover_repository),
    cache: CacheService = Depends(get_cache_service),
    user_repo: UserRepository = Depends(get_user_repository),
) -> DiscoveryService:
    return DiscoveryService(pin_repo, discover_repo, cache, user_repo)


def get_search_service(
    user_repository: UserRepository = Depends(get_user_repository),
    board_repository: BoardRepository = Depends(get_board_repository),
    pin_repository: PinRepository = Depends(get_pin_repository),
) -> SearchService:
    return SearchService(user_repository, board_repository, pin_repository)


def get_board_service(
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
    board_repository: BoardRepository = Depends(get_board_repository),
    pin_service: PinService = Depends(get_pin_service),
    user_repository: UserRepository = Depends(get_user_repository),
    notification_service: NotificationService = Depends(get_notification_service),
) -> BoardService:
    return BoardService(
        db,
        session_service,
        board_repository,
        pin_service,
        user_repository,
        notification_service,
    )
