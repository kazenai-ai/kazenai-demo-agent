#!/usr/bin/env python3
"""16 — LangChain LCEL chain that mixes OpenAI and Anthropic under one budget.

    plan  = prompt | ChatOpenAI     (cheap model drafts a plan)
    reply = prompt | ChatAnthropic  (stronger model writes the reply)
    chain = {"plan": plan, "ticket": passthrough} | reply

Both chat models are bound to monitored clients that share one `SharedBudget`.
The composed chain declares both clients as its Control boundary, so
`wrap_langchain_runnable(..., guarded_clients=[...])` can verify that every
provider the chain uses is guarded:

    declare_langchain_control_boundary(chain, gpt_client, claude_client)
    wrap_langchain_runnable(chain, capability="control", guarded_clients=[gpt_client, claude_client])

The chain runs ticket after ticket until the budget can't cover the next step,
which is refused before it reaches the provider.

Requires: pip install -r requirements-frameworks.txt
Runs offline by default; `--live` uses your real keys.
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
    from langchain_anthropic import ChatAnthropic
    from langchain_core.callbacks import get_usage_metadata_callback
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_openai import ChatOpenAI

    from kazenai import BudgetExceeded, SharedBudget
    from kazenai.integrations.langchain import (
        bind_monitored_chat_anthropic,
        bind_monitored_chat_openai,
        bound_guarded_client,
        declare_langchain_control_boundary,
        wrap_langchain_runnable,
    )
    oa_sync, oa_async = openai_clients()
    an_sync, an_async = anthropic_clients()

    # --- the KazenAI part -------------------------------------------------
    budget = SharedBudget(max_usd=0.006, name="support-chain")
    gpt = ChatOpenAI(model=openai_model(), max_tokens=300)
    bind_monitored_chat_openai(gpt, oa_sync, async_client=oa_async, budget=budget, soft_pause_pct=100.0,
                               workflow_id="support-chain", feature_id="plan")
    claude = ChatAnthropic(model=anthropic_model(), max_tokens=300)
    bind_monitored_chat_anthropic(claude, an_sync, async_client=an_async, budget=budget, soft_pause_pct=100.0,
                                  workflow_id="support-chain", feature_id="reply")
    # ----------------------------------------------------------------------

    plan = ChatPromptTemplate.from_template("List 3 short steps to resolve: {ticket}") | gpt | StrOutputParser()
    reply = ChatPromptTemplate.from_template(
        "Ticket: {ticket}\nPlan: {plan}\nWrite a short, friendly reply to the customer."
    ) | claude | StrOutputParser()
    chain = {"plan": plan, "ticket": RunnablePassthrough()} | reply

    # --- declare every provider client the chain uses ---------------------
    clients = [bound_guarded_client(gpt), bound_guarded_client(claude)]
    declare_langchain_control_boundary(chain, *clients)
    support_chain = wrap_langchain_runnable(chain, capability="control", guarded_clients=clients)
    # ----------------------------------------------------------------------

    replies, denied_at = 0, None
    with get_usage_metadata_callback() as usage:  # LangChain's own per-model token counts
        for number, ticket in enumerate(TICKETS, start=1):
            try:
                support_chain.invoke(ticket)
                replies += 1
            except BudgetExceeded as exc:
                denied_at = {"ticket": number, "reason": str(exc)}
                break

    per_model = {}
    for model_name, meta in usage.usage_metadata.items():
        model = openai_model() if model_name.startswith(openai_model()) else anthropic_model()
        per_model[model_name] = round(
            recorded_model_cost_usd(
                model, input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
                client=oa_sync if model == openai_model() else an_sync,
            ),
            6,
        )
    expected = sum(per_model.values())

    return report({
        "ok": replies >= 1 and denied_at is not None and abs(budget.spent_usd - expected) < 1e-5
        and budget.spent_usd <= budget.max_usd,
        "budget_usd": budget.max_usd,
        "tickets_answered": replies,
        "denied_before_dispatch": denied_at,
        "spent_usd": round(budget.spent_usd, 6),
        "spent_by_model_usd": per_model,
        "takeaway": "One chain, two providers, one budget: the step that would overspend never reached a provider.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
