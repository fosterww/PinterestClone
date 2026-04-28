import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from boards.models import BoardVisibility
from pins.schemas import PinListResponse
from users.schemas import UserSearchResponse


class SearchTarget(str, Enum):
    all = "all"
    users = "users"
    boards = "boards"
    pins = "pins"


class BoardSearchResponse(BaseModel):
    id: uuid.UUID
    title: str = Field(..., max_length=50)
    description: str | None = Field(None, max_length=200)
    visibility: BoardVisibility
    created_at: datetime
    owner_username: str


class SearchResponse(BaseModel):
    query: str
    target: SearchTarget
    users: list[UserSearchResponse] = Field(default_factory=list)
    boards: list[BoardSearchResponse] = Field(default_factory=list)
    pins: list[PinListResponse] = Field(default_factory=list)
