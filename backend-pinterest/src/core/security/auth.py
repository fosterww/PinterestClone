from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database import get_db
from users.models import UserModel
from core.security.session import SessionService
from core.dependencies import get_session_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    session_service: SessionService = Depends(get_session_service),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        username: str | None = payload.get("sub")
        session_id: str | None = payload.get("session_id")
        if username is None or session_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    try:
        user_id_str = await session_service.validate_session(session_id)
        if not user_id_str:
            raise credentials_exception
        await session_service.refresh_session_ttl(session_id)
    except Exception:
        raise credentials_exception

    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def logout_user(
    token: str = Depends(oauth2_scheme),
    session_service: SessionService = Depends(get_session_service),
):
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        session_id: str | None = payload.get("session_id")
        if session_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        await session_service.delete_session(session_id)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
