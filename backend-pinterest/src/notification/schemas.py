import uuid
from enum import Enum

from pydantic import BaseModel, EmailStr


class NotificationType(str, Enum):
    FOLLOW = "Follow"
    PIN_COMMENT = "Pin comment"
    COMMENT_REPLY = "Comment reply"
    PIN_SAVE = "Pin save"


class EmailNotificationPayload(BaseModel):
    notification_type: NotificationType
    recipient_id: uuid.UUID
    recipient_email: EmailStr
    recipient_username: str
    subject: str
    text_body: str
    html_body: str | None = None
