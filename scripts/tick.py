"""Run one agent tick from the command line and print what happened.

The same code path Cloud Scheduler hits via POST /tick.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.agents import default_roster, run_all  # noqa: E402
from steward.gemini import get_client  # noqa: E402
from steward.store import get_store  # noqa: E402


def main() -> None:
    store = get_store()
    orgs = store.query("orgs")
    if not orgs:
        print("No org found. Run scripts/seed.py first.")
        raise SystemExit(1)

    org = orgs[0]
    before = len(store.query("decisions", org_id=org["id"]))

    mode = "Gemini API" if get_client().available else "offline fallback (no GEMINI_API_KEY)"
    print(f"Ticking {org['name']} via {mode}\n")

    summary = run_all(default_roster(), org)

    for entry in summary["agents"]:
        if not entry.get("ok"):
            print(f"  {entry['agent']:<12} FAILED  {entry['error']}")
        else:
            print(
                f"  {entry['agent']:<12} {entry['decisions']:>2} decisions, "
                f"{entry['acted']:>2} acted"
            )

    decisions = sorted(
        store.query("decisions", org_id=org["id"]),
        key=lambda d: d["created_at"],
    )[before:]

    print(f"\n{len(decisions)} new decisions:\n")
    for decision in decisions:
        print(f"  [{decision['agent']}] {decision['decision']} -> {decision['action']}")
        print(f"      {decision['rationale']}")

    messages = store.query("messages", org_id=org["id"])
    print(f"\nOutbox now holds {len(messages)} message(s).")


if __name__ == "__main__":
    main()
