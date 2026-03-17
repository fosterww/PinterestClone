from fastapi import FastAPI

from src.auth.router import router as auth_router
from src.boards.router import router as board_router
from src.pins.router import router as pin_router
from src.users.router import router as user_router

app = FastAPI(
    title="Pinterest API",
    description="Pinterest API",
    version="0.0.1",
    )

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_router, prefix="/api/v1/users", tags=["users"])
app.include_router(pin_router, prefix="/api/v1/pins", tags=["pins"])
app.include_router(board_router, prefix="/api/v1/boards", tags=["boards"])

