from pydantic import BaseModel, ConfigDict

from src.boards.models import BoardVisibility
from src.users.schemas import UserResponse
from src.pins.schemas import PinResponse


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
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class BoardPinsResponse(BoardBase):
    user: UserResponse
    pins: list[PinResponse]

    model_config = ConfigDict(from_attributes=True)
