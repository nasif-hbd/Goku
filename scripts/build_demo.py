"""Build the static demo page from a real application run.

Pipeline:  seed.py -> export_run.py -> build_demo.py

The page is generated, never hand-edited: edit `demo/template.html` and rebuild,
so the published demo always carries genuine agent output rather than sample
data that has drifted from what the code actually does.

Writes two identical outputs:
  demo/index.html   source of truth, published as a hosted artifact
  docs/index.html   served by GitHub Pages (Pages serves / or /docs only)
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "demo" / "template.html"
RUN_JSON = ROOT / "demo" / "run.json"
OUTPUTS = [ROOT / "demo" / "index.html", ROOT / "docs" / "index.html"]
PLACEHOLDER = "__RUN_DATA__"


def ensure_run() -> dict:
    """Reuse an existing export, or produce one from a fresh seeded database."""
    if RUN_JSON.exists():
        return json.loads(RUN_JSON.read_text())

    print("No run.json - seeding and exporting a fresh run")
    env = {**os.environ, "STEWARD_DB": str(ROOT / "build-demo.db")}
    db = pathlib.Path(env["STEWARD_DB"])
    db.unlink(missing_ok=True)
    for script in ("seed.py", "export_run.py"):
        args = [sys.executable, str(ROOT / "scripts" / script)]
        if script == "export_run.py":
            args.append(str(RUN_JSON))
        subprocess.run(args, check=True, env=env, cwd=ROOT)
    db.unlink(missing_ok=True)
    return json.loads(RUN_JSON.read_text())


def main() -> None:
    template = TEMPLATE.read_text()
    if PLACEHOLDER not in template:
        raise SystemExit(f"{TEMPLATE} is missing the {PLACEHOLDER} placeholder")

    run = ensure_run()
    page = template.replace(PLACEHOLDER, json.dumps(run, separators=(",", ":")))

    for out in OUTPUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page)

    decisions = sum(len(t) for t in run["ticks"])
    print(f"Built {decisions} decisions across {len(run['ticks'])} ticks")
    for out in OUTPUTS:
        print(f"  {out.relative_to(ROOT)}  ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
