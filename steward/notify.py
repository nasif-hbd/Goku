"""Outbound delivery.

Every outbound message is persisted as a Message record regardless of transport,
so the decision -> message chain stays auditable. Transport is pluggable: the
default records only (safe for demos and for a customer's first week), and SMTP
sends for real when configured.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from .config import settings
from .models import Message
from .store import get_store


class Transport:
    name = "record"

    def deliver(self, message: Message) -> str:
        """Return the resulting message status."""
        return "sent" if settings.autosend else "queued_for_approval"


class SMTPTransport(Transport):
    name = "smtp"

    def __init__(self) -> None:
        self.host = os.environ["SMTP_HOST"]
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.environ["SMTP_USER"]
        self.password = os.environ["SMTP_PASSWORD"]
        self.sender = os.getenv("SMTP_FROM", self.user)

    def deliver(self, message: Message) -> str:
        if not settings.autosend:
            return "queued_for_approval"
        email = EmailMessage()
        email["From"] = self.sender
        email["To"] = message.to_address
        email["Subject"] = message.subject
        email.set_content(message.body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(self.user, self.password)
                smtp.send_message(email)
            return "sent"
        except Exception:  # noqa: BLE001 - a failed send must not abort the tick
            return "failed"


def get_transport() -> Transport:
    if os.getenv("SMTP_HOST"):
        return SMTPTransport()
    return Transport()


def send(
    *,
    org_id: str,
    to_name: str,
    to_address: str,
    subject: str,
    body: str,
    decision_id: str,
    channel: str = "email",
) -> Message:
    message = Message(
        org_id=org_id,
        channel=channel,
        to_name=to_name,
        to_address=to_address,
        subject=subject,
        body=body,
        decision_id=decision_id,
    )
    message.status = get_transport().deliver(message)
    get_store().put("messages", message)
    return message
