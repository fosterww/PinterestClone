from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from ai.router import router as ai_router
from auth.router import router as auth_router
from boards.router import router as board_router
from core.config import settings
from core.infra.metrics import metrics_response, setup_metrics
from core.security.limiter import limiter
from pins.router import router as pin_router
from search.router import router as search_router
from users.router import router as user_router


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
    allow_origins=[
        "http://localhost:5173",
        "https://pinterestclone-beige.vercel.app/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
setup_metrics(app)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return _rate_limit_exceeded_handler(request, exc)


app.include_router(auth_router, prefix="/api/v2/auth", tags=["auth"])
app.include_router(ai_router, prefix="/api/v2/ai", tags=["ai"])
app.include_router(search_router, prefix="/api/v2/search", tags=["search"])
app.include_router(user_router, prefix="/api/v2/users", tags=["users"])
app.include_router(pin_router, prefix="/api/v2/pins", tags=["pins"])
app.include_router(board_router, prefix="/api/v2/boards", tags=["boards"])


@app.get("/metrics", include_in_schema=False)
@app.get("/api/v2/metrics", include_in_schema=False)
async def get_metrics() -> Response:
    return metrics_response()
