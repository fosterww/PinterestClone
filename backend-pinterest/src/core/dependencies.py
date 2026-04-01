from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.database import get_db
from src.core.config import settings
from src.core.security.session import SessionService
from src.core.infra.cache import CacheService
from src.core.infra.s3 import S3Service
from src.users.repository import UserRepository
from src.auth.service import AuthService
from src.pins.repository import PinRepository
from src.pins.service import PinService
from src.boards.repository import BoardRepository
from src.boards.service import BoardService
from src.auth.repository import AuthRepository
from src.tags.service import TagService


def get_board_repository(db: AsyncSession = Depends(get_db)) -> BoardRepository:
    return BoardRepository(db)


def get_pin_repository(db: AsyncSession = Depends(get_db)) -> PinRepository:
    return PinRepository(db)


def get_auth_repository(db: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_tag_service(db: AsyncSession = Depends(get_db)) -> TagService:
    return TagService(db)


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


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
    cache: CacheService = Depends(get_cache_service),
    repo: PinRepository = Depends(get_pin_repository),
    tag_service: TagService = Depends(get_tag_service),
    s3_service: S3Service = Depends(get_s3_service),
) -> PinService:
    return PinService(db, cache, repo, tag_service, s3_service)


def get_board_service(
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
    board_repository: BoardRepository = Depends(get_board_repository),
    pin_service: PinService = Depends(get_pin_service),
) -> BoardService:
    return BoardService(db, session_service, board_repository, pin_service)
