"""Export a real multi-tick run as JSON.

Used to build the static demo page from genuine application output rather than
hand-written sample data.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.agents import default_roster, run_all  # noqa: E402
from steward.models import utcnow  # noqa: E402
from steward.store import get_store  # noqa: E402

TICKS = 3
HOURS_BETWEEN_TICKS = 24


def main() -> None:
    store = get_store()
    org = store.query("orgs")[0]
    base = utcnow()

    tick_groups: list[list[dict]] = []
    seen: set[str] = set()

    for index in range(TICKS):
        # Space ticks a day apart so digest and report intervals behave as they
        # would in production rather than all firing inside one second.
        run_all(default_roster(), org, now=base + timedelta(hours=index * HOURS_BETWEEN_TICKS))
        current = sorted(
            store.query("decisions", org_id=org["id"]), key=lambda d: d["created_at"]
        )
        fresh = [d for d in current if d["id"] not in seen]
        seen.update(d["id"] for d in fresh)
        tick_groups.append(fresh)

    messages_by_decision: dict[str, list[dict]] = {}
    for message in store.query("messages", org_id=org["id"]):
        messages_by_decision.setdefault(message["decision_id"], []).append(message)

    def render(decision: dict) -> dict:
        return {
            "id": decision["id"],
            "agent": decision["agent"],
            "decision": decision["decision"],
            "rationale": decision["rationale"],
            "action": decision["action"],
            "confidence": decision["confidence"],
            "model": decision["model"] or "-",
            "latency_ms": decision["latency_ms"],
            "observed": decision["observed"],
            "messages": [
                {
                    "to_name": m["to_name"],
                    "to_address": m["to_address"],
                    "subject": m["subject"],
                    "body": m["body"],
                    "status": m["status"],
                }
                for m in messages_by_decision.get(decision["id"], [])
            ],
        }

    payload = {
        "org": {"name": org["name"], "owner_name": org["owner_name"]},
        "clients": [
            {
                "name": c["name"],
                "payer_name": c["payer_name"],
                "monthly_fee": c["monthly_fee"],
                "status": c["status"],
            }
            for c in sorted(store.query("clients", org_id=org["id"]), key=lambda c: c["name"])
        ],
        "ticks": [[render(d) for d in group] for group in tick_groups],
    }

    out = sys.argv[1] if len(sys.argv) > 1 else "run.json"
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=1)

    print(f"{sum(len(t) for t in payload['ticks'])} decisions across {TICKS} ticks -> {out}")
    for index, group in enumerate(payload["ticks"], 1):
        acted = sum(1 for d in group if d["action"] != "none")
        print(f"  tick {index}: {len(group):>2} decisions, {acted:>2} acted")


if __name__ == "__main__":
    main()
