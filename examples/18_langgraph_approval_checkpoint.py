#!/usr/bin/env python3
"""18 — LangGraph: pause for human approval, resume later, pay for each step once.

A draft step (Anthropic) writes a reply, the graph pauses before `send`
(`interrupt_before=["send"]`) and checkpoints to SQLite. Later — here with a
freshly built graph, as after a restart — it resumes from the checkpoint and
runs only `send` (OpenAI). KazenAI keeps one budget across both halves, and the
resumed run does not re-run or re-charge the step that already finished.

The same `SharedBudget` instance only lives in one process; across real
restarts, use Agent FinOps with a `workflow_id` workflow limit.

Requires: pip install -r requirements-frameworks.txt
Runs offline by default; `--live` uses your real keys.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TypedDict

from _providers import TICKETS, anthropic_clients, anthropic_model, local_only_env, openai_clients, openai_model, report


class Reply(TypedDict, total=False):
    ticket: str
    draft: str
    crm_note: str


def main() -> int:
    local_only_env()
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, StateGraph

    from kazenai import SharedBudget
    from kazenai.integrations.langchain import (
        bind_monitored_chat_anthropic,
        bind_monitored_chat_openai,
        bound_guarded_client,
    )
    from kazenai.integrations.langgraph import declare_langgraph_control_boundary, wrap_graph

    budget = SharedBudget(max_usd=0.05, name="approval-flow")
    provider_calls: list = []  # filled by the offline transport only
    steps_run: list = []       # model-calling steps actually executed (offline and live)

    def build_app(saver):
        """Build the graph (called twice: before the pause and after the 'restart')."""
        oa_sync, oa_async = openai_clients(calls=provider_calls)
        an_sync, an_async = anthropic_clients(calls=provider_calls)
        writer = ChatAnthropic(model=anthropic_model(), max_tokens=300)
        bind_monitored_chat_anthropic(writer, an_sync, async_client=an_async, budget=budget,
                                      soft_pause_pct=100.0, workflow_id="approval-flow", feature_id="draft")
        logger = ChatOpenAI(model=openai_model(), max_tokens=200)
        bind_monitored_chat_openai(logger, oa_sync, async_client=oa_async, budget=budget,
                                   soft_pause_pct=100.0, workflow_id="approval-flow", feature_id="send")

        def draft(state: Reply) -> Reply:
            steps_run.append("draft")
            return {"draft": str(writer.invoke(f"Write a short reply to: {state['ticket']}").content)}

        def send(state: Reply) -> Reply:
            steps_run.append("send")
            note = logger.invoke(f"Summarize this sent reply as a one-line CRM note:\n{state['draft']}")
            return {"crm_note": str(note.content)}

        builder = StateGraph(Reply)
        builder.add_node("draft", draft)
        builder.add_node("send", send)
        builder.set_entry_point("draft")
        builder.add_edge("draft", "send")
        builder.add_edge("send", END)
        graph = builder.compile(checkpointer=saver, interrupt_before=["send"])

        clients = [bound_guarded_client(writer), bound_guarded_client(logger)]
        declare_langgraph_control_boundary(graph, *clients)
        return wrap_graph(graph, capability="control", guarded_clients=clients)

    config = {"configurable": {"thread_id": "ticket-42"}}
    db = str(Path(tempfile.mkdtemp(prefix="kazenai-demo-")) / "checkpoints.sqlite")

    with SqliteSaver.from_conn_string(db) as saver:
        paused = build_app(saver).invoke({"ticket": TICKETS[0]}, config=config)
    calls_before_approval = len(steps_run)
    spent_before_approval = budget.spent_usd

    # ... a human reviews paused["draft"] and approves ...

    with SqliteSaver.from_conn_string(db) as saver:  # fresh graph, same checkpoint
        done = build_app(saver).invoke(None, config=config)

    return report({
        "ok": calls_before_approval == 1 and steps_run == ["draft", "send"] and bool(done.get("crm_note"))
        and budget.spent_usd > spent_before_approval,
        "paused_before": "send",
        "draft_ready_for_review": bool(paused.get("draft")),
        "provider_calls_before_approval": calls_before_approval,
        "provider_calls_total": len(steps_run),
        "spent_before_approval_usd": round(spent_before_approval, 6),
        "spent_total_usd": round(budget.spent_usd, 6),
        "takeaway": "Resuming from the checkpoint ran only the remaining step; the draft was not re-run or re-charged.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
