import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tags.schemas import TagResponse
from users.schemas import UserSearchResponse


class PinBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    link_url: str | None = Field(None, max_length=200)
    likes_count: int = 0


class PinCommentCreate(BaseModel):
    comment: str = Field(..., min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None

    @field_validator("parent_id", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class PinCommentResponse(PinCommentCreate):
    id: uuid.UUID
    likes_count: int = 0
    created_at: datetime
    user: UserSearchResponse
    replies: list["PinCommentResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PinCreate(PinBase):
    tags: list[str] | None = None
    generate_ai_description: bool = False
    generated_pin_id: uuid.UUID | None = None


class PinUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    link_url: str | None = Field(None, max_length=200)
    image_url: str | None = Field(None, max_length=200)
    tags: list[str] = Field(default_factory=list)


class PinListResponse(PinBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    user: UserSearchResponse
    image_url: str
    tags: list[TagResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PinResponse(PinBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    user: UserSearchResponse
    image_url: str
    tags: list[TagResponse]
    created_at: datetime
    comments: list[PinCommentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PinLikeResponse(BaseModel):
    id: uuid.UUID
    pin: PinResponse
    user: UserSearchResponse

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
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)
    search: str | None = Field(None, max_length=100)

    model_config = ConfigDict(from_attributes=True)
