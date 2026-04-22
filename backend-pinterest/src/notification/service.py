import uuid
from urllib.parse import urljoin

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from boards.models import BoardModel, BoardVisibility, PinCommentModel, PinModel
from core.config import settings
from core.infra.metrics import record_notification_event
from core.logger import logger
from notification.schemas import EmailNotificationPayload, NotificationType
from notification.task import send_notification_email_task
from users.models import UserModel


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_follow(
        self,
        follower_id: uuid.UUID,
        followed_username: str,
    ) -> bool:
        try:
            follower = await self._get_user_by_id(follower_id)
            recipient = await self._get_user_by_username(followed_username)
            if follower is None or recipient is None:
                return False

            payload = self._build_follow_payload(follower, recipient)
            if payload is None:
                return False

            self._enqueue(payload)
            return True
        except Exception:
            logger.exception(
                "Failed to enqueue follow notification for %s -> %s",
                follower_id,
                followed_username,
            )
            return False

    async def notify_comment(
        self,
        actor_id: uuid.UUID,
        pin_id: uuid.UUID,
        comment_id: uuid.UUID,
    ) -> bool:
        try:
            actor = await self._get_user_by_id(actor_id)
            pin = await self._get_pin_by_id(pin_id)
            comment = await self._get_comment_by_id(comment_id)
            if (
                actor is None
                or pin is None
                or comment is None
                or comment.pin_id != pin_id
            ):
                return False

            if comment.parent_id is None:
                recipient = await self._get_user_by_id(pin.owner_id)
                if recipient is None:
                    return False
                payload = self._build_pin_comment_payload(
                    actor=actor,
                    recipient=recipient,
                    pin=pin,
                    comment=comment,
                )
            else:
                parent_comment = await self._get_comment_by_id(comment.parent_id)
                if parent_comment is None:
                    return False
                recipient = await self._get_user_by_id(parent_comment.user_id)
                if recipient is None:
                    return False
                payload = self._build_comment_reply_payload(
                    actor=actor,
                    recipient=recipient,
                    pin=pin,
                    comment=comment,
                    parent_comment=parent_comment,
                )

            if payload is None:
                return False

            self._enqueue(payload)
            return True
        except Exception:
            logger.exception(
                "Failed to enqueue comment notification for actor=%s pin=%s comment=%s",
                actor_id,
                pin_id,
                comment_id,
            )
            return False

    async def notify_pin_save(
        self,
        actor_id: uuid.UUID,
        board_id: uuid.UUID,
        pin_id: uuid.UUID,
    ) -> bool:
        try:
            actor = await self._get_user_by_id(actor_id)
            board = await self._get_board_by_id(board_id)
            pin = await self._get_pin_by_id(pin_id)
            if actor is None or board is None or pin is None:
                return False

            recipient = await self._get_user_by_id(pin.owner_id)
            if recipient is None:
                return False

            payload = self._build_pin_save_payload(
                actor=actor,
                recipient=recipient,
                pin=pin,
                board=board,
            )
            if payload is None:
                return False

            self._enqueue(payload)
            return True
        except Exception:
            logger.exception(
                "Failed to enqueue pin save notification for actor=%s board=%s pin=%s",
                actor_id,
                board_id,
                pin_id,
            )
            return False

    async def _get_user_by_id(self, user_id: uuid.UUID) -> UserModel | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        return result.scalar_one_or_none()

    async def _get_user_by_username(self, username: str) -> UserModel | None:
        result = await self.db.execute(
            select(UserModel).where(UserModel.username == username)
        )
        return result.scalar_one_or_none()

    async def _get_pin_by_id(self, pin_id: uuid.UUID) -> PinModel | None:
        result = await self.db.execute(select(PinModel).where(PinModel.id == pin_id))
        return result.scalar_one_or_none()

    async def _get_board_by_id(self, board_id: uuid.UUID) -> BoardModel | None:
        result = await self.db.execute(
            select(BoardModel).where(BoardModel.id == board_id)
        )
        return result.scalar_one_or_none()

    async def _get_comment_by_id(self, comment_id: uuid.UUID) -> PinCommentModel | None:
        result = await self.db.execute(
            select(PinCommentModel)
            .where(PinCommentModel.id == comment_id)
            .options(selectinload(PinCommentModel.user))
        )
        return result.scalar_one_or_none()

    def _build_follow_payload(
        self,
        actor: UserModel,
        recipient: UserModel,
    ) -> EmailNotificationPayload | None:
        if not self._should_notify(recipient, actor.id):
            return None

        actor_name = self._display_name(actor)
        profile_url = self._frontend_url(f"/users/{actor.username}")
        body = f"{actor_name} started following you on Pinterest."
        if profile_url:
            body = f"{body}\n\nView profile: {profile_url}"

        return EmailNotificationPayload(
            notification_type=NotificationType.FOLLOW,
            recipient_id=recipient.id,
            recipient_email=recipient.email,
            recipient_username=recipient.username,
            subject=f"{actor_name} started following you",
            text_body=body,
        )

    def _build_pin_comment_payload(
        self,
        actor: UserModel,
        recipient: UserModel,
        pin: PinModel,
        comment: PinCommentModel,
    ) -> EmailNotificationPayload | None:
        if not self._should_notify(recipient, actor.id):
            return None

        actor_name = self._display_name(actor)
        pin_label = self._pin_label(pin)
        pin_url = self._frontend_url(f"/pins/{pin.id}")
        body = (
            f"{actor_name} commented on {pin_label}.\n\n"
            f"Comment: {self._excerpt(comment.comment)}"
        )
        if pin_url:
            body = f"{body}\n\nView pin: {pin_url}"

        return EmailNotificationPayload(
            notification_type=NotificationType.PIN_COMMENT,
            recipient_id=recipient.id,
            recipient_email=recipient.email,
            recipient_username=recipient.username,
            subject=f"{actor_name} commented on your pin",
            text_body=body,
        )

    def _build_comment_reply_payload(
        self,
        actor: UserModel,
        recipient: UserModel,
        pin: PinModel,
        comment: PinCommentModel,
        parent_comment: PinCommentModel,
    ) -> EmailNotificationPayload | None:
        if not self._should_notify(recipient, actor.id):
            return None

        actor_name = self._display_name(actor)
        pin_url = self._frontend_url(f"/pins/{pin.id}")
        body = (
            f"{actor_name} replied to your comment on {self._pin_label(pin)}.\n\n"
            f"Your comment: {self._excerpt(parent_comment.comment)}\n"
            f"Reply: {self._excerpt(comment.comment)}"
        )
        if pin_url:
            body = f"{body}\n\nView discussion: {pin_url}"

        return EmailNotificationPayload(
            notification_type=NotificationType.COMMENT_REPLY,
            recipient_id=recipient.id,
            recipient_email=recipient.email,
            recipient_username=recipient.username,
            subject=f"{actor_name} replied to your comment",
            text_body=body,
        )

    def _build_pin_save_payload(
        self,
        actor: UserModel,
        recipient: UserModel,
        pin: PinModel,
        board: BoardModel,
    ) -> EmailNotificationPayload | None:
        if not self._should_notify(recipient, actor.id):
            return None

        actor_name = self._display_name(actor)
        pin_label = self._pin_label(pin)
        pin_url = self._frontend_url(f"/pins/{pin.id}")

        if board.visibility == BoardVisibility.SECRET:
            body = f"{actor_name} saved {pin_label}."
        else:
            body = f'{actor_name} saved {pin_label} to the board "{board.title}".'

        if pin_url:
            body = f"{body}\n\nView pin: {pin_url}"

        return EmailNotificationPayload(
            notification_type=NotificationType.PIN_SAVE,
            recipient_id=recipient.id,
            recipient_email=recipient.email,
            recipient_username=recipient.username,
            subject=f"{actor_name} saved your pin",
            text_body=body,
        )

    def _should_notify(self, recipient: UserModel, actor_id: uuid.UUID) -> bool:
        return (
            recipient.id != actor_id
            and bool(recipient.email)
            and recipient.email_notifications_enabled
        )

    def _enqueue(self, payload: EmailNotificationPayload) -> None:
        record_notification_event(payload.notification_type.value, "enqueued")
        send_notification_email_task.delay(payload.model_dump(mode="json"))

    def _display_name(self, user: UserModel) -> str:
        return user.full_name or user.username

    def _pin_label(self, pin: PinModel) -> str:
        return f'your pin "{pin.title}"'

    def _excerpt(self, text: str, limit: int = 180) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def _frontend_url(self, path: str) -> str | None:
        if not settings.frontend_base_url:
            return None
        return urljoin(f"{settings.frontend_base_url.rstrip('/')}/", path.lstrip("/"))
