# Evidence pack

Screening and verification is run by Hacker Fund before finalists are chosen.
Unverifiable claims are worse than modest ones — a number you cannot evidence
costs more credibility than it buys.

## What is asked for

| Category | Artifact |
|---|---|
| Revenue | Stripe dashboard export or bank statement, plus a simple P&L |
| Product | Agent execution logs, API usage records, dashboard screenshots |
| Customer | Real customer contacts (name, email, phone), testimonials |
| Expenses | Total spend during the window, including marketing and CAC |

## What Steward can already evidence

**Product evidence is the strong column, and it generates itself.**

- **Agent execution logs.** The `decisions` collection is exactly this — every
  autonomous action with timestamp, observations, rationale, confidence, model,
  and latency. Export it:

  ```bash
  python - <<'PY'
  import csv, json, sys
  sys.path.insert(0, '.')
  from steward.store import get_store
  store = get_store()
  org = store.query('orgs')[0]
  rows = sorted(store.query('decisions', org_id=org['id']), key=lambda d: d['created_at'])
  with open('agent_decisions.csv', 'w', newline='') as fh:
      w = csv.writer(fh)
      w.writerow(['timestamp','agent','decision','rationale','action','confidence','model','latency_ms','observed'])
      for d in rows:
          w.writerow([d['created_at'], d['agent'], d['decision'], d['rationale'],
                      d['action'], d['confidence'], d['model'], d['latency_ms'],
                      json.dumps(d['observed'])])
  print(f'{len(rows)} decisions -> agent_decisions.csv')
  PY
  ```

- **API usage records.** Google Cloud console → APIs & Services → Gemini API,
  request-count graph over the competition window. Screenshot it.

- **Continuous operation.** Cloud Scheduler job history showing ticks firing on
  schedule without human involvement. This is the proof that matters most: it
  demonstrates *unattended* operation, which is the claim being scored.

## What is missing, and what it would take

**Revenue.** Nothing to show. The shortest honest path:

1. Integrate Stripe Checkout for the subscription — roughly half a day.
2. Onboard one organization at a real (small) price.
3. Export the Stripe dashboard as-is. One genuine transaction evidenced beats a
   large number you cannot substantiate.

**Customers.** Requires named, contactable people who agreed to be contacted.
Do not list anyone who has not consented — verification may actually call them,
and a contact who denies being a customer is fatal.

**Expenses.** Keep a running total from the moment there is any spend: Google
Cloud billing, domain, Stripe fees, anything spent on acquisition. A one-page
P&L with real receipts behind it is sufficient at this scale.

## Ground rules

- Never submit a metric you cannot produce a document for.
- If a number is small, submit the small number. Verification is designed to
  catch inflation, and a modest verified figure survives scrutiny that a large
  unverified one does not.
- Screenshot with the URL bar and system clock visible.
- Distinguish demo data from customer data explicitly. The seeded coaching
  center is illustrative and must never be presented as a real customer.
