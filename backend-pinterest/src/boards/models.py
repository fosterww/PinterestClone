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
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["UserModel"] = relationship(
        "UserModel", back_populates="pins"
    )
    boards: Mapped[list["BoardModel"]] = relationship(
        "BoardModel",
        secondary=board_pin_association,
        back_populates="pins"
    )
    tags: Mapped[list["TagModel"]] = relationship(
        "TagModel",
        secondary=pin_tag_association,
        back_populates="pins"
    )


class BoardModel(Base):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visibility: Mapped[BoardVisibility] = mapped_column(
        SAEnum(BoardVisibility, name="boardvisibility"),
        default=BoardVisibility.PUBLIC
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["UserModel"] = relationship(
        "UserModel", back_populates="boards"
    )
    pins: Mapped[list["PinModel"]] = relationship(
        "PinModel",
        secondary=board_pin_association,
        back_populates="boards"
    )


class TagModel(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    pins: Mapped[list["PinModel"]] = relationship(
        "PinModel",
        secondary=pin_tag_association,
        back_populates="tags"
    )