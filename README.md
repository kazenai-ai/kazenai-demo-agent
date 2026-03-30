# kazenai-demo-agent

> **Watch KazenAI catch a runaway AI agent in real time.**

[![KazenAI](https://img.shields.io/badge/powered%20by-KazenAI-534AB7)](https://kazenai.com)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

This repo contains three demo agents that show exactly what KazenAI catches — and what happens without it.

---

## The demos

### Demo 1: `loop_agent.py` — The $47K Scenario

An agent given an ambiguous task that causes it to call the same search tool repeatedly, rephrasing the query slightly each time. Without KazenAI: it runs until you kill it. With KazenAI: blocked at step 9.

```bash
python demos/loop_agent.py --mode without-kazenai  # watch it spiral
python demos/loop_agent.py --mode with-kazenai     # watch it get caught
```

**Terminal output with KazenAI:**
```
[KazenAI] step=1  gpt-4o-mini  cost=$0.0043  total=$0.0043  proj=$0.21/$5.00  OK
[KazenAI] step=2  gpt-4o-mini  cost=$0.0041  total=$0.0084  proj=$0.19/$5.00  OK
[KazenAI] step=5  gpt-4o-mini  cost=$0.0039  total=$0.021   proj=$0.19/$5.00  WARN:loop_h1:0.88
[KazenAI] step=6  gpt-4o-mini  cost=$0.0040  total=$0.025   BLOCKED:loop  h1_score=0.91
```

### Demo 2: `budget_agent.py` — Pre-flight Budget Enforcement

Shows the difference between a tool that records spend after the fact vs KazenAI blocking before the call is made.

```bash
python demos/budget_agent.py
```

### Demo 3: `multi_agent.py` — Parent-Child Cost Attribution

An orchestrator agent spawning two sub-agents. KazenAI tracks cost across the full call tree with `parent_step_id` linking each sub-agent call back to the originating orchestrator step.

```bash
python demos/multi_agent.py
```

---

## Setup

```bash
git clone https://github.com/kazenai/kazenai-demo-agent
cd kazenai-demo-agent
pip install -r requirements.txt

# Set your OpenAI key (demos use gpt-4o-mini, very cheap)
export OPENAI_API_KEY="sk-..."

# Optional: KazenAI API key for backend dashboard
# Get one free at kazenai.com
export KAZENAI_API_KEY="kz_..."
```

---

## What you'll see

```
Without KazenAI:
  Step 1...  Step 2...  Step 3...  Step 4... [still running] Step 20...
  [3 hours later] $47.00 billed. Agent still running.

With KazenAI (debug=True):
  [KazenAI] step=1  gpt-4o-mini  cost=$0.0043  total=$0.0043  OK
  [KazenAI] step=5  gpt-4o-mini  WARN:loop_h1:0.88
  [KazenAI] step=6  gpt-4o-mini  BLOCKED:loop
  Total spent: $0.021. Loop caught before it became expensive.
```

---

## The one-liner that does this

```python
from kazenai import monitor

agent = monitor(
    your_agent,
    agent_id="demo-agent",
    api_key="kz_...",
    max_budget_usd=0.10,
    debug=True,
)
```

Three parameters. Your existing agent code unchanged.

---

## Star ⭐ kazenai-core

If this demo shows you something useful, the main SDK is at **[github.com/kazenai/kazenai-core](https://github.com/kazenai/kazenai-core)**. Star it there — that's where the code lives.

---

## Roadmap for this repo

- [ ] Demo 4: Semantic drift — agent behaviour changes after model update
- [ ] Demo 5: Multi-provider — agent switching between GPT-4o and Claude mid-run
- [ ] Demo 6: CrewAI crew with budget enforcement across all agents

---

Built by [Dhavan Shah](dhavan-shah.github.io) · [kazenai.com](https://kazenai.com)
