import uuid

from pydantic import BaseModel, ConfigDict

from src.tags.schemas import TagResponse


class PinBase(BaseModel):
    title: str
    description: str | None = None
    link_url: str | None = None


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

    model_config = ConfigDict(from_attributes=True)
