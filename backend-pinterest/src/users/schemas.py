import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=200)
    avatar_url: str | None = Field(None, max_length=200)


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=200)
    avatar_url: str | None = Field(None, max_length=200)
    email_notifications_enabled: bool | None = Field(None)


class UserSearchResponse(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str | None = Field(None, max_length=100)
    avatar_url: str | None = Field(None, max_length=200)

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: uuid.UUID
    followers_count: int = 0
    following_count: int = 0
    email_notifications_enabled: bool = True

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
