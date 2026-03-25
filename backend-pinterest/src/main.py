from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.boards.router import router as board_router
from src.pins.router import router as pin_router
from src.users.router import router as user_router
from src.core.limiter import limiter

app = FastAPI(
    title="Pinterest API",
    description="Pinterest API",
    version="0.0.1",
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

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_router, prefix="/api/v1/users", tags=["users"])
app.include_router(pin_router, prefix="/api/v1/pins", tags=["pins"])
app.include_router(board_router, prefix="/api/v1/boards", tags=["boards"])
