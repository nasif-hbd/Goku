"""CollectionAgent - recovers unpaid fees on a schedule nobody has to remember.

Small organizations lose real money here, not because owners do not know who
owes them, but because chasing payment is socially uncomfortable and always
loses to whatever is urgent. The agent escalates on a fixed ladder, and adapts
tone to payment history - a reliable payer who is three days late gets a
different message than someone with four late cycles behind them.
"""

from __future__ import annotations

from typing import Any

from ..config import settings
from ..gemini import get_client
from ..models import Decision
from ..notify import send
from .base import Agent, TickContext


class CollectionAgent(Agent):
    name = "collections"
    purpose = "Escalates overdue invoices with history-aware messaging and payment plans."

    def tick(self, ctx: TickContext) -> list[Decision]:
        ladder = ctx.vertical.fee_escalation_days
        invoices = ctx.query("invoices", status="unpaid")
        clients_by_id = {c["id"]: c for c in ctx.query("clients")}

        decisions: list[Decision] = []
        for invoice in invoices:
            client = clients_by_id.get(invoice["client_id"])
            if not client:
                continue

            overdue = max(0, (ctx.now - invoice["due_date"]).days)
            if overdue <= 0:
                continue

            tier = sum(1 for threshold in ladder if overdue >= threshold)
            already = invoice.get("reminders_sent", 0)

            if tier == 0:
                if not self._has_hold(ctx, invoice["id"]):
                    decisions.append(self._hold(ctx, invoice, client, overdue, ladder[0]))
                continue

            if tier <= already:
                continue  # this rung of the ladder has already been sent

            decisions.append(self._chase(ctx, invoice, client, overdue, tier, len(ladder)))

        return decisions

    # -- helpers ---------------------------------------------------------

    def _has_hold(self, ctx: TickContext, invoice_id: str) -> bool:
        prior = ctx.store.query(
            "decisions", org_id=ctx.org["id"], agent=self.name, entity_id=invoice_id
        )
        return any(d["decision"] == "hold_grace_period" for d in prior)

    def _payment_history(self, ctx: TickContext, client_id: str) -> dict[str, Any]:
        paid = ctx.store.query(
            "invoices", org_id=ctx.org["id"], client_id=client_id, status="paid"
        )
        late_cycles = 0
        for inv in paid:
            if inv.get("paid_at") and inv.get("due_date") and inv["paid_at"] > inv["due_date"]:
                late_cycles += 1
        return {
            "paid_invoices": len(paid),
            "late_cycles": late_cycles,
            "reliable": len(paid) >= 2 and late_cycles == 0,
        }

    # -- actions ---------------------------------------------------------

    def _hold(
        self,
        ctx: TickContext,
        invoice: dict[str, Any],
        client: dict[str, Any],
        overdue: int,
        first_rung: int,
    ) -> Decision:
        return self.record(
            ctx,
            entity_type="invoice",
            entity_id=invoice["id"],
            observed={"days_overdue": overdue, "client": client["name"]},
            decision="hold_grace_period",
            rationale=(
                f"{overdue}d overdue but the first reminder is not due until day "
                f"{first_rung}. Chasing sooner costs goodwill for no gain."
            ),
            action="none",
            confidence=0.85,
        )

    def _chase(
        self,
        ctx: TickContext,
        invoice: dict[str, Any],
        client: dict[str, Any],
        overdue: int,
        tier: int,
        max_tier: int,
    ) -> Decision:
        v = ctx.vertical
        history = self._payment_history(ctx, client["id"])
        final = tier >= max_tier

        result = get_client().decide(
            system=self.system_prompt(ctx),
            prompt=(
                f"Invoice {invoice['period']} for {client['name']} is {overdue} days "
                f"overdue. Amount: {invoice['amount']:.2f} {settings.currency}. "
                f"Recipient: {client['payer_name']} ({v.payer_label}). "
                f"Payment history: {history['paid_invoices']} invoices paid, "
                f"{history['late_cycles']} of them late. "
                f"This is reminder {tier} of {max_tier}"
                + (" - the final one before the owner steps in." if final else ".")
                + " Write the reminder. Keep it short and respectful; do not "
                "threaten. If the history shows repeated lateness, offer a "
                "payment plan and set offer_payment_plan true."
            ),
            schema_hint=(
                '{"subject": string, "body": string, "rationale": string, '
                '"offer_payment_plan": boolean}'
            ),
            fallback={
                "subject": f"Invoice {invoice['period']} - {invoice['amount']:.2f} {settings.currency}",
                "body": (
                    f"Hello {client['payer_name']}, the {invoice['period']} invoice for "
                    f"{client['name']} ({invoice['amount']:.2f} {settings.currency}) is "
                    f"{overdue} days past due. Could you settle it this week?"
                ),
                "rationale": f"reminder {tier} of {max_tier} at {overdue}d overdue",
                "offer_payment_plan": history["late_cycles"] >= 2,
            },
        )

        decision = self.record(
            ctx,
            entity_type="invoice",
            entity_id=invoice["id"],
            observed={
                "days_overdue": overdue,
                "amount": invoice["amount"],
                "tier": tier,
                "history": history,
            },
            decision=(
                f"send_reminder_tier_{tier}"
                + ("_with_payment_plan" if result.data.get("offer_payment_plan") else "")
            ),
            rationale=result.data.get("rationale", f"{overdue}d overdue"),
            action="send_message",
            confidence=0.9,
            model=result.model,
            latency_ms=result.latency_ms,
        )

        send(
            org_id=ctx.org["id"],
            to_name=client["payer_name"],
            to_address=client["payer_email"],
            subject=result.data.get("subject", "Outstanding invoice"),
            body=result.data.get("body", ""),
            decision_id=decision.id,
        )

        invoice["reminders_sent"] = tier
        ctx.store.put("invoices", invoice)

        if final:
            send(
                org_id=ctx.org["id"],
                to_name=ctx.org["owner_name"],
                to_address=ctx.org["owner_email"],
                subject=f"Final reminder sent: {client['name']} ({overdue}d overdue)",
                body=(
                    f"{client['payer_name']} has now had all {max_tier} reminders for "
                    f"invoice {invoice['period']} ({invoice['amount']:.2f} "
                    f"{settings.currency}). Automated chasing stops here."
                ),
                decision_id=decision.id,
            )

        return decision
