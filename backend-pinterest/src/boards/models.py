import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON
from sqlalchemy import UUID as SAUUID
from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from users.models import UserModel


class BoardVisibility(str, Enum):
    PUBLIC = "public"
    SECRET = "secret"


class PinProcessingState(str, Enum):
    UPLOADED = "uploaded"
    TAGGED = "tagged"
    INDEXED = "indexed"
    FAILED = "failed"


class PinModerationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    HIDDEN = "hidden"
    FAILED = "failed"


class PinEditSource(str, Enum):
    USER = "user"
    SYSTEM = "system"


board_pin_association = Table(
    "board_pins",
    Base.metadata,
    Column("board_id", SAUUID(as_uuid=True), ForeignKey("boards.id"), primary_key=True),
    Column("pin_id", SAUUID(as_uuid=True), ForeignKey("pins.id"), primary_key=True),
)


pin_tag_association = Table(
    "pin_tags",
    Base.metadata,
    Column("pin_id", SAUUID(as_uuid=True), ForeignKey("pins.id"), primary_key=True),
    Column("tag_id", SAUUID(as_uuid=True), ForeignKey("tags.id"), primary_key=True),
)


class PinModel(Base):
    __tablename__ = "pins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    processing_state: Mapped[PinProcessingState] = mapped_column(
        SAEnum(
            PinProcessingState,
            values_callable=lambda enum: [item.value for item in enum],
            name="pinprocessingstate",
        ),
        default=PinProcessingState.UPLOADED,
        server_default=PinProcessingState.UPLOADED.value,
        nullable=False,
    )
    moderation_status: Mapped[PinModerationStatus] = mapped_column(
        SAEnum(
            PinModerationStatus,
            values_callable=lambda enum: [item.value for item in enum],
            name="pinmoderationstatus",
        ),
        default=PinModerationStatus.PENDING,
        server_default=PinModerationStatus.PENDING.value,
        nullable=False,
    )
    tagging_attempts: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    indexing_attempts: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    last_processing_error: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    tagged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dominant_colors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    file_hash_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    duplicate_of_pin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pins.id", ondelete="SET NULL"), nullable=True, index=True
    )

    likes: Mapped[list["PinLikeModel"]] = relationship(
        "PinLikeModel", back_populates="pin"
    )
    views_count: Mapped[int] = mapped_column(server_default="0")
    likes_count: Mapped[int] = mapped_column(server_default="0")
    saves_count: Mapped[int] = mapped_column(server_default="0")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="pins")
    boards: Mapped[list["BoardModel"]] = relationship(
        "BoardModel", secondary=board_pin_association, back_populates="pins"
    )
    tags: Mapped[list["TagModel"]] = relationship(
        "TagModel", secondary=pin_tag_association, back_populates="pins"
    )
    comments: Mapped[list["PinCommentModel"]] = relationship(
        "PinCommentModel",
        primaryjoin="and_(PinModel.id == PinCommentModel.pin_id, PinCommentModel.parent_id == None)",
        viewonly=True,
    )
    edit_history: Mapped[list["PinEditHistoryModel"]] = relationship(
        "PinEditHistoryModel",
        back_populates="pin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GeneratedPinModel(Base):
    __tablename__ = "generated_pins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(String(1000), nullable=False)
    style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    user: Mapped["UserModel"] = relationship(
        "UserModel", back_populates="generated_pins"
    )
    moderation_status: Mapped["PinModerationStatus"] = mapped_column(
        SAEnum(
            PinModerationStatus,
            values_callable=lambda enum: [item.value for item in enum],
            name="generatedpinmoderationstatus",
        ),
        default=PinModerationStatus.APPROVED,
        server_default=PinModerationStatus.APPROVED.value,
        nullable=False,
    )
    moderation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PinEditHistoryModel(Base):
    __tablename__ = "pin_edit_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[PinEditSource] = mapped_column(
        SAEnum(
            PinEditSource,
            values_callable=lambda enum: [item.value for item in enum],
            name="pineditsource",
        ),
        default=PinEditSource.SYSTEM,
        server_default=PinEditSource.SYSTEM.value,
        nullable=False,
    )
    changed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    pin: Mapped["PinModel"] = relationship("PinModel", back_populates="edit_history")
    actor: Mapped["UserModel | None"] = relationship("UserModel")


class BoardModel(Base):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visibility: Mapped[BoardVisibility] = mapped_column(
        SAEnum(BoardVisibility, name="boardvisibility"), default=BoardVisibility.PUBLIC
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="boards")
    pins: Mapped[list["PinModel"]] = relationship(
        "PinModel", secondary=board_pin_association, back_populates="boards"
    )


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    pins: Mapped[list["PinModel"]] = relationship(
        "PinModel", secondary=pin_tag_association, back_populates="tags"
    )


class PinLikeModel(Base):
    __tablename__ = "pin_likes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pins.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("pin_id", "user_id", name="uq_pin_user_like"),)

    pin: Mapped["PinModel"] = relationship("PinModel", back_populates="likes")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="likes")


class PinCommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    comment: Mapped[str] = mapped_column(String(500), nullable=False)
    likes_count: Mapped[int] = mapped_column(server_default="0")
    pin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pins.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    pin: Mapped["PinModel"] = relationship("PinModel", back_populates="comments")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="comments")
    replies: Mapped[list["PinCommentModel"]] = relationship(
        "PinCommentModel",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parent: Mapped["PinCommentModel | None"] = relationship(
        "PinCommentModel",
        back_populates="replies",
        remote_side=[id],
    )
    likes: Mapped[list["PinCommentLikeModel"]] = relationship(
        "PinCommentLikeModel",
        back_populates="comment_obj",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PinCommentLikeModel(Base):
    __tablename__ = "comment_likes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_user_like"),
    )

    comment_obj: Mapped["PinCommentModel"] = relationship(
        "PinCommentModel", back_populates="likes"
    )
    user: Mapped["UserModel"] = relationship("UserModel")
