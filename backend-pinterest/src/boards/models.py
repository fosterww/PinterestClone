from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, func, ForeignKey, Table, Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy import UUID as SAUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.users.models import UserModel


class BoardVisibility(str, Enum):
    PUBLIC = "public"
    SECRET = "secret"


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
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    likes: Mapped[list["PinLikeModel"]] = relationship(
        "PinLikeModel", back_populates="pin"
    )
    likes_count: Mapped[int] = mapped_column(server_default="0")
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
    name: Mapped[str] = mapped_column(String(50), nullable=False)
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

    pin: Mapped["PinModel"] = relationship("PinModel", back_populates="likes")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="likes")


class PinCommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    comment: Mapped[str] = mapped_column(String(500), nullable=False)
    likes_count: Mapped[int] = mapped_column(server_default="0")
    pin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pins.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
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
    parent: Mapped[PinCommentModel | None] = relationship(
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

    comment_obj: Mapped["PinCommentModel"] = relationship(
        "PinCommentModel", back_populates="likes"
    )
    user: Mapped["UserModel"] = relationship("UserModel")
