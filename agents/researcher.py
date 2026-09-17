from typing import Any

from kazenai import BudgetExceeded, Enforcement, LoopDetected
from pydantic import BaseModel, Field

from tools.search_tool import search_tool


_USD_PER_TOKEN = 0.00002
_LOOP_LIMIT = 3


class ResearcherState(BaseModel):
    agent_id: str
    run_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    budget: float = 1.0  # default budget
    tokens_used: int = 0
    cost_usd: float = 0.0
    loop_count: int = 0


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def researcher_agent(state: ResearcherState, query: str) -> str:
    """
    ReAct-style demo agent with local KazenAI budget and loop enforcement.
    """
    projected_tokens = _estimate_tokens(query)
    projected_cost = projected_tokens * _USD_PER_TOKEN
    Enforcement(max_cost_usd=state.budget).check_local(
        projected_cost_usd=state.cost_usd + projected_cost
    )

    plan = f"Search for: {query}"
    state.history.append({"plan": plan})

    tool_result = search_tool(query)
    state.history.append({"tool_result": tool_result})
    state.tokens_used += projected_tokens
    state.cost_usd += projected_cost

    if tool_result.get("triggered_loop"):
        state.loop_count += 1
        if state.loop_count >= _LOOP_LIMIT:
            raise LoopDetected(
                f"repeated recursive search detected after {state.loop_count} turns"
            )

    review = f"Tool returned: {tool_result['result']}"
    state.history.append({"review": review})
    state.metadata["budget_remaining_usd"] = round(max(0.0, state.budget - state.cost_usd), 6)
    return review
