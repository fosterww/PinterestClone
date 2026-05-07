import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    negative_prompt: str | None = Field(None, max_length=500)
    style: str | None = Field(None, max_length=100)
    aspect_ratio: Literal["1:1", "16:9", "9:16"] | None = "1:1"
    seed: int | None = Field(None, ge=0)
    num_images: int = Field(1, ge=1, le=1)

    @field_validator("prompt", "negative_prompt", "style", mode="before")
    @classmethod
    def strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GeneratedImageResponse(BaseModel):
    id: uuid.UUID
    image_url: str
    prompt: str
    style: str | None = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateImageResponse(BaseModel):
    generated_images: list[GeneratedImageResponse]
    operation_id: uuid.UUID | None = None
