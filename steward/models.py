"""Domain records.

Deliberately flat and dict-convertible so the same shapes persist to SQLite rows
and Firestore documents without an ORM in the middle.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Base:
    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in asdict(self).items():
            out[key] = value.isoformat() if isinstance(value, datetime) else value
        return out


@dataclass
class Org(Base):
    name: str
    owner_name: str
    owner_email: str
    vertical: str = "coaching_center"
    timezone: str = "UTC"
    id: str = field(default_factory=lambda: new_id("org"))


@dataclass
class Staff(Base):
    org_id: str
    name: str
    email: str
    phone: str = ""
    active: bool = True
    id: str = field(default_factory=lambda: new_id("stf"))


@dataclass
class Client(Base):
    """A student / patient / client, plus whoever pays and receives reports."""

    org_id: str
    name: str
    payer_name: str
    payer_email: str
    monthly_fee: float
    payer_phone: str = ""
    status: str = "active"  # active | at_risk | paused | churned
    enrolled_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("cli"))


@dataclass
class Session(Base):
    org_id: str
    client_id: str
    staff_id: str
    scheduled_at: datetime
    # None = not yet marked. Agents treat unmarked past sessions as a data gap,
    # not as an absence.
    attended: bool | None = None
    id: str = field(default_factory=lambda: new_id("ses"))


@dataclass
class Note(Base):
    org_id: str
    session_id: str
    staff_id: str
    client_id: str
    body: str
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("not"))


@dataclass
class Invoice(Base):
    org_id: str
    client_id: str
    period: str  # e.g. "2026-08"
    amount: float
    due_date: datetime
    status: str = "unpaid"  # unpaid | paid | written_off
    paid_at: datetime | None = None
    reminders_sent: int = 0
    id: str = field(default_factory=lambda: new_id("inv"))

    def days_overdue(self, now: datetime | None = None) -> int:
        if self.status != "unpaid":
            return 0
        now = now or utcnow()
        return max(0, (now - self.due_date).days)


@dataclass
class Decision(Base):
    """The audit record for one autonomous agent action.

    This is the product's spine: every agent writes one of these before acting,
    capturing what it saw, what it chose, and why.
    """

    org_id: str
    agent: str
    entity_type: str
    entity_id: str
    observed: dict[str, Any]
    decision: str
    rationale: str
    action: str  # send_message | escalate | flag | none
    confidence: float = 0.0
    model: str = ""
    latency_ms: int = 0
    autonomous: bool = True
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("dec"))


@dataclass
class Message(Base):
    org_id: str
    channel: str  # email | sms | whatsapp | dashboard
    to_name: str
    to_address: str
    subject: str
    body: str
    decision_id: str = ""
    status: str = "sent"  # sent | queued_for_approval | failed
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("msg"))
