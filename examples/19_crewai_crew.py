#!/usr/bin/env python3
"""19 — CrewAI: a two-agent crew (OpenAI researcher, Anthropic writer) on one budget.

    budget = SharedBudget(max_usd=0.02)
    bind_crew_llm_client(researcher, OpenAI(), budget=budget)     # OpenAI model
    bind_crew_llm_client(writer, Anthropic(), budget=budget)      # Anthropic model

    crew = wrap_crew(crew, capability="control", guarded_clients=[oa, an])
    crew.kickoff()   # or: await crew.akickoff() / await crew.kickoff_async()

`bind_crew_llm_client` swaps monitored clients into each agent's CrewAI LLM
(sync and async, one budget), so every LLM call the crew makes is checked
against the budget before it is sent. Pass an OpenAI client for an OpenAI model
and an Anthropic client for an Anthropic model. Under Control, `wrap_crew`
refuses a crew with any LLM that is not bound (agent, manager, planning),
memory/knowledge, `Crew(stream=True)` or `llm_overlay`.

A budget denial stops the crew: it is raised as `BudgetExceeded` that is also
CrewAI's `HookAborted`, so CrewAI does not retry the task.

Status: certified for CrewAI 1.15.26 (live-verified with OpenAI and Anthropic).

Requires: pip install -r requirements-crewai.txt
Runs offline by default; `--live` uses your real keys.
"""

from __future__ import annotations

from _providers import (
    OFFLINE_ANTHROPIC_BASE_URL,
    OFFLINE_OPENAI_BASE_URL,
    TICKETS,
    anthropic_clients,
    anthropic_model,
    live_mode,
    local_only_env,
    openai_clients,
    openai_model,
    report,
)


def _crew_reply(body):
    # CrewAI agents finish when the model answers in this format.
    return "Thought: I now can give a great answer\nFinal Answer: (offline) " + str(
        body.get("messages", [{}])[-1].get("content", "")
    )[:80]


def _build_crew(budget, calls):
    from crewai import LLM, Agent, Crew, Task

    from kazenai.integrations.crewai import bind_crew_llm_client, wrap_crew

    offline = {} if live_mode() else {"base_url": OFFLINE_OPENAI_BASE_URL}
    researcher = Agent(
        role="Support researcher", goal="Find the cause of the customer's issue", backstory="Tier-2 support.",
        llm=LLM(model=openai_model(), max_tokens=300, **offline),
        allow_delegation=False, max_iter=1,
    )
    offline = {} if live_mode() else {"base_url": OFFLINE_ANTHROPIC_BASE_URL}
    writer = Agent(
        role="Support writer", goal="Write a clear, kind reply", backstory="Customer-facing writer.",
        llm=LLM(model=f"anthropic/{anthropic_model()}", max_tokens=300, **offline),
        allow_delegation=False, max_iter=1,
    )

    # --- the KazenAI part -------------------------------------------------
    oa_sync, _ = openai_clients(reply=_crew_reply, calls=calls)
    an_sync, _ = anthropic_clients(reply=_crew_reply, calls=calls)
    oa = bind_crew_llm_client(researcher, oa_sync, budget=budget, soft_pause_pct=100.0,
                              workflow_id="crew-support", feature_id="research")
    an = bind_crew_llm_client(writer, an_sync, budget=budget, soft_pause_pct=100.0,
                              workflow_id="crew-support", feature_id="write")
    # ----------------------------------------------------------------------

    research = Task(description=f"Investigate: {TICKETS[0]}", expected_output="Likely cause", agent=researcher)
    reply = Task(description="Write the customer reply from the research.", expected_output="A reply", agent=writer)
    crew = Crew(agents=[researcher, writer], tasks=[research, reply])
    # Control: every LLM the crew can call must be one of these guarded clients.
    return wrap_crew(crew, capability="control", guarded_clients=[oa, an])


def main() -> int:
    local_only_env()
    from kazenai import BudgetExceeded, SharedBudget

    budget = SharedBudget(max_usd=0.02, name="crew-support")
    calls: list = []
    result = _build_crew(budget, calls).kickoff()
    calls_after_first = len(calls)
    spent_after_first = budget.spent_usd

    # A crew whose budget is already used up never reaches the provider.
    exhausted = SharedBudget(max_usd=0.000001)
    blocked_calls: list = []
    try:
        _build_crew(exhausted, blocked_calls).kickoff()
        denied = False
    except BudgetExceeded:
        denied = True

    offline_calls_ok = live_mode() or calls_after_first == 2  # the live API is not counted locally
    return report({
        "ok": offline_calls_ok and spent_after_first > 0 and bool(str(result).strip()) and denied
        and blocked_calls == [],
        "status": "CrewAI 1.15.26 certified (kickoff, akickoff, kickoff_async)",
        "crew_result": str(result)[:120],
        "provider_calls": calls_after_first if not live_mode() else "not counted in --live mode",
        "spent_usd": round(spent_after_first, 6),
        "exhausted_budget_denied_before_dispatch": denied and blocked_calls == [],
        "takeaway": "Both agents' LLMs, on two providers, drew from one budget; an exhausted budget "
                    "stopped the crew before any provider call.",
    })


if __name__ == "__main__":
    raise SystemExit(main())
