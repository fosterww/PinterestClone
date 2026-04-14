from functools import lru_cache
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from database import get_db
from core.config import settings
from core.security.session import SessionService
from core.infra.cache import CacheService
from core.infra.s3 import S3Service
from core.infra.comment_filter import CommentFilter

from users.repository import UserRepository
from auth.repository import AuthRepository
from boards.repository import BoardRepository

from pins.repository.pin import PinRepository
from pins.repository.comment import CommentRepository
from pins.repository.discover import DiscoverRepository

from core.infra.gemini import GeminiService
from auth.service import AuthService
from pins.service.pin import PinService
from pins.service.comment import CommentService
from pins.service.discovery import DiscoveryService
from boards.service import BoardService
from tags.service import TagService


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


def get_gemini_service() -> GeminiService:
    return GeminiService()


@lru_cache()
def get_comment_filter() -> CommentFilter:
    return CommentFilter()


async def get_session_service() -> SessionService:
    redis = await Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_socket_timeout,
    )
    return SessionService(redis)


async def get_cache_service() -> CacheService:
    redis = await Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_socket_timeout,
    )
    return CacheService(redis)


async def get_s3_service() -> S3Service:
    return S3Service()


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
) -> CommentService:
    return CommentService(pin_repo, comment_repo, comment_filter)


def get_discovery_service(
    pin_repo: PinRepository = Depends(get_pin_repository),
    discover_repo: DiscoverRepository = Depends(get_discover_repository),
    cache: CacheService = Depends(get_cache_service),
) -> DiscoveryService:
    return DiscoveryService(pin_repo, discover_repo, cache)


def get_board_service(
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
    board_repository: BoardRepository = Depends(get_board_repository),
    pin_service: PinService = Depends(get_pin_service),
) -> BoardService:
    return BoardService(db, session_service, board_repository, pin_service)
