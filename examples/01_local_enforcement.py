#!/usr/bin/env python3
"""01 — Local Enforcement only (no network, no monitor).

Hermetic demo of BudgetExceeded / LoopDetected using check_local().
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.researcher import ResearcherState, researcher_agent
from kazenai import BudgetExceeded, LoopDetected


def main() -> int:
    budget = float(os.getenv("KAZENAI_DEMO_BUDGET_USD", "0.01"))
    query = os.getenv(
        "KAZENAI_DEMO_QUERY",
        "Summarize the following text: " + ("lorem ipsum " * 1000),
    )
    state = ResearcherState(agent_id="demo-researcher", run_id="ex01-local", budget=budget)
    try:
        result = researcher_agent(state, query)
    except (BudgetExceeded, LoopDetected) as exc:
        print(f"blocked:{type(exc).__name__}:{exc}")
        print(f"state:{state.model_dump()}")
        return 0
    print(f"ok:{result}")
    print(f"state:{state.model_dump()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
