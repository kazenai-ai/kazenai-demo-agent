#!/usr/bin/env python3
"""17 — LangGraph: a plan → draft → review workflow across OpenAI and Anthropic.

Each node uses a different chat model, bound to its own monitored client, and
all clients share one `SharedBudget`. The graph declares every client its nodes
use, and `wrap_graph(..., guarded_clients=[...])` refuses to run if any of them
is missing or unrelated:

    declare_langgraph_control_boundary(graph, planner_client, writer_client, reviewer_client)
    app = wrap_graph(graph, capability="control", guarded_clients=[...])

Tickets run through the graph until the next step can't fit in the budget. That
step — wherever it is in the graph — is refused before reaching the provider,
and the run stops with `BudgetExceeded`. Spend is reported per step.

Requires: pip install -r requirements-frameworks.txt
Runs offline by default; `--live` uses your real keys.
"""

from __future__ import annotations

from typing import TypedDict

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


class Ticket(TypedDict, total=False):
    ticket: str
    plan: str
    draft: str
    review: str


def main() -> int:
    local_only_env()
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, StateGraph

    from kazenai import BudgetExceeded, SharedBudget
    from kazenai.integrations.langchain import (
        bind_monitored_chat_anthropic,
        bind_monitored_chat_openai,
        bound_guarded_client,
    )
    from kazenai.integrations.langgraph import declare_langgraph_control_boundary, wrap_graph
    # --- the KazenAI part: bind each step's model to one shared budget ----
    budget = SharedBudget(max_usd=0.008, name="ticket-graph")
    common = dict(budget=budget, soft_pause_pct=100.0, workflow_id="ticket-graph")

    oa_sync, oa_async = openai_clients()
    an_sync, an_async = anthropic_clients()

    planner = ChatOpenAI(model=openai_model(), max_tokens=300)
    bind_monitored_chat_openai(planner, oa_sync, async_client=oa_async, feature_id="plan", **common)
    writer = ChatAnthropic(model=anthropic_model(), max_tokens=300)
    bind_monitored_chat_anthropic(writer, an_sync, async_client=an_async, feature_id="draft", **common)
    reviewer = ChatOpenAI(model=openai_model(), max_tokens=300)
    rv_sync, rv_async = openai_clients()
    bind_monitored_chat_openai(reviewer, rv_sync, async_client=rv_async, feature_id="review", **common)
    # ----------------------------------------------------------------------

    spend_by_step: dict = {"plan": 0.0, "draft": 0.0, "review": 0.0}

    def charge(step: str, model: str, message) -> str:
        meta = message.usage_metadata
        spend_by_step[step] += recorded_model_cost_usd(
            model, input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
            client=oa_sync if model == openai_model() else an_sync,
        )
        return str(message.content)

    def plan(state: Ticket) -> Ticket:
        msg = planner.invoke(f"List 3 short steps to resolve: {state['ticket']}")
        return {"plan": charge("plan", openai_model(), msg)}

    def draft(state: Ticket) -> Ticket:
        msg = writer.invoke(f"Ticket: {state['ticket']}\nPlan: {state['plan']}\nWrite a short reply.")
        return {"draft": charge("draft", anthropic_model(), msg)}

    def review(state: Ticket) -> Ticket:
        msg = reviewer.invoke(f"Check this reply for tone and accuracy, in one line:\n{state['draft']}")
        return {"review": charge("review", openai_model(), msg)}

    builder = StateGraph(Ticket)
    builder.add_node("plan", plan)
    builder.add_node("draft", draft)
    builder.add_node("review", review)
    builder.set_entry_point("plan")
    builder.add_edge("plan", "draft")
    builder.add_edge("draft", "review")
    builder.add_edge("review", END)
    graph = builder.compile()

    # --- declare every provider client the graph's nodes use -------------
    clients = [bound_guarded_client(planner), bound_guarded_client(writer), bound_guarded_client(reviewer)]
    declare_langgraph_control_boundary(graph, *clients)
    app = wrap_graph(graph, capability="control", guarded_clients=clients)
    # ----------------------------------------------------------------------

    completed, denied_at = 0, None
    for number, ticket in enumerate(TICKETS, start=1):
        before = dict(spend_by_step)
        try:
            app.invoke({"ticket": ticket})
            completed += 1
        except BudgetExceeded as exc:
            ran = [s for s in ("plan", "draft", "review") if spend_by_step[s] > before[s]]
            denied_step = ("plan", "draft", "review")[len(ran)]
            denied_at = {"ticket": number, "step": denied_step, "reason": str(exc)}
            break

    total = sum(spend_by_step.values())
    return report({
        "ok": completed >= 1 and denied_at is not None and abs(budget.spent_usd - total) < 1e-9
        and budget.spent_usd <= budget.max_usd,
        "budget_usd": budget.max_usd,
        "tickets_completed": completed,
        "denied_before_dispatch": denied_at,
        "spent_usd": round(budget.spent_usd, 6),
        "spent_by_step_usd": {k: round(v, 6) for k, v in spend_by_step.items()},
        "takeaway": "Every step of the graph, on either provider, draws from one budget; the step that "
                    "would overspend is refused wherever it falls in the graph.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
