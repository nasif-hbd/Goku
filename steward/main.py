"""FastAPI application.

Two surfaces: a dashboard the owner reads, and a /tick endpoint Cloud Scheduler
calls to run the agents. Everything the agents do is visible in the decision log.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .agents import default_roster, run_all
from .config import VERTICALS, settings
from .models import Note, utcnow
from .store import get_store

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Steward", version="0.1.0")


def _current_org() -> dict[str, Any]:
    orgs = get_store().query("orgs")
    if not orgs:
        raise HTTPException(404, "No organization yet - run scripts/seed.py")
    return orgs[0]


def _vertical(org: dict[str, Any]):
    return VERTICALS.get(org.get("vertical", ""), settings.vertical)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    from .gemini import get_client

    return {
        "ok": True,
        "store": "firestore" if settings.use_firestore else "sqlite",
        "gemini_configured": get_client().available,
        "model": settings.gemini_model,
        "vertical": settings.vertical.key,
        "autosend": settings.autosend,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    store = get_store()
    org = _current_org()
    vertical = _vertical(org)

    decisions = sorted(
        store.query("decisions", org_id=org["id"]),
        key=lambda d: d["created_at"],
        reverse=True,
    )
    messages = {m["decision_id"]: m for m in store.query("messages", org_id=org["id"])}
    clients = store.query("clients", org_id=org["id"])
    invoices = store.query("invoices", org_id=org["id"])

    now = utcnow()
    outstanding = [
        i for i in invoices if i["status"] == "unpaid" and i["due_date"] <= now
    ]

    stats = {
        "clients": len([c for c in clients if c["status"] in ("active", "at_risk")]),
        "at_risk": len([c for c in clients if c["status"] == "at_risk"]),
        "decisions": len(decisions),
        "acted": len([d for d in decisions if d["action"] != "none"]),
        "messages": len(messages),
        "outstanding": round(sum(i["amount"] for i in outstanding), 2),
        "mrr": round(sum(c["monthly_fee"] for c in clients if c["status"] != "churned"), 2),
    }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "org": org,
            "v": vertical,
            "stats": stats,
            "decisions": decisions[:60],
            "messages": messages,
            "clients": sorted(clients, key=lambda c: c["name"]),
            "currency": settings.currency,
            "roster": default_roster(),
        },
    )


@app.get("/decisions/{decision_id}", response_class=HTMLResponse)
def decision_detail(request: Request, decision_id: str):
    store = get_store()
    decision = store.get("decisions", decision_id)
    if not decision:
        raise HTTPException(404, "No such decision")
    org = _current_org()
    related = store.query("messages", org_id=org["id"], decision_id=decision_id)
    return templates.TemplateResponse(
        request,
        "decision.html",
        {
            "org": org,
            "v": _vertical(org),
            "decision": decision,
            "messages": related,
        },
    )


@app.post("/tick")
def tick(dry_run: bool = False) -> JSONResponse:
    """Run every agent once. This is the Cloud Scheduler entry point."""
    org = _current_org()
    if dry_run:
        return JSONResponse({"agents": [a.name for a in default_roster()], "dry_run": True})
    summary = run_all(default_roster(), org)
    return JSONResponse(summary)


@app.post("/notes")
def add_note(
    session_id: str = Form(...),
    body: str = Form(...),
) -> RedirectResponse:
    """Staff files a session note - the input the chase and report agents run on."""
    store = get_store()
    org = _current_org()
    session = store.get("sessions", session_id)
    if not session:
        raise HTTPException(404, "No such session")
    store.put(
        "notes",
        Note(
            org_id=org["id"],
            session_id=session_id,
            staff_id=session["staff_id"],
            client_id=session["client_id"],
            body=body.strip(),
        ),
    )
    return RedirectResponse("/", status_code=303)


@app.post("/invoices/{invoice_id}/pay")
def mark_paid(invoice_id: str) -> RedirectResponse:
    store = get_store()
    invoice = store.get("invoices", invoice_id)
    if not invoice:
        raise HTTPException(404, "No such invoice")
    invoice["status"] = "paid"
    invoice["paid_at"] = utcnow().isoformat()
    store.put("invoices", invoice)
    return RedirectResponse("/", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
