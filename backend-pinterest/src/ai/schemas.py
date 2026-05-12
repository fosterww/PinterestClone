import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai.models import AIOperationModel, AIStatus
from boards.models import PinModerationStatus


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
    moderation_status: PinModerationStatus
    moderation_reason: str | None = None
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIQuotaMetadata(BaseModel):
    operation_type: str
    limit: int
    used: int
    remaining: int
    resets_at: datetime


class AIOperationOutput(BaseModel):
    id: uuid.UUID
    status: AIStatus
    error: str | None = None
    latency_ms: int | None
    output_id: uuid.UUID | None = None

    @classmethod
    def from_operation(cls, operation: AIOperationModel) -> "AIOperationOutput":
        return cls(
            id=operation.id,
            status=operation.status,
            error=operation.error_message,
            latency_ms=operation.latency_ms,
            output_id=operation.generated_pin_id or operation.related_pin_id,
        )


class GenerateImageResponse(BaseModel):
    generated_images: list[GeneratedImageResponse]
    operation_id: uuid.UUID | None = None
    quota: AIQuotaMetadata | None = None
