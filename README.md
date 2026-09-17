# kazenai-demo-agent

Runnable local demo for KazenAI budget and loop enforcement.

This package intentionally stays small: one deterministic researcher agent, one
local search tool, and two pytest scenarios that assert the enforcement behavior.
It does not call external LLMs or search APIs, so it is safe to run in CI.

## Setup

```bash
cd kazenai-demo-agent
pip install -r requirements.txt
```

For monorepo development without installing `kazenai-core`, run with:

```bash
PYTHONPATH=../kazenai-core:. python main.py
```

Optional environment variables:

```bash
export KAZENAI_DEMO_QUERY="research KazenAI budget enforcement"
export KAZENAI_DEMO_BUDGET_USD="0.25"
```

## Scenarios

```bash
PYTHONPATH=../kazenai-core:. pytest scenarios -q
```

The scenarios cover:

- `BudgetExceeded` before a high-token task can run past the configured budget.
- `LoopDetected` after repeated recursive search suggestions.

## Core API Used

```python
from kazenai import BudgetExceeded, Enforcement, LoopDetected
```

`researcher_agent` uses `Enforcement.check_local()` before tool work and raises
the same SDK exceptions production integrations catch.
