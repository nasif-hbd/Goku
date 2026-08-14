# Submission notes — Build with Gemini XPRIZE

Working draft of the Devpost submission. Verify every rule claim against
<https://xprize.devpost.com/rules> before submitting.

---

## Category

**Small Business Services.**

The customer is a small organization — a coaching center, a clinic, a two-person
agency — that runs on unpaid administrative labour. Steward removes that labour
rather than digitising it.

Entrepreneurship & Job Creation is a defensible second choice, but the primary
claim is straightforward: this is back-office capability that small businesses
currently cannot afford to staff.

## Requirement compliance

| Requirement | How it is met | Where |
|---|---|---|
| Gemini API call in the deployed app | Every agent judgement and every drafted message routes through `GeminiClient.decide` | `steward/gemini.py` |
| At least one Google Cloud product | Cloud Run, Firestore, Cloud Scheduler, Secret Manager | `deploy/deploy.sh` |
| Deployed and reachable | Cloud Run service, public URL | `deploy/deploy.sh` |
| Public repository | This repository | — |
| Category selected | Small Business Services | above |
| Demo video under 3 minutes | Script in `DEMO_SCRIPT.md` | — |

## Mapping to the three judging criteria

### 1. AI-native operations

The distinction the rubric is testing is whether AI *runs* the business or
merely decorates it. Steward's agents are the operators, and the decision log is
the evidence:

- Agents run unattended on a Cloud Scheduler tick. No human initiates them.
- Each agent **observes → decides → acts**, and writes a `Decision` record with
  what it saw, what it chose, why, and its confidence — including when it
  chooses *not* to act.
- The judgement calls are real, not cosmetic:
  - `collections` holds during the grace period rather than chasing on day one,
    and offers a payment plan based on payment history.
  - `reports` refuses to send a progress update when there is no material,
    rather than generating filler.
  - `chase` writes off documentation older than the chase window instead of
    nagging indefinitely.
  - `risk` combines two weak signals into one actionable prediction.
- Escalation converges: nudge, second nudge, hand to owner, stop. An agent that
  never stops is an agent nobody keeps installed.

The honest boundary: money movement and identity are not autonomous. Invoices
are marked paid by a human, and no agent can spend. That is a deliberate limit,
not an unfinished feature.

### 2. Business viability

- **Buyer:** owner-operator of a 5–50 client organization.
- **Pain:** the admin loop is real work that currently gets done badly at night
  or not at all. Unpaid invoices are money already earned and not collected.
- **Pricing:** flat monthly per organization, below the cost of the part-time
  administrator it displaces.
- **ROI:** one recovered invoice covers the subscription for months. This is the
  argument that closes the sale, and it is arithmetic, not a pitch.
- **Wedge:** collections. It is the loop with a number attached, so it is the
  easiest to prove and the easiest to sell.

### 3. Category impact

Small organizations lose margin to administrative work that larger competitors
staff away. Every hour a coaching center owner spends chasing fees is an hour
not spent teaching or selling, and the work is disproportionately borne by
owner-operators in markets where hiring an administrator is not an option.

Steward gives a six-person organization the back office of a sixty-person one.

## What is genuinely built

Verified working, end to end:

- Five agent loops, all firing on real seeded data
- Decision logging with observations, rationale, confidence, model, latency
- Convergent escalation (verified across five consecutive ticks)
- Dashboard and per-decision drill-down
- SQLite and Firestore backends behind one interface
- Cloud Run packaging and a deploy script

## What is not built

Stated plainly, because the verification stage will find it anyway:

- **No revenue yet.** No paying customers at the time of writing.
- **No payment provider.** Invoices are marked paid manually; Stripe is not
  integrated.
- **Email only.** SMS and WhatsApp are not wired up.
- **Single-tenant dashboard.** Serves the first org in the store; no auth.
- **Container not built.** The Dockerfile is written but has not been built in
  CI — Docker was unavailable in the development sandbox.

## The competitive reality

This project began three days before the submission deadline. The competition
scores ninety days of accumulated traction — real users, real revenue, verified
by Hacker Fund. Steward has none of that history and cannot manufacture it.

The submission is therefore honest about what it is: a working autonomous
operations system with a credible business behind it and no trading record. It
will score on AI-native operations and lose on business viability.

The build is worth more than the placing. The loops work, the wedge is real, and
the same code with ninety days of customers behind it is a different submission
entirely.
