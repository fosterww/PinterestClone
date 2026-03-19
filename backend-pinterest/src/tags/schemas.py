import uuid

from pydantic import BaseModel, ConfigDict


class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)