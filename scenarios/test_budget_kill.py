from agents.researcher import ResearcherState, researcher_agent
from kazenai import BudgetExceeded
import pytest


def test_budget_kill() -> None:
    state = ResearcherState(agent_id="test-agent", run_id="budget-kill", budget=0.01)
    query = "Summarize the following text: " + ("lorem ipsum " * 1000)
    with pytest.raises(BudgetExceeded):
        researcher_agent(state, query)
