import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class UserSearchResponse(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str | None = None
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: uuid.UUID
    followers_count: int = 0
    following_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PublicUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    pins_count: int = 0
    boards_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class UserInternal(UserBase):
    id: uuid.UUID
    hashed_password: str | None = None
    google_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class GoogleLogin(BaseModel):
    id_token: str


class TokenRefresh(BaseModel):
    refresh_token: str
