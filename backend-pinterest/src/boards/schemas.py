import uuid
from pydantic import BaseModel, ConfigDict

from boards.models import BoardVisibility
from users.schemas import UserResponse
from pins.schemas import PinResponse


class BoardBase(BaseModel):
    title: str
    description: str | None = None
    visibility: BoardVisibility = BoardVisibility.PUBLIC


class BoardCreate(BoardBase):
    pass


class BoardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    visibility: BoardVisibility | None = None


class BoardResponse(BoardBase):
    id: uuid.UUID
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class BoardPinsResponse(BoardBase):
    id: uuid.UUID
    user: UserResponse
    pins: list[PinResponse]

    model_config = ConfigDict(from_attributes=True)
