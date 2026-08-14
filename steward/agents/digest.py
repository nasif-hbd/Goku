"""DigestAgent - the one message the owner is expected to read.

Runs last on each tick and reports on the other agents: what was handled without
them, and the short list that genuinely needs a human. The point is that an
owner who reads only this stays fully informed.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from ..gemini import get_client
from ..models import Decision
from ..notify import send
from .base import Agent, TickContext

MIN_INTERVAL_HOURS = 20


class DigestAgent(Agent):
    name = "digest"
    purpose = "Summarises agent activity for the owner and surfaces what needs a human."

    def tick(self, ctx: TickContext) -> list[Decision]:
        prior = ctx.store.query("decisions", org_id=ctx.org["id"], agent=self.name)
        last_run = max((d["created_at"] for d in prior), default=None)

        if last_run and (ctx.now - last_run) < timedelta(hours=MIN_INTERVAL_HOURS):
            return []

        since = last_run or (ctx.now - timedelta(days=1))
        activity = [
            d
            for d in ctx.store.query("decisions", org_id=ctx.org["id"])
            if d["agent"] != self.name and d["created_at"] > since
        ]

        if not activity:
            return [
                self.record(
                    ctx,
                    entity_type="org",
                    entity_id=ctx.org["id"],
                    observed={"decisions_since_last": 0},
                    decision="skip_nothing_to_report",
                    rationale="No agent activity since the last digest; a digest would be noise.",
                    action="none",
                    confidence=1.0,
                )
            ]

        return [self._digest(ctx, activity, since)]

    def _digest(
        self, ctx: TickContext, activity: list[dict[str, Any]], since
    ) -> Decision:
        by_agent = Counter(d["agent"] for d in activity)
        escalations = [d for d in activity if d["action"] == "escalate"]
        flags = [d for d in activity if d["action"] == "flag"]
        sent = [d for d in activity if d["action"] == "send_message"]

        lines = "\n".join(
            f"- [{d['agent']}] {d['decision']}: {d['rationale']}"
            for d in sorted(activity, key=lambda d: d["created_at"])
        )

        result = get_client().decide(
            system=self.system_prompt(ctx),
            prompt=(
                f"Write the owner's digest for {ctx.org['owner_name']} covering "
                f"agent activity since {since:%b %d %H:%M}. Activity:\n\n{lines}\n\n"
                f"Open with one sentence on what was handled automatically "
                f"({len(sent)} messages sent). Then, under a short heading, list only "
                f"the items that genuinely need {ctx.org['owner_name']} to act "
                f"({len(escalations)} escalation(s), {len(flags)} risk flag(s)), each "
                f"with the specific action. If nothing needs them, say so plainly. "
                f"No filler, no praise, under 150 words."
            ),
            schema_hint='{"subject": string, "body": string, "rationale": string}',
            fallback={
                "subject": (
                    f"Daily digest - {len(sent)} handled, "
                    f"{len(escalations) + len(flags)} need you"
                ),
                "body": (
                    f"Handled automatically: {len(sent)} messages.\n\n"
                    f"Needs you:\n{lines if (escalations or flags) else 'Nothing today.'}"
                ),
                "rationale": f"{len(activity)} decisions across {len(by_agent)} agents",
            },
        )

        decision = self.record(
            ctx,
            entity_type="org",
            entity_id=ctx.org["id"],
            observed={
                "decisions_since_last": len(activity),
                "by_agent": dict(by_agent),
                "messages_sent": len(sent),
                "escalations": len(escalations),
                "flags": len(flags),
            },
            decision="send_owner_digest",
            rationale=result.data.get("rationale", f"{len(activity)} decisions summarised"),
            action="send_message",
            confidence=0.9,
            model=result.model,
            latency_ms=result.latency_ms,
        )

        send(
            org_id=ctx.org["id"],
            to_name=ctx.org["owner_name"],
            to_address=ctx.org["owner_email"],
            subject=result.data.get("subject", "Daily digest"),
            body=result.data.get("body", ""),
            decision_id=decision.id,
        )
        return decision
