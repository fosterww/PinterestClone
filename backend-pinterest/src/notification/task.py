from celery.utils.log import get_task_logger

from core.infra.celery import celery_app
from core.infra.metrics import record_notification_event
from notification.schemas import EmailNotificationPayload
from notification.sender import EmailSender

task_logger = get_task_logger(__name__)


@celery_app.task(
    name="send_notification_email_task",
    queue="default",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_notification_email_task(payload: dict) -> None:
    notification = EmailNotificationPayload.model_validate(payload)
    try:
        EmailSender().send(notification)
    except Exception:
        record_notification_event(notification.notification_type.value, "failed")
        raise

    record_notification_event(notification.notification_type.value, "sent")
    task_logger.info(
        "Notification email sent: type=%s recipient=%s",
        notification.notification_type.value,
        notification.recipient_email,
    )
