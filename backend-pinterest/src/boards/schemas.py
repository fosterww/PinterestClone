import uuid
from pydantic import BaseModel, ConfigDict, Field

from boards.models import BoardVisibility
from users.schemas import UserResponse
from pins.schemas import PinResponse


class BoardBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    visibility: BoardVisibility = BoardVisibility.PUBLIC


class BoardCreate(BoardBase):
    pass


class BoardUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=200)
    visibility: BoardVisibility | None = Field(None)


class BoardResponse(BoardBase):
    id: uuid.UUID
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class BoardPinsResponse(BoardBase):
    id: uuid.UUID
    user: UserResponse
    pins: list[PinResponse]

    model_config = ConfigDict(from_attributes=True)
