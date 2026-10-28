#!/usr/bin/env python3
"""15 — LangChain: put ChatOpenAI and ChatAnthropic under one KazenAI budget.

    budget = SharedBudget(max_usd=1.00)
    bind_monitored_chat_openai(chat_openai, OpenAI(), async_client=AsyncOpenAI(), budget=budget)
    bind_monitored_chat_anthropic(chat_claude, Anthropic(), async_client=AsyncAnthropic(), budget=budget)

After binding, use the models exactly as usual — `invoke`, `stream`,
`ainvoke`, `astream`, `with_structured_output` — and every provider call is
checked against the budget before it is sent and charged at the model's price
afterwards. `wrap_langchain_runnable(model, capability="control")` adds run
context and refuses to run if the model is not actually bound.

Requires: pip install -r requirements-frameworks.txt
Runs offline by default; `--live` uses your real keys.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

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


class Triage(BaseModel):
    category: str
    urgency: int


def _offline_reply(body):
    if body.get("response_format"):  # structured output request
        return '{"category": "billing", "urgency": 2}'
    return "(offline reply) " + str(body.get("messages", [{}])[-1].get("content", ""))[:60]


def main() -> int:
    local_only_env()
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    from kazenai import BudgetExceeded, SharedBudget
    from kazenai.integrations.langchain import (
        bind_monitored_chat_anthropic,
        bind_monitored_chat_openai,
        wrap_langchain_runnable,
    )
    oa_sync, oa_async = openai_clients(reply=_offline_reply)
    an_sync, an_async = anthropic_clients()

    # --- the KazenAI part -------------------------------------------------
    budget = SharedBudget(max_usd=1.00, name="langchain-demo")
    gpt = ChatOpenAI(model=openai_model(), max_tokens=300, stream_usage=True)
    bind_monitored_chat_openai(gpt, oa_sync, async_client=oa_async, budget=budget, soft_pause_pct=100.0,
                               workflow_id="support", feature_id="triage")
    claude = ChatAnthropic(model=anthropic_model(), max_tokens=300)
    bind_monitored_chat_anthropic(claude, an_sync, async_client=an_async, budget=budget, soft_pause_pct=100.0,
                                  workflow_id="support", feature_id="reply")
    gpt_run = wrap_langchain_runnable(gpt, capability="control")
    claude_run = wrap_langchain_runnable(claude, capability="control")
    # ----------------------------------------------------------------------

    used = []  # (model, input_tokens, output_tokens) as reported by LangChain

    def track(model, message):
        meta = message.usage_metadata
        used.append((model, meta["input_tokens"], meta["output_tokens"]))
        return message

    # 1. invoke
    track(openai_model(), gpt_run.invoke(f"In one sentence, what is this ticket about? {TICKETS[0]}"))
    # 2. stream
    streamed = None
    for chunk in claude_run.stream(f"Write a two-sentence reply to: {TICKETS[1]}"):
        streamed = chunk if streamed is None else streamed + chunk
    track(anthropic_model(), streamed)
    # 3. async
    track(anthropic_model(), asyncio.run(claude_run.ainvoke(f"Suggest a subject line for: {TICKETS[2]}")))
    # 4. structured output (OpenAI parse endpoint — guarded like create)
    structured = gpt.with_structured_output(Triage, include_raw=True).invoke(f"Triage this ticket: {TICKETS[3]}")
    track(openai_model(), structured["raw"])

    expected = sum(
        recorded_model_cost_usd(
            m, input_tokens=i, output_tokens=o,
            client=oa_sync if m == openai_model() else an_sync,
        )
        for m, i, o in used
    )

    # 5. a model bound to an exhausted budget never reaches the provider
    tiny = SharedBudget(max_usd=0.000001)
    blocked_calls: list = []
    blocked_sync, blocked_async = openai_clients(calls=blocked_calls)
    blocked = ChatOpenAI(model=openai_model(), max_tokens=300)
    bind_monitored_chat_openai(blocked, blocked_sync, async_client=blocked_async, budget=tiny)
    try:
        blocked.invoke("This call should never be sent.")
        denied = False
    except BudgetExceeded:
        denied = True

    return report({
        "ok": abs(budget.spent_usd - expected) < 1e-9 and denied and isinstance(structured["parsed"], Triage)
        and blocked_calls == [],
        "calls": [{"model": m, "input_tokens": i, "output_tokens": o} for m, i, o in used],
        "spent_usd": round(budget.spent_usd, 6),
        "spent_equals_price_of_reported_usage": abs(budget.spent_usd - expected) < 1e-9,
        "structured_output": structured["parsed"].model_dump() if structured["parsed"] else None,
        "exhausted_budget_denied_before_dispatch": denied and blocked_calls == [],
        "takeaway": "Bind once; invoke/stream/async/structured output are all budgeted and priced exactly.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
