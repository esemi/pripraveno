"""Отправка уведомления об изменении статусов по email через SMTP (Gmail).

Креды берём из окружения, чтобы не хранить пароль в коде/git:
    IPC_SMTP_USER      — логин SMTP (обычно gmail-адрес отправителя)
    IPC_SMTP_PASSWORD  — app-пароль Google (не обычный пароль аккаунта)
    IPC_MAIL_TO        — получатель (по умолчанию = IPC_SMTP_USER)
    IPC_SMTP_HOST      — SMTP-хост (по умолчанию smtp.gmail.com)
    IPC_SMTP_PORT      — порт STARTTLS (по умолчанию 587)

Если IPC_SMTP_USER/IPC_SMTP_PASSWORD не заданы — отправка считается
не сконфигурированной (is_configured() == False), письмо не шлётся.
"""
import os
import smtplib
from email.message import EmailMessage


class Mailer:
    """Тонкая обёртка над smtplib для одного письма."""

    def __init__(self) -> None:
        self.user = os.environ.get("IPC_SMTP_USER", "")
        self.password = os.environ.get("IPC_SMTP_PASSWORD", "")
        self.mail_to = os.environ.get("IPC_MAIL_TO") or self.user
        self.host = os.environ.get("IPC_SMTP_HOST", "smtp.gmail.com")
        self.port = int(os.environ.get("IPC_SMTP_PORT", "587"))

    def is_configured(self) -> bool:
        return bool(self.user and self.password and self.mail_to)

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = self.mail_to
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(self.user, self.password)
            smtp.send_message(msg)
