"""Seed a realistic coaching center so every agent has something real to decide.

Shaped so one tick exercises all five loops: documentation gaps for chase, an
invoice at each rung of the collections ladder, a week of notes for reports, and
one student whose attendance and payments have both slipped for risk.
"""

from __future__ import annotations

import os
import random
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.models import Client, Invoice, Note, Org, Session, Staff, utcnow  # noqa: E402
from steward.store import get_store  # noqa: E402

random.seed(7)

NOTE_BANK = [
    "Worked through quadratic factorisation. Got the method, still slow on signs.",
    "Reading comprehension - can summarise but struggles to infer motive.",
    "Fractions revision. Much more confident than last month.",
    "Essay structure. Intro is strong now, conclusions still rushed.",
    "Went over the mock paper. Lost marks on units, not on method.",
    "Times tables drill, 6s and 7s. Speed improving.",
    "Trigonometry intro. Needed three attempts at SOHCAHTOA but got there.",
    "Spelling test 14/20. The silent-letter group is the weak spot.",
]


def main() -> None:
    store = get_store()
    now = utcnow()

    org = Org(
        name="Northside Coaching",
        owner_name="Rina",
        owner_email="owner@northside.example",
        vertical="coaching_center",
    )
    store.put("orgs", org)

    teachers = [
        Staff(org_id=org.id, name="Imran", email="imran@northside.example"),
        Staff(org_id=org.id, name="Sadia", email="sadia@northside.example"),
        Staff(org_id=org.id, name="Tanvir", email="tanvir@northside.example"),
    ]
    for teacher in teachers:
        store.put("staff", teacher)

    # (name, payer, fee, attendance pattern over last 6 sessions, documented?)
    roster = [
        ("Ayaan", "Nusrat", 60.0, [1, 1, 1, 1, 1, 1], True),
        ("Mahi", "Farhana", 60.0, [1, 1, 0, 1, 1, 1], True),
        ("Zara", "Kamrul", 75.0, [1, 0, 0, 0, 1, 0], False),   # risk: attendance + unpaid
        ("Rafi", "Shirin", 60.0, [1, 1, 1, 0, 1, 1], True),
        ("Nabil", "Jahangir", 90.0, [1, 1, 1, 1, 0, 1], False),  # chase: no notes filed
        ("Tasnim", "Rubel", 60.0, [1, 1, 1, 1, 1, 0], True),
    ]

    students = []
    for name, payer, fee, pattern, documented in roster:
        client = Client(
            org_id=org.id,
            name=name,
            payer_name=payer,
            payer_email=f"{payer.lower()}@example.com",
            payer_phone="+880000000000",
            monthly_fee=fee,
            enrolled_at=now - timedelta(days=random.randint(90, 400)),
        )
        store.put("clients", client)
        students.append((client, pattern, documented))

        # Six weekly sessions, most recent three days ago.
        for index, attended in enumerate(reversed(pattern)):
            teacher = teachers[index % len(teachers)]
            scheduled = now - timedelta(days=3 + index * 7)
            session = Session(
                org_id=org.id,
                client_id=client.id,
                staff_id=teacher.id,
                scheduled_at=scheduled,
                attended=bool(attended),
            )
            store.put("sessions", session)

            # Notes exist for documented students on attended sessions only.
            if attended and documented:
                store.put(
                    "notes",
                    Note(
                        org_id=org.id,
                        session_id=session.id,
                        staff_id=teacher.id,
                        client_id=client.id,
                        body=random.choice(NOTE_BANK),
                        created_at=scheduled + timedelta(hours=2),
                    ),
                )

    by_name = {c.name: c for c, _, _ in students}

    # One invoice at each rung of the escalation ladder (3 / 10 / 21 days).
    invoice_plan = [
        ("Ayaan", 30, "paid"),
        ("Mahi", 2, "unpaid"),     # inside grace period -> agent holds
        ("Rafi", 6, "unpaid"),     # rung 1
        ("Nabil", 13, "unpaid"),   # rung 2
        ("Zara", 26, "unpaid"),    # rung 3, final
        ("Zara", 56, "unpaid"),    # second unpaid cycle -> risk signal
        ("Tasnim", 40, "paid"),
    ]
    for name, days_ago, status in invoice_plan:
        client = by_name[name]
        due = now - timedelta(days=days_ago)
        invoice = Invoice(
            org_id=org.id,
            client_id=client.id,
            period=f"{due:%Y-%m}",
            amount=client.monthly_fee,
            due_date=due,
            status=status,
        )
        if status == "paid":
            invoice.paid_at = due - timedelta(days=1)
        store.put("invoices", invoice)

    print(f"Seeded org {org.id} - {org.name}")
    print(f"  {len(teachers)} teachers, {len(students)} students")
    print(f"  {len(invoice_plan)} invoices")
    print("\nRun the agents:  python scripts/tick.py")


if __name__ == "__main__":
    main()
