"""Vertical-driven configuration.

The agent loops are the product; the vertical only changes vocabulary and a few
policy numbers. Swapping to clinics or NGOs means adding a VerticalProfile here,
not rewriting agents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VerticalProfile:
    key: str
    org_label: str
    # Vocabulary. Agents render prompts and UI through these so one profile swap
    # re-skins the whole product.
    client_label: str
    client_plural: str
    staff_label: str
    staff_plural: str
    session_label: str
    session_plural: str
    payer_label: str  # who receives invoices and progress reports
    note_label: str
    # Policy knobs the agents reason with.
    note_due_hours: int = 24
    # Past this, documentation is not worth chasing - the detail is gone and the
    # nudge only annoys. The agent writes it off once instead of nagging forever.
    note_chase_window_days: int = 14
    fee_escalation_days: tuple[int, ...] = (3, 10, 21)
    attendance_window: int = 6
    attendance_risk_ratio: float = 0.6
    tone: str = "warm, concise, and professional"


VERTICALS: dict[str, VerticalProfile] = {
    "coaching_center": VerticalProfile(
        key="coaching_center",
        org_label="coaching center",
        client_label="student",
        client_plural="students",
        staff_label="teacher",
        staff_plural="teachers",
        session_label="class",
        session_plural="classes",
        payer_label="parent",
        note_label="progress note",
    ),
    "clinic": VerticalProfile(
        key="clinic",
        org_label="clinic",
        client_label="patient",
        client_plural="patients",
        staff_label="practitioner",
        staff_plural="practitioners",
        session_label="appointment",
        session_plural="appointments",
        payer_label="patient",
        note_label="visit note",
        note_due_hours=12,
    ),
    "agency": VerticalProfile(
        key="agency",
        org_label="agency",
        client_label="client",
        client_plural="clients",
        staff_label="team member",
        staff_plural="team members",
        session_label="engagement",
        session_plural="engagements",
        payer_label="client contact",
        note_label="status update",
        fee_escalation_days=(5, 14, 30),
    ),
}


@dataclass
class Settings:
    vertical: VerticalProfile = field(
        default_factory=lambda: VERTICALS[os.getenv("STEWARD_VERTICAL", "coaching_center")]
    )
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    gcp_project: str | None = field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT"))
    sqlite_path: str = field(default_factory=lambda: os.getenv("STEWARD_DB", "steward.db"))
    currency: str = field(default_factory=lambda: os.getenv("STEWARD_CURRENCY", "USD"))
    # Agents draft and send. Set false to require owner approval before anything
    # leaves the building - useful for the first week with a new customer.
    autosend: bool = field(
        default_factory=lambda: os.getenv("STEWARD_AUTOSEND", "true").lower() == "true"
    )

    @property
    def use_firestore(self) -> bool:
        return bool(self.gcp_project) and os.getenv("STEWARD_STORE", "").lower() != "sqlite"


settings = Settings()
