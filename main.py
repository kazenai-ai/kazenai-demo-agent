import os
from dotenv import load_dotenv
from kazenai import BudgetExceeded, LoopDetected
from agents.researcher import ResearcherState, researcher_agent

load_dotenv()

def main():
    agent_id = os.getenv('AGENT_ID', 'demo-researcher')
    run_id = os.getenv("RUN_ID", "run-001")
    budget = float(os.getenv("KAZENAI_DEMO_BUDGET_USD", "0.25"))
    state = ResearcherState(agent_id=agent_id, run_id=run_id, budget=budget)
    query = os.getenv("KAZENAI_DEMO_QUERY", "research KazenAI budget enforcement")
    try:
        result = researcher_agent(state, query)
    except (BudgetExceeded, LoopDetected) as exc:
        print("Agent blocked:", exc)
    else:
        print("Agent Output:", result)
    print("Agent State:", state.model_dump())

if __name__ == "__main__":
    main()
