# Demo video script — 2:45

Judges are not required to watch past three minutes, so the proof has to land
early. The single thing to prove: **agents are making real decisions in
production, unattended.**

Record the screen with voiceover. No title cards, no logo animation, no music
bed — every second spent on production is a second not spent on evidence.

---

## 0:00–0:20 — The problem, in one breath

> "This is a coaching center with six students. Every week the owner has to
> chase teachers for progress notes, chase parents for unpaid fees, write
> progress updates, and notice when a student is quietly drifting away. She does
> none of it, because she's teaching. That's not a software gap — it's unpaid
> labour that never happens."

Show: the dashboard, top stats row.

## 0:20–0:40 — What is actually running

> "Steward runs five agents against her data on a schedule. Nobody starts them.
> Cloud Scheduler calls the tick endpoint, agents observe, decide, and act."

Show: the running-agents panel, then briefly `deploy/deploy.sh` — the Cloud
Scheduler job creation.

## 0:40–1:35 — The decision log (the core of the video)

Scroll the log slowly. Land on **three** decisions — this is what separates the
submission from a CRUD app with a chat button. Do not rush this section.

1. **`hold_grace_period`**
   > "It found an invoice two days overdue and deliberately did nothing —
   > because the first reminder isn't due until day three, and chasing sooner
   > costs goodwill for no gain. That's a decision not to act, logged with its
   > reasoning."

2. **`skip_no_material`**
   > "It was due to send a progress report for Zara, and refused — no teacher
   > notes were filed this week, and a fabricated progress report is worse than
   > none."

3. **`escalate_to_owner`**
   > "It nudged this teacher twice about a missing note, got nothing, and handed
   > it to the owner — then stopped. It doesn't nag forever."

## 1:35–2:05 — Open one decision

Click through to a decision detail page.

> "Every decision records what the agent observed, what it chose, why, its
> confidence, which Gemini model made the call, and how long it took — plus the
> exact message that went out. This is the audit trail. Nothing the system does
> is unexplained."

Show: the observed-JSON block and the generated message body.

## 2:05–2:30 — The money loop

> "Collections is the wedge. Overdue invoices walk a three-tier ladder, tone
> adapted to payment history — a reliable payer three days late gets a different
> message than someone with four late cycles behind them. Chronic late payers
> get offered a payment plan automatically."

Show: the three `send_reminder_tier_*` decisions and one generated message.

> "One recovered invoice pays for the subscription several times over."

## 2:30–2:45 — Close

> "It's on Cloud Run, storing to Firestore, with Gemini making every judgement
> call. Five loops, running unattended. The owner reads one digest a day and
> gets her evenings back."

Show: `/healthz` returning live config, then the dashboard one last time.

---

## Recording checklist

- [ ] **`GEMINI_API_KEY` set before recording.** Without it the model column
      reads `fallback:none`, which visibly undercuts the entire claim.
- [ ] Reseed and run three ticks so escalations are present:
      `rm -f steward.db && python scripts/seed.py && for i in 1 2 3; do python scripts/tick.py; done`
- [ ] Record against the deployed Cloud Run URL, not localhost — the URL bar is
      part of the proof.
- [ ] Browser zoom ~125% so the log is legible when the video is compressed.
- [ ] Watch it back at 3:00 and confirm the three decisions land before 1:35.
