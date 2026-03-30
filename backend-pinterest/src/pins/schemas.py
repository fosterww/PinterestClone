import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.tags.schemas import TagResponse
from src.users.schemas import UserResponse


class PinBase(BaseModel):
    title: str
    description: str | None = None
    link_url: str | None = None
    likes_count: int = 0


class PinCreate(PinBase):
    tags: list[str] = []


class PinUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    link_url: str | None = None
    image_url: str | None = None
    tags: list[str] = []


class PinResponse(PinBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    image_url: str
    tags: list[TagResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PinLikeResponse(BaseModel):
    id: uuid.UUID
    pin: PinResponse
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class Popularity(str, Enum):
    most_popular = "most_popular"
    least_popular = "least_popular"


class CreatedAt(str, Enum):
    newest = "newest"
    oldest = "oldest"


class FilterPins(BaseModel):
    created_at: CreatedAt | None = None
    popularity: Popularity | None = None

    model_config = ConfigDict(from_attributes=True)


class Pagination(BaseModel):
    offset: int = 0
    limit: int = 20
    search: str | None = None

    model_config = ConfigDict(from_attributes=True)
