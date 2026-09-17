from agents.researcher import ResearcherState, researcher_agent
from kazenai import LoopDetected
import pytest


def test_infinite_loop() -> None:
    state = ResearcherState(agent_id="test-agent", run_id="loop-test")
    query = "research the recursive nature of recursion"
    with pytest.raises(LoopDetected):
        for _ in range(10):
            researcher_agent(state, query)
    assert state.loop_count == 3
