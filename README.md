# Steward

**Autonomous back-office operations for small organizations.**

Steward is not a place to write tasks down. It is a set of agents that *do* the
recurring administrative work a small organization never gets to: chasing staff
for missing documentation, escalating unpaid invoices, writing the progress
updates clients expect, spotting churn before it happens, and reporting the lot
to the owner once a day.

Every action is preceded by a logged decision explaining what the agent saw and
why it chose to act — or chose not to.

---

## Why this shape

Small organizations do not fail at admin because they lack somewhere to store
tasks; they have WhatsApp, notebooks, and three abandoned Trello boards. They
fail because the work is uncomfortable, repetitive, and always loses to whatever
is urgent. Nobody enjoys asking a parent for money.

So Steward does not add another surface for humans to maintain. The humans keep
teaching; the agents run the loop around them.

## The agents

| Agent | What it does |
|---|---|
| `chase` | Finds sessions with no filed note, nudges the staff member, escalates to the owner after two ignored nudges, and writes off anything older than the chase window rather than nagging forever. |
| `collections` | Walks overdue invoices up a 3/10/21-day escalation ladder, adapting tone to payment history and offering a payment plan to chronically late payers. Holds during the grace period instead of chasing on day one. |
| `reports` | Compiles staff notes into a progress update for the payer. Refuses to send when there is no material — a fabricated report is worse than none. |
| `risk` | Combines attendance decay and unpaid invoices into a churn signal, flags the client, and tells the owner the single most effective next step. |
| `digest` | Runs last. Summarises what was handled automatically and the short list that genuinely needs a human. |

Agents converge: a given issue produces a nudge, a second nudge, an escalation,
and then silence. They do not re-fire on every tick.

## Architecture

```
Cloud Scheduler ──POST /tick──▶ Cloud Run (FastAPI)
                                    │
                                    ├── agents/  observe → decide → act
                                    ├── Gemini API   (judgement + drafting)
                                    └── Firestore    (orgs, decisions, messages)
```

- **Gemini API** backs every judgement call and every drafted message.
- **Firestore** stores documents in production; SQLite backs local development
  through the same interface, so the two behave identically.
- **Cloud Run** hosts the app; **Cloud Scheduler** drives the tick; **Secret
  Manager** holds the API key.

If `GEMINI_API_KEY` is absent the agents fall back to deterministic templates so
the loops stay runnable offline. Fallback output is always tagged as such in the
decision log — it can never be mistaken for a model decision.

## Live demo

A static page that replays a real three-tick run — step through the scheduler
and watch the agents decide, escalate, and then stop.

- **Hosted:** <https://claude.ai/code/artifact/3eb64766-1331-461f-85ca-44f23aa381f9>
- **GitHub Pages:** enable Settings → Pages → source `/docs`, then browse to
  `https://<user>.github.io/<repo>/`

It is generated, not hand-written — `demo/template.html` plus genuine exported
output, so it cannot drift from what the code actually does:

```bash
python scripts/seed.py
python scripts/export_run.py demo/run.json
python scripts/build_demo.py          # -> demo/index.html and docs/index.html
```

The demo is a replay, not the running service, and the page says so. It also
ran without a Gemini key, so message wording came from templates while the
decisions and escalation logic are real.

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

export GEMINI_API_KEY=...          # optional; omit to run on fallbacks
.venv/bin/python scripts/seed.py   # realistic coaching center
.venv/bin/python scripts/tick.py   # run every agent once
.venv/bin/python -m uvicorn steward.main:app --port 8080
```

Open <http://localhost:8080> for the dashboard and decision log.

Run `scripts/tick.py` repeatedly to watch escalation work: nudge, second nudge,
escalation to the owner, then silence.

## Deploy

```bash
export PROJECT_ID=your-gcp-project
export GEMINI_API_KEY=your-key
./deploy/deploy.sh
```

Enables the required APIs, creates the Firestore database, stores the key in
Secret Manager, deploys to Cloud Run, and schedules the tick every four hours.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini API key. Absent ⇒ fallback mode. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model for agent decisions. |
| `GOOGLE_CLOUD_PROJECT` | — | Set ⇒ Firestore backend. |
| `STEWARD_VERTICAL` | `coaching_center` | `coaching_center`, `clinic`, or `agency`. |
| `STEWARD_AUTOSEND` | `true` | `false` queues messages for owner approval. |
| `STEWARD_CURRENCY` | `USD` | Currency label. |
| `SMTP_HOST` etc. | — | Real email delivery. Unset ⇒ messages recorded only. |

## Changing vertical

The agent logic is domain-independent; the vertical supplies vocabulary and a
few policy numbers. `clinic` and `agency` profiles ship in
`steward/config.py` — adding another is one `VerticalProfile`, no agent changes.

## Layout

```
steward/
  agents/       chase, collections, reports, risk, digest
  config.py     vertical profiles and settings
  gemini.py     Gemini client with tagged offline fallback
  models.py     domain records incl. the Decision audit record
  store.py      SQLite + Firestore behind one interface
  main.py       FastAPI app, dashboard, /tick
scripts/        seed.py, tick.py
deploy/         deploy.sh
```

## Status

Working: all five agent loops, decision logging, dashboard, SQLite and Firestore
backends, Gemini integration, Cloud Run packaging.

Not yet done: real payment-provider integration (invoices are marked paid
manually), SMS/WhatsApp delivery (email and dashboard only), and multi-org
authentication — the dashboard currently serves the first org in the store.
