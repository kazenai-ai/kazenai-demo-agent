#!/usr/bin/env python3
"""14 — One budget across OpenAI and Anthropic (plain SDK, no framework).

The pattern every multi-model workflow builds on:

    budget = SharedBudget(max_usd=0.01)
    planner = monitor(OpenAI(), budget=budget)
    writer  = monitor(Anthropic(), budget=budget)

Each `monitor(..., max_budget_usd=...)` client would have its *own* cap, so two
clients at $0.01 could spend $0.02. With one `SharedBudget`, every call on
either client is checked against the same $0.01 before it is sent, and the call
that would overspend raises `BudgetExceeded` without reaching the provider.

Runs offline by default; `--live` uses your real OpenAI and Anthropic keys.
"""

from __future__ import annotations

from _providers import (
    TICKETS,
    anthropic_clients,
    anthropic_model,
    local_only_env,
    openai_clients,
    openai_model,
    recorded_model_cost_usd,
    report,
)


def main() -> int:
    local_only_env()
    from kazenai import BudgetExceeded, SharedBudget, monitor

    openai_raw, _ = openai_clients()
    anthropic_raw, _ = anthropic_clients()

    # --- the KazenAI part -------------------------------------------------
    budget = SharedBudget(max_usd=0.01, name="ticket-workflow")
    # soft_pause_pct=100 turns off the early "trajectory" pause (see example 13)
    # so this example shows only the hard, pre-dispatch cap.
    planner = monitor(openai_raw, budget=budget, soft_pause_pct=100.0, workflow_id="ticket-reply", feature_id="plan")
    writer = monitor(anthropic_raw, budget=budget, soft_pause_pct=100.0, workflow_id="ticket-reply", feature_id="write")
    # ----------------------------------------------------------------------

    calls, denied_at = [], None
    for ticket, text in enumerate(TICKETS, start=1):
        try:
            plan = planner.chat.completions.create(
                model=openai_model(), max_tokens=300,
                messages=[{"role": "user", "content": f"List 3 steps to resolve this support ticket: {text}"}],
            )
            calls.append(("plan", openai_model(), plan.usage.prompt_tokens, plan.usage.completion_tokens))
            reply = writer.messages.create(
                model=anthropic_model(), max_tokens=300,
                messages=[{"role": "user", "content": f"Ticket: {text}\nPlan: {plan.choices[0].message.content}\nWrite a short reply to the customer."}],
            )
            calls.append(("write", anthropic_model(), reply.usage.input_tokens, reply.usage.output_tokens))
        except BudgetExceeded as exc:
            denied_at = {"ticket": ticket, "step": "plan" if len(calls) % 2 == 0 else "write", "reason": str(exc)}
            break

    expected = sum(
        recorded_model_cost_usd(
            m, input_tokens=i, output_tokens=o,
            client=openai_raw if step == "plan" else anthropic_raw,
        )
        for step, m, i, o in calls
    )
    return report({
        "ok": denied_at is not None and len(calls) >= 2 and budget.spent_usd <= budget.max_usd
        and abs(budget.spent_usd - expected) < 1e-9,
        "budget_usd": budget.max_usd,
        "spent_usd": round(budget.spent_usd, 6),
        "provider_calls": len(calls),
        "denied_before_dispatch": denied_at,
        "spent_equals_sum_of_call_prices": abs(budget.spent_usd - expected) < 1e-9,
        "takeaway": "Both providers drew from one wallet; the call that would overspend was refused before it was sent.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
