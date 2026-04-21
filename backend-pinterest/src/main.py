from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from auth.router import router as auth_router
from boards.router import router as board_router
from pins.router import router as pin_router
from search.router import router as search_router
from users.router import router as user_router
from core.config import settings
from core.security.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=settings.redis_socket_timeout,
    )
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.aclose()


app = FastAPI(
    title="Pinterest API",
    description="Pinterest API",
    version="0.0.2",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router, prefix="/api/v2/auth", tags=["auth"])
app.include_router(search_router, prefix="/api/v2/search", tags=["search"])
app.include_router(user_router, prefix="/api/v2/users", tags=["users"])
app.include_router(pin_router, prefix="/api/v2/pins", tags=["pins"])
app.include_router(board_router, prefix="/api/v2/boards", tags=["boards"])
