import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from boards.models import GeneratedPinModel, PinModel
from database import Base
from users.models import UserModel


class AIProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    CLARIFAI = "clarifai"


class AIOperationType(str, Enum):
    IMAGE_GENERATION = "image_generation"
    TAG_GENERATION = "tag_generation"
    DESCRIPTION_GENERATION = "description_generation"
    IMAGE_INDEXING = "image_indexing"
    VISUAL_SEARCH = "visual_search"


class AIStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AIOperationModel(Base):
    __tablename__ = "ai_operations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    related_pin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    generated_pin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("generated_pins.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[AIProvider] = mapped_column(
        SAEnum(
            AIProvider,
            values_callable=lambda enum: [item.value for item in enum],
            name="aiprovider",
        ),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_type: Mapped[AIOperationType] = mapped_column(
        SAEnum(
            AIOperationType,
            values_callable=lambda enum: [item.value for item in enum],
            name="aioperationtype",
        ),
        nullable=False,
        index=True,
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[AIStatus] = mapped_column(
        SAEnum(
            AIStatus,
            values_callable=lambda enum: [item.value for item in enum],
            name="aistatus",
        ),
        nullable=False,
        default=AIStatus.PENDING,
        server_default=AIStatus.PENDING.value,
        index=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["UserModel | None"] = relationship("UserModel")
    related_pin: Mapped["PinModel | None"] = relationship("PinModel")
    generated_pin: Mapped["GeneratedPinModel | None"] = relationship(
        "GeneratedPinModel"
    )
