#!/usr/bin/env python3
"""20 — LiteLLM proxy: budget every model behind the proxy from your app.

Application-owned accounting (this example): your app talks to the LiteLLM
proxy with the OpenAI SDK, wrapped by `monitor()`. KazenAI checks the budget
before each call and prices it by the model name you request, whichever
provider the proxy routes it to:

    client = monitor(OpenAI(base_url=LITELLM_URL, api_key=LITELLM_KEY), budget=budget)
    client.chat.completions.create(model="gpt-4o-mini", ...)        # routed to OpenAI
    client.chat.completions.create(model="claude-haiku-4-5", ...)   # routed to Anthropic

Keep the proxy's own retries and fallbacks off (`num_retries: 0`) so one app
call is one provider attempt.

Gateway-owned accounting is the alternative when apps can't be changed: load
`kazenai.integrations.litellm_gateway.proxy_handler_instance` as a LiteLLM
callback and set `KAZENAI_ENFORCEMENT_OWNER=gateway`
in the proxy; apps then send `metadata={"kazenai_operation_id": ...}` and must
not reserve again. Both modes are live-verified with Agent FinOps.

Offline by default (a fake proxy). `--live` needs a running proxy:
    KAZENAI_DEMO_LITELLM_URL=http://127.0.0.1:4000  KAZENAI_DEMO_LITELLM_KEY=sk-...
"""

from __future__ import annotations

import os

from _providers import (
    TICKETS,
    anthropic_model,
    live_mode,
    local_only_env,
    openai_clients,
    openai_model,
    recorded_model_cost_usd,
    report,
)


def main() -> int:
    local_only_env()
    from kazenai import BudgetExceeded, SharedBudget, monitor
    from kazenai.model_pricing import output_limit_param

    if live_mode():
        url, key = os.getenv("KAZENAI_DEMO_LITELLM_URL", ""), os.getenv("KAZENAI_DEMO_LITELLM_KEY", "")
        if not url:
            return report({"ok": True, "skipped": "set KAZENAI_DEMO_LITELLM_URL (and _KEY) to run against a proxy"})
        import openai

        proxy = openai.OpenAI(base_url=url, api_key=key, max_retries=0)
    else:
        proxy, _ = openai_clients()  # stands in for the proxy's OpenAI-compatible API

    # --- the KazenAI part -------------------------------------------------
    budget = SharedBudget(max_usd=0.006, name="via-litellm")
    client = monitor(proxy, budget=budget, soft_pause_pct=100.0, workflow_id="litellm-support")
    # ----------------------------------------------------------------------

    used, denied_at = [], None
    models = [openai_model(), anthropic_model()]
    for number, ticket in enumerate(TICKETS, start=1):
        model = models[(number - 1) % 2]
        try:
            kwargs = {"model": model, output_limit_param(model): 300,
                      "messages": [{"role": "user", "content": f"Reply briefly to: {ticket}"}]}
            if number % 3 == 0:  # streaming works the same way
                usage = None
                for chunk in client.chat.completions.create(stream=True, **kwargs):
                    usage = chunk.usage or usage  # KazenAI requests the final usage chunk
                used.append((model, usage.prompt_tokens, usage.completion_tokens))
            else:
                resp = client.chat.completions.create(**kwargs)
                used.append((model, resp.usage.prompt_tokens, resp.usage.completion_tokens))
        except BudgetExceeded as exc:
            denied_at = {"ticket": number, "model": model, "reason": str(exc)}
            break

    expected = sum(
        recorded_model_cost_usd(m, input_tokens=i, output_tokens=o, client=proxy)
        for m, i, o in used
    )
    return report({
        "ok": denied_at is not None and len(used) >= 2 and abs(budget.spent_usd - expected) < 1e-9,
        "calls": [{"model": m, "input_tokens": i, "output_tokens": o} for m, i, o in used],
        "denied_before_dispatch": denied_at,
        "spent_usd": round(budget.spent_usd, 6),
        "spent_equals_price_of_reported_usage": abs(budget.spent_usd - expected) < 1e-9,
        "takeaway": "One proxy client, models from two providers, one budget priced per model.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
