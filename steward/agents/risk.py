"""RiskAgent - spots the quiet leavers before they leave.

Churn in small organizations is almost never announced. Attendance thins,
payments slip, and one day someone stops coming. Each signal on its own is
ignorable; together they are a prediction. This agent combines them, changes the
client's status, and tells the owner what to do about it while there is still
time to do it.
"""

from __future__ import annotations

from typing import Any

from ..models import Decision
from ..notify import send
from ..gemini import get_client
from .base import Agent, TickContext


class RiskAgent(Agent):
    name = "risk"
    purpose = "Detects churn risk from attendance and payment signals, recommends action."

    def tick(self, ctx: TickContext) -> list[Decision]:
        clients = [c for c in ctx.query("clients") if c.get("status") in ("active", "at_risk")]
        sessions = ctx.query("sessions")
        invoices = ctx.query("invoices")

        decisions: list[Decision] = []
        for client in clients:
            signals = self._signals(ctx, client, sessions, invoices)
            at_risk = signals["attendance_ratio"] is not None and (
                signals["attendance_ratio"] < ctx.vertical.attendance_risk_ratio
                or signals["unpaid_invoices"] >= 2
            )

            already_flagged = client.get("status") == "at_risk"

            if at_risk and not already_flagged:
                decisions.append(self._flag(ctx, client, signals))
            elif not at_risk and already_flagged:
                decisions.append(self._clear(ctx, client, signals))

        return decisions

    # -- helpers ---------------------------------------------------------

    def _signals(
        self,
        ctx: TickContext,
        client: dict[str, Any],
        sessions: list[dict],
        invoices: list[dict],
    ) -> dict[str, Any]:
        window = ctx.vertical.attendance_window
        past = sorted(
            (
                s
                for s in sessions
                if s["client_id"] == client["id"]
                and s["scheduled_at"] <= ctx.now
                and s.get("attended") is not None
            ),
            key=lambda s: s["scheduled_at"],
            reverse=True,
        )[:window]

        attended = sum(1 for s in past if s["attended"])
        ratio = (attended / len(past)) if past else None
        unpaid = [
            i
            for i in invoices
            if i["client_id"] == client["id"]
            and i["status"] == "unpaid"
            and i["due_date"] <= ctx.now
        ]

        return {
            "client": client["name"],
            "sessions_considered": len(past),
            "attended": attended,
            "attendance_ratio": round(ratio, 2) if ratio is not None else None,
            "unpaid_invoices": len(unpaid),
            "amount_outstanding": round(sum(i["amount"] for i in unpaid), 2),
        }

    # -- actions ---------------------------------------------------------

    def _flag(self, ctx: TickContext, client: dict[str, Any], signals: dict[str, Any]) -> Decision:
        v = ctx.vertical
        result = get_client().decide(
            system=self.system_prompt(ctx),
            prompt=(
                f"{client['name']} is showing churn signals: attended "
                f"{signals['attended']} of the last {signals['sessions_considered']} "
                f"{v.session_plural} (ratio {signals['attendance_ratio']}), with "
                f"{signals['unpaid_invoices']} overdue invoice(s) totalling "
                f"{signals['amount_outstanding']}. Monthly fee is "
                f"{client['monthly_fee']:.2f}. Recommend the single most effective "
                f"next step for the owner - be concrete about who contacts whom and "
                f"what they say. Two sentences."
            ),
            schema_hint=(
                '{"recommendation": string, "rationale": string, '
                '"severity": "watch"|"act_now"}'
            ),
            fallback={
                "recommendation": (
                    f"Call {client['payer_name']} personally this week to ask what "
                    f"has changed before raising the unpaid balance."
                ),
                "rationale": (
                    f"attendance {signals['attendance_ratio']}, "
                    f"{signals['unpaid_invoices']} unpaid"
                ),
                "severity": "act_now" if signals["unpaid_invoices"] >= 2 else "watch",
            },
        )

        decision = self.record(
            ctx,
            entity_type="client",
            entity_id=client["id"],
            observed=signals,
            decision=f"flag_at_risk ({result.data.get('severity', 'watch')})",
            rationale=result.data.get("rationale", "combined attendance and payment signals"),
            action="flag",
            confidence=0.82,
            model=result.model,
            latency_ms=result.latency_ms,
        )

        client["status"] = "at_risk"
        ctx.store.put("clients", client)

        send(
            org_id=ctx.org["id"],
            to_name=ctx.org["owner_name"],
            to_address=ctx.org["owner_email"],
            subject=f"At risk: {client['name']} ({client['monthly_fee']:.0f}/mo)",
            body=(
                f"Signals: attended {signals['attended']}/"
                f"{signals['sessions_considered']} recent {v.session_plural}; "
                f"{signals['unpaid_invoices']} overdue invoice(s) "
                f"({signals['amount_outstanding']}).\n\n"
                f"Recommended: {result.data.get('recommendation', '')}"
            ),
            decision_id=decision.id,
        )
        return decision

    def _clear(self, ctx: TickContext, client: dict[str, Any], signals: dict[str, Any]) -> Decision:
        decision = self.record(
            ctx,
            entity_type="client",
            entity_id=client["id"],
            observed=signals,
            decision="clear_at_risk",
            rationale=(
                f"Attendance recovered to {signals['attendance_ratio']} with "
                f"{signals['unpaid_invoices']} overdue invoice(s). Risk signals "
                f"no longer met."
            ),
            action="flag",
            confidence=0.8,
        )
        client["status"] = "active"
        ctx.store.put("clients", client)
        return decision
