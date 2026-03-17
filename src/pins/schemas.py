import uuid

from pydantic import BaseModel, ConfigDict


class PinBase(BaseModel):
    title: str
    description: str | None = None
    link_url: str | None = None


class PinCreate(PinBase):
    pass


class PinUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    link_url: str | None = None
    image_url: str | None = None


class PinResponse(PinBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    image_url: str

    model_config = ConfigDict(from_attributes=True)
