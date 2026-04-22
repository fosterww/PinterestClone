import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from core.config import settings
from notification.schemas import EmailNotificationPayload


class EmailSender:
    def __init__(self) -> None:
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.email_from_address = settings.email_from_address
        self.email_from_name = settings.email_from_name

    def send(self, payload: EmailNotificationPayload) -> None:
        if not self.smtp_host:
            raise RuntimeError("SMTP host is not configured")
        if not self.email_from_address:
            raise RuntimeError("Email sender address is not configured")

        message = EmailMessage()
        message["Subject"] = payload.subject
        message["To"] = payload.recipient_email
        message["From"] = formataddr((self.email_from_name, self.email_from_address))
        message.set_content(payload.text_body)

        if payload.html_body:
            message.add_alternative(payload.html_body, subtype="html")

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            if self.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self.smtp_username:
                smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)
