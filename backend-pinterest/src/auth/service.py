import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.security.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from core.security.session import SessionService
from core.logger import logger
from users.models import RefreshTokenModel, UserModel
from users.schemas import UserCreate
from core.config import settings
from users.repository import UserRepository
from auth.repository import AuthRepository
from core.exception import ConflictError


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        session_service: SessionService,
        user_repo: UserRepository,
        auth_repo: AuthRepository,
    ) -> None:
        self.db = db
        self.user_repo = user_repo
        self.auth_repo = auth_repo
        self.session_service = session_service

    async def register_user(self, data: UserCreate) -> UserModel:
        existing = await self.user_repo.get_user_by_username_or_email(
            data.username, data.email
        )
        if existing:
            field = "username" if existing.username == data.username else "email"
            raise ConflictError(f"{field} already taken")

        user_data = {
            "username": data.username,
            "email": data.email,
            "hashed_password": hash_password(data.password),
            "full_name": data.full_name,
            "bio": data.bio,
            "avatar_url": data.avatar_url,
        }
        return await self.user_repo.create_user(user_data)

    async def authenticate_user(self, username: str, password: str) -> UserModel | None:
        user = await self.user_repo.get_user_by_username_or_email(username, username)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    async def logout_user(self, token: str):
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            session_id: str | None = payload.get("session_id")
            if session_id:
                await self.session_service.delete_session(session_id)
        except InvalidTokenError:
            pass

    async def get_or_create_google_user(self, google_info: dict) -> UserModel:
        user = await self.user_repo.get_user_by_google_id_or_email(
            google_info["sub"], google_info["email"]
        )
        if user:
            if not user.google_id:
                user = await self.user_repo.link_google_id(user.id, google_info["sub"])
            return user

        username = google_info["email"].split("@")[0]
        collision_count = 0
        while True:
            existing = await self.user_repo.get_user_by_username_or_email(username, "")
            if not existing:
                break
            collision_count += 1
            username = f"{username}{collision_count}"

        user_data = {
            "username": username,
            "email": google_info["email"],
            "google_id": google_info["sub"],
            "full_name": google_info["name"],
            "avatar_url": google_info["picture"],
        }
        return await self.user_repo.create_user(user_data)

    async def create_user_session_and_tokens(self, user: UserModel) -> dict:
        session_id = await self.session_service.create_session(user.id)
        access_token = create_access_token(
            {"sub": user.username, "session_id": session_id}
        )
        refresh_token = create_refresh_token(
            {"sub": user.username, "session_id": session_id}
        )

        token_model = RefreshTokenModel(
            token=refresh_token,
            user_id=user.id,
            session_id=session_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.refresh_token_expire_minutes),
        )
        await self.auth_repo.save_refresh_token(token_model)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "session_id": session_id,
        }

    async def refresh_user_token(self, refresh_token: str) -> dict:
        unauthorized_exc = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

        token = await self.auth_repo.get_refresh_token(refresh_token)
        if not token or token.is_expired:
            raise unauthorized_exc

        user = token.user
        if not user:
            raise unauthorized_exc

        is_valid = False
        try:
            is_valid = await self.session_service.validate_session(token.session_id)
        except Exception:
            logger.warning(f"Session validation failed for session {token.session_id}")

        session_id = (
            token.session_id
            if is_valid
            else await self.session_service.create_session(user.id)
        )

        access_token = create_access_token(
            {"sub": user.username, "session_id": session_id}
        )
        new_refresh_token = create_refresh_token(
            {"sub": user.username, "session_id": session_id}
        )

        token.token = new_refresh_token
        token.session_id = session_id
        token.expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.refresh_token_expire_minutes
        )
        await self.auth_repo.save_refresh_token(token)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
