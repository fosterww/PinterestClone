from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from auth.service import AuthService
from boards.schemas import BoardCreate
from boards.service import BoardService
from notification.schemas import NotificationType
from notification.service import NotificationService
from pins.schemas import PinCreate
from pins.service.comment import CommentService
from pins.repository.comment import CommentRepository
from pins.repository.pin import PinRepository
from users.repository import UserRepository
from users.schemas import UserCreate, UserUpdate
from users.service import UserService


from tests.test_service.test_pins_service import mock_image_file


@pytest.fixture
def comment_svc_with_notifications(
    db_session: AsyncSession,
    comment_filter,
    notification_svc: NotificationService,
):
    pin_repo = PinRepository(db_session)
    comment_repo = CommentRepository(db_session)
    return CommentService(
        pin_repo,
        comment_repo,
        comment_filter,
        db_session,
        notification_svc,
    )


@pytest_asyncio.fixture
async def first_user(auth_svc: AuthService):
    return await auth_svc.register_user(
        UserCreate(
            username="notify_user_1",
            email="notify_user_1@example.com",
            password="securepassword",
        )
    )


@pytest_asyncio.fixture
async def second_user(auth_svc: AuthService):
    return await auth_svc.register_user(
        UserCreate(
            username="notify_user_2",
            email="notify_user_2@example.com",
            password="securepassword",
        )
    )


@pytest.mark.asyncio
async def test_follow_notification_enqueues_email(
    user_svc: UserService, first_user, second_user
):
    with patch("notification.task.send_notification_email_task.delay") as mock_delay:
        await user_svc.follow_user(first_user.id, second_user.username)

    mock_delay.assert_called_once()
    payload = mock_delay.call_args.args[0]
    assert payload["notification_type"] == NotificationType.FOLLOW.value
    assert payload["recipient_email"] == second_user.email


@pytest.mark.asyncio
async def test_follow_notification_skips_disabled_recipient(
    user_svc: UserService,
    first_user,
    second_user,
    db_session: AsyncSession,
):
    user_repo = UserRepository(db_session)
    await user_repo.update_user(
        second_user.id,
        UserUpdate(email_notifications_enabled=False),
    )
    await db_session.commit()

    with patch("notification.task.send_notification_email_task.delay") as mock_delay:
        await user_svc.follow_user(first_user.id, second_user.username)

    mock_delay.assert_not_called()


@pytest.mark.asyncio
async def test_reply_notification_targets_parent_comment_author(
    pin_svc,
    comment_svc_with_notifications: CommentService,
    first_user,
    second_user,
):
    pin = await pin_svc.create_pin(
        mock_image_file(), first_user, PinCreate(title="Reply Test")
    )
    root_comment = await comment_svc_with_notifications.add_comment(
        pin.id, None, first_user.id, "Root comment"
    )

    with patch("notification.task.send_notification_email_task.delay") as mock_delay:
        await comment_svc_with_notifications.add_comment(
            pin.id, root_comment.id, second_user.id, "Reply body"
        )

    mock_delay.assert_called_once()
    payload = mock_delay.call_args.args[0]
    assert payload["notification_type"] == NotificationType.COMMENT_REPLY.value
    assert payload["recipient_email"] == first_user.email


@pytest.mark.asyncio
async def test_pin_save_on_secret_board_omits_board_title(
    board_svc: BoardService,
    pin_svc,
    first_user,
    second_user,
):
    pin = await pin_svc.create_pin(
        mock_image_file(), first_user, PinCreate(title="Save Test")
    )
    board = await board_svc.create_board(
        second_user,
        BoardCreate(title="Secret Saves", visibility="secret"),
    )

    with patch("notification.task.send_notification_email_task.delay") as mock_delay:
        await board_svc.add_pin_to_board(board.id, pin.id, second_user)

    mock_delay.assert_called_once()
    payload = mock_delay.call_args.args[0]
    assert payload["notification_type"] == NotificationType.PIN_SAVE.value
    assert payload["recipient_email"] == first_user.email
    assert "Secret Saves" not in payload["text_body"]
