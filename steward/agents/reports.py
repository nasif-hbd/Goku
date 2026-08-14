"""ReportAgent - turns staff shorthand into the weekly update payers actually read.

Teachers write four-word notes. Parents want to know whether their child is
improving. Bridging that gap by hand is an hour a week per class, so it does not
happen. The agent does it from the notes already in the system, and refuses to
send anything when there is no real material - a fabricated progress report is
worse than none.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..gemini import get_client
from ..models import Decision
from ..notify import send
from .base import Agent, TickContext

REPORT_INTERVAL_DAYS = 7


class ReportAgent(Agent):
    name = "reports"
    purpose = "Compiles staff notes into periodic progress reports for payers."

    def tick(self, ctx: TickContext) -> list[Decision]:
        window_start = ctx.now - timedelta(days=REPORT_INTERVAL_DAYS)
        clients = [c for c in ctx.query("clients") if c.get("status") in ("active", "at_risk")]
        all_notes = ctx.query("notes")
        staff_by_id = {s["id"]: s for s in ctx.query("staff")}

        decisions: list[Decision] = []
        for client in clients:
            if self._reported_recently(ctx, client["id"], window_start):
                continue

            notes = [
                n
                for n in all_notes
                if n["client_id"] == client["id"] and n["created_at"] >= window_start
            ]
            if not notes:
                decisions.append(self._skip(ctx, client))
                continue

            decisions.append(self._report(ctx, client, notes, staff_by_id))

        return decisions

    # -- helpers ---------------------------------------------------------

    def _reported_recently(self, ctx: TickContext, client_id: str, since) -> bool:
        """True if this client was already handled this period.

        Counts skips as well as sends: having decided once that there is nothing
        to report, re-deciding it on every tick only floods the log.
        """
        prior = ctx.store.query(
            "decisions", org_id=ctx.org["id"], agent=self.name, entity_id=client_id
        )
        return any(d["created_at"] >= since for d in prior)

    # -- actions ---------------------------------------------------------

    def _skip(self, ctx: TickContext, client: dict[str, Any]) -> Decision:
        v = ctx.vertical
        return self.record(
            ctx,
            entity_type="client",
            entity_id=client["id"],
            observed={"notes_in_window": 0, "client": client["name"]},
            decision="skip_no_material",
            rationale=(
                f"No {v.note_label}s filed for {client['name']} this period. Sending a "
                f"report with nothing in it would damage trust; the gap is the "
                f"chase agent's problem, not a report to write around."
            ),
            action="none",
            confidence=0.95,
        )

    def _report(
        self,
        ctx: TickContext,
        client: dict[str, Any],
        notes: list[dict[str, Any]],
        staff_by_id: dict[str, dict],
    ) -> Decision:
        v = ctx.vertical
        rendered = "\n".join(
            f"- [{n['created_at']:%b %d}] {staff_by_id.get(n['staff_id'], {}).get('name', 'staff')}: "
            f"{n['body']}"
            for n in sorted(notes, key=lambda n: n["created_at"])
        )

        result = get_client().decide(
            system=self.system_prompt(ctx),
            prompt=(
                f"Write the weekly progress update for {client['name']}, addressed to "
                f"{client['payer_name']} ({v.payer_label}). These are the "
                f"{v.note_label}s filed by {v.staff_plural} this week:\n\n{rendered}\n\n"
                f"Summarise what actually happened, name one concrete strength and one "
                f"thing to work on, and close with a specific suggestion the "
                f"{v.payer_label} can act on at home. Ground every claim in the notes "
                f"above - do not invent progress that is not described. 120 words max."
            ),
            schema_hint=(
                '{"subject": string, "body": string, "rationale": string, '
                '"sentiment": "positive"|"mixed"|"concerning"}'
            ),
            fallback={
                "subject": f"{client['name']} - weekly update",
                "body": (
                    f"Hello {client['payer_name']},\n\nHere is what "
                    f"{client['name']} covered this week:\n\n{rendered}\n\n"
                    f"- {ctx.org['name']}"
                ),
                "rationale": f"compiled from {len(notes)} {v.note_label}s",
                "sentiment": "mixed",
            },
        )

        decision = self.record(
            ctx,
            entity_type="client",
            entity_id=client["id"],
            observed={
                "notes_in_window": len(notes),
                "client": client["name"],
                "sentiment": result.data.get("sentiment"),
            },
            decision="send_progress_report",
            rationale=result.data.get("rationale", f"compiled from {len(notes)} notes"),
            action="send_message",
            confidence=0.88,
            model=result.model,
            latency_ms=result.latency_ms,
        )

        send(
            org_id=ctx.org["id"],
            to_name=client["payer_name"],
            to_address=client["payer_email"],
            subject=result.data.get("subject", f"{client['name']} - weekly update"),
            body=result.data.get("body", ""),
            decision_id=decision.id,
        )

        # A concerning report is a churn signal the owner should see early.
        if result.data.get("sentiment") == "concerning":
            send(
                org_id=ctx.org["id"],
                to_name=ctx.org["owner_name"],
                to_address=ctx.org["owner_email"],
                subject=f"Heads up: {client['name']}'s week read as concerning",
                body=(
                    f"This week's update for {client['name']} was compiled as "
                    f"concerning. Worth a personal call to "
                    f"{client['payer_name']} before they draw their own conclusions."
                ),
                decision_id=decision.id,
            )

        return decision
