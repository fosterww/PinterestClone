from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.limiter import limiter
from src.core.auth import oauth2_scheme
from src.database import get_db
from src.auth.service import (
    register_user,
    authenticate_user,
    logout_user,
    create_user_token,
)
from src.users.schemas import UserCreate, UserResponse
from src.core.session import SessionService, get_session_service

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await register_user(db, data)
    return user


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_id = await session_service.create_session(user.id)
    token = create_user_token(user, session_id)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    session_service: SessionService = Depends(get_session_service),
):
    await logout_user(token, session_service)
