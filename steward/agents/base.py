"""Agent framework.

An agent observes org state on a tick, decides what (if anything) warrants
action, records a Decision explaining itself, and then acts. The Decision is
written whether or not the agent acts - "looked and chose not to act" is
information the owner needs, and it is what distinguishes a decision log from a
send log.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import VerticalProfile, settings
from ..models import Decision, Message, utcnow
from ..store import Store, get_store


@dataclass
class TickContext:
    org: dict[str, Any]
    now: datetime
    store: Store
    vertical: VerticalProfile

    def query(self, collection: str, **equals: Any) -> list[dict]:
        return self.store.query(collection, org_id=self.org["id"], **equals)


class Agent:
    """Base class. Subclasses implement observe/act inside `tick`."""

    name: str = "agent"
    purpose: str = ""

    def tick(self, ctx: TickContext) -> list[Decision]:
        raise NotImplementedError

    # -- helpers ---------------------------------------------------------

    def record(
        self,
        ctx: TickContext,
        *,
        entity_type: str,
        entity_id: str,
        observed: dict[str, Any],
        decision: str,
        rationale: str,
        action: str,
        confidence: float = 0.0,
        model: str = "",
        latency_ms: int = 0,
    ) -> Decision:
        record = Decision(
            org_id=ctx.org["id"],
            agent=self.name,
            entity_type=entity_type,
            entity_id=entity_id,
            observed=observed,
            decision=decision,
            rationale=rationale,
            action=action,
            confidence=confidence,
            model=model,
            latency_ms=latency_ms,
            created_at=ctx.now,
        )
        ctx.store.put("decisions", record)
        return record

    def system_prompt(self, ctx: TickContext) -> str:
        v = ctx.vertical
        return (
            f"You operate the back office of a small {v.org_label} called "
            f"\"{ctx.org['name']}\". You handle {v.client_plural}, their "
            f"{v.payer_label}s, and the {v.staff_plural} who teach them. "
            f"Write in a {v.tone} tone. Be specific and never invent facts that "
            f"are not in the data you are given. Currency is {settings.currency}."
        )


def run_all(agents: list[Agent], org: dict[str, Any], now: datetime | None = None) -> dict:
    """Run one tick across all agents. One agent failing must not stop the rest."""
    from ..config import VERTICALS

    store = get_store()
    ctx = TickContext(
        org=org,
        now=now or utcnow(),
        store=store,
        vertical=VERTICALS.get(org.get("vertical", ""), settings.vertical),
    )

    summary: dict[str, Any] = {"org_id": org["id"], "ran_at": ctx.now.isoformat(), "agents": []}
    for agent in agents:
        try:
            decisions = agent.tick(ctx)
            summary["agents"].append(
                {
                    "agent": agent.name,
                    "decisions": len(decisions),
                    "acted": sum(1 for d in decisions if d.action != "none"),
                    "ok": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            summary["agents"].append(
                {"agent": agent.name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            )
    return summary


def latest_message_for(store: Store, decision_id: str) -> Message | None:
    rows = store.query("messages", decision_id=decision_id)
    return rows[0] if rows else None
