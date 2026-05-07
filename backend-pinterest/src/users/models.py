import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import UUID as SAUUID
from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from boards.models import (
        BoardModel,
        GeneratedPinModel,
        PinCommentModel,
        PinLikeModel,
        PinModel,
    )


user_follow_association = Table(
    "user_follows",
    Base.metadata,
    Column(
        "follower_id",
        SAUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "followed_id",
        SAUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at", DateTime(timezone=True), server_default=func.now(), nullable=False
    ),
)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )
    email_notifications_enabled: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    boards: Mapped[list["BoardModel"]] = relationship(
        "BoardModel", back_populates="user"
    )
    pins: Mapped[list["PinModel"]] = relationship("PinModel", back_populates="user")
    likes: Mapped[list["PinLikeModel"]] = relationship(
        "PinLikeModel", back_populates="user"
    )
    comments: Mapped[list["PinCommentModel"]] = relationship(
        "PinCommentModel", back_populates="user"
    )
    generated_pins: Mapped[list["GeneratedPinModel"]] = relationship(
        "GeneratedPinModel", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(
        "RefreshTokenModel", back_populates="user", cascade="all, delete"
    )

    followers: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        secondary=user_follow_association,
        primaryjoin=id == user_follow_association.c.followed_id,
        secondaryjoin=id == user_follow_association.c.follower_id,
        viewonly=True,
    )
    following: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        secondary=user_follow_association,
        primaryjoin=id == user_follow_association.c.follower_id,
        secondaryjoin=id == user_follow_association.c.followed_id,
        viewonly=True,
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(index=True, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    session_id: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def is_expired(self) -> bool:
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at

    user: Mapped["UserModel"] = relationship(
        "UserModel", back_populates="refresh_tokens"
    )
