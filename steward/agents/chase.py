"""ChaseAgent - gets missing documentation out of staff without the owner asking.

The most reliably neglected task in a small organization: the session happened,
nobody wrote it up, and by the time anyone notices, the detail is gone. This
agent notices the same day, nudges the right person, and escalates to the owner
only when nudging has stopped working.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..gemini import get_client
from ..models import Decision
from ..notify import send
from .base import Agent, TickContext

MAX_NUDGES = 2


class ChaseAgent(Agent):
    name = "chase"
    purpose = "Chases staff for missing session documentation and escalates when ignored."

    def tick(self, ctx: TickContext) -> list[Decision]:
        cutoff = ctx.now - timedelta(hours=ctx.vertical.note_due_hours)
        sessions = ctx.query("sessions")
        notes = ctx.query("notes")
        documented = {note["session_id"] for note in notes}

        staff_by_id = {s["id"]: s for s in ctx.query("staff")}
        clients_by_id = {c["id"]: c for c in ctx.query("clients")}

        stale_before = ctx.now - timedelta(days=ctx.vertical.note_chase_window_days)

        outstanding = [
            s
            for s in sessions
            if s["scheduled_at"] <= cutoff
            and s.get("attended") is not False
            and s["id"] not in documented
        ]

        decisions: list[Decision] = []
        for session in outstanding:
            staff = staff_by_id.get(session["staff_id"])
            client = clients_by_id.get(session["client_id"])
            if not staff or not client:
                continue

            prior_decisions = ctx.store.query(
                "decisions", org_id=ctx.org["id"], agent=self.name, entity_id=session["id"]
            )

            if session["scheduled_at"] < stale_before:
                if not prior_decisions:
                    decisions.append(self._write_off(ctx, session, staff, client))
                continue

            # Once it is the owner's problem the agent is done with it. Without
            # this the escalation re-fires on every tick.
            if any(d["decision"] == "escalate_to_owner" for d in prior_decisions):
                continue

            prior = sum(1 for d in prior_decisions if d["action"] == "send_message")
            hours_late = int((ctx.now - session["scheduled_at"]).total_seconds() // 3600)
            observed = {
                "session_id": session["id"],
                "hours_since_session": hours_late,
                "prior_nudges": prior,
                "staff": staff["name"],
                "client": client["name"],
            }

            if prior >= MAX_NUDGES:
                decisions.append(self._escalate(ctx, session, staff, client, observed))
            else:
                decisions.append(self._nudge(ctx, session, staff, client, observed, hours_late))

        return decisions

    # -- actions ---------------------------------------------------------

    def _write_off(
        self,
        ctx: TickContext,
        session: dict[str, Any],
        staff: dict[str, Any],
        client: dict[str, Any],
    ) -> Decision:
        v = ctx.vertical
        days = (ctx.now - session["scheduled_at"]).days
        return self.record(
            ctx,
            entity_type="session",
            entity_id=session["id"],
            observed={
                "session_id": session["id"],
                "days_since_session": days,
                "staff": staff["name"],
                "client": client["name"],
            },
            decision="write_off_stale",
            rationale=(
                f"{client['name']}'s {v.session_label} with {staff['name']} was "
                f"{days} days ago and is still undocumented. Past the "
                f"{v.note_chase_window_days}-day window the detail is gone, so "
                f"chasing it now costs goodwill and recovers nothing."
            ),
            action="none",
            confidence=0.9,
        )

    def _nudge(
        self,
        ctx: TickContext,
        session: dict[str, Any],
        staff: dict[str, Any],
        client: dict[str, Any],
        observed: dict[str, Any],
        hours_late: int,
    ) -> Decision:
        v = ctx.vertical
        result = get_client().decide(
            system=self.system_prompt(ctx),
            prompt=(
                f"{staff['name']} taught a {v.session_label} with {client['name']} "
                f"{hours_late} hours ago and has not filed the {v.note_label} yet. "
                f"This is nudge number {observed['prior_nudges'] + 1}. "
                f"Write a short direct message to {staff['name']} asking for it. "
                f"One or two sentences. No greeting boilerplate, no guilt."
            ),
            schema_hint='{"subject": string, "body": string, "rationale": string}',
            fallback={
                "subject": f"{v.note_label.title()} needed: {client['name']}",
                "body": (
                    f"Hi {staff['name']}, the {v.note_label} for your "
                    f"{v.session_label} with {client['name']} is still outstanding "
                    f"({hours_late}h). Could you add it today?"
                ),
                "rationale": f"{v.note_label} overdue by {hours_late}h",
            },
        )

        decision = self.record(
            ctx,
            entity_type="session",
            entity_id=session["id"],
            observed=observed,
            decision=f"nudge_staff (attempt {observed['prior_nudges'] + 1})",
            rationale=result.data.get("rationale", "missing documentation"),
            action="send_message",
            confidence=0.9,
            model=result.model,
            latency_ms=result.latency_ms,
        )
        send(
            org_id=ctx.org["id"],
            to_name=staff["name"],
            to_address=staff["email"],
            subject=result.data.get("subject", "Missing note"),
            body=result.data.get("body", ""),
            decision_id=decision.id,
        )
        return decision

    def _escalate(
        self,
        ctx: TickContext,
        session: dict[str, Any],
        staff: dict[str, Any],
        client: dict[str, Any],
        observed: dict[str, Any],
    ) -> Decision:
        v = ctx.vertical
        decision = self.record(
            ctx,
            entity_type="session",
            entity_id=session["id"],
            observed=observed,
            decision="escalate_to_owner",
            rationale=(
                f"{staff['name']} did not respond to {observed['prior_nudges']} nudges; "
                f"further automated reminders are unlikely to work."
            ),
            action="escalate",
            confidence=0.95,
        )
        send(
            org_id=ctx.org["id"],
            to_name=ctx.org["owner_name"],
            to_address=ctx.org["owner_email"],
            subject=f"Needs you: {staff['name']} - missing {v.note_label}",
            body=(
                f"{staff['name']} has not filed the {v.note_label} for "
                f"{client['name']}'s {v.session_label} after "
                f"{observed['prior_nudges']} reminders "
                f"({observed['hours_since_session']}h ago). Stopping automated "
                f"reminders on this one - it needs a word from you."
            ),
            decision_id=decision.id,
        )
        return decision
