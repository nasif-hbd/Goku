"""Seed the demo coaching center from the command line.

The dataset itself lives in steward/seeddata.py so the CLI and the deployed
app's /seed endpoint stay in step.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.seeddata import seed  # noqa: E402
from steward.store import get_store  # noqa: E402


def main() -> None:
    store = get_store()
    if store.query("orgs"):
        print("An organization already exists - nothing to do.")
        return

    result = seed(store)
    print(f"Seeded org {result['org_id']} - {result['org']}")
    print(f"  {result['staff']} teachers, {result['students']} students")
    print(f"  {result['invoices']} invoices")
    print("\nRun the agents:  python scripts/tick.py")


if __name__ == "__main__":
    main()
