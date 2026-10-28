# kazenai-demo-agent

Small, runnable demos of KazenAI's hard spending limits: every model call is
checked against a limit before it runs, and an over-limit call never reaches the
provider. Plus copy-ready framework recipes (LangChain, LangGraph, CrewAI,
LiteLLM) you can lift into your own agent workflows.

Every example runs offline by default against a local fake provider, so you
need no API keys and spend nothing. Output is illustrative — not a bill and not
a savings claim.

This repository is self-contained: clone it, install from PyPI, and run.

Docs: [Control demo guide](https://docs.kazenai.com/guides/control-demo/) ·
Core: [kazenai](https://pypi.org/project/kazenai/) ·
FinOps: [kazenai-finops](https://pypi.org/project/kazenai-finops/) ·
Product: [kazenai.com](https://kazenai.com)

## 60-second path (no keys)

```bash
git clone https://github.com/kazenai-ai/kazenai-demo-agent.git
cd kazenai-demo-agent
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python examples/02_monitor_fake_provider.py
```

Expected: `BudgetExceeded` with `provider_calls: 0`.

## Install (PyPI)

Public package pins (reproducible demo):

- `kazenai==1.2.0`
- `kazen-event-schema==0.6.6`

Dependencies install from public PyPI. This demo does **not** ship offline vendor
wheels. Prefer bounded provider extras when installing the customer SDK elsewhere:

```bash
python -m pip install "kazenai-finops[openai]==1.2.0"
```

Report issues: [github.com/kazenai-ai/kazenai-demo-agent/issues](https://github.com/kazenai-ai/kazenai-demo-agent/issues)

Optional env:

```bash
export KAZENAI_DEMO_QUERY="research KazenAI budget enforcement"
export KAZENAI_DEMO_BUDGET_USD="0.25"
```

## Scenario tests (offline)

```bash
python -m pytest scenarios -q
```

Also:

```bash
python main.py
```

## SDK examples (ordered by user value)

| Script | What it shows | Runs |
|--------|----------------|------|
| `examples/02_monitor_fake_provider.py` | Tiny cap → **0** provider calls | offline |
| `examples/05_customer_feature_attribution.py` | Two customers, one feature, retry cost difference | offline, writes a local timeline |
| `examples/06_streaming_lifecycle.py` | Sync stream settle vs early-close pending | offline |
| `examples/07_concurrent_reservation.py` | Workers race local reservation authority | offline, several local workers |
| `examples/08_agent_runaway_then_deny.py` | Multi-step agent plans many calls; budget stops after one | offline |
| `examples/09_agent_fanout_budget_deny.py` | Parent fans out subagents; siblings denied while one holds | offline, several local workers |
| `examples/10_sequential_multi_agent_workflow.py` | Triage → research → reply; shared budget stops later stage | offline |
| `examples/11_fail_closed_vs_fail_open.py` | Fail-closed / fail-open / unknown-model block postures | offline |
| `examples/12_anthropic_messages_monitor.py` | Anthropic-shaped `messages.create` via `monitor()` | offline |
| `examples/13_soft_pause_vs_hard_budget_deny.py` | Soft `KazenCircuitBreaker` vs hard `BudgetExceeded` | offline |
| `examples/01_local_enforcement.py` | `Enforcement.check_local()` via researcher agent | offline |
| `examples/04_capture_metadata_default.py` | Metadata-default capture (bodies omitted) | offline |
| `examples/03_monitor_multisink_hosted.py` | HttpSink → your Agent FinOps | needs your Agent FinOps |

```bash
python examples/02_monitor_fake_provider.py
python examples/05_customer_feature_attribution.py
python examples/06_streaming_lifecycle.py
python examples/07_concurrent_reservation.py
python examples/08_agent_runaway_then_deny.py
python examples/09_agent_fanout_budget_deny.py
python examples/10_sequential_multi_agent_workflow.py
python examples/11_fail_closed_vs_fail_open.py
python examples/12_anthropic_messages_monitor.py
python examples/13_soft_pause_vs_hard_budget_deny.py
python examples/01_local_enforcement.py
python examples/04_capture_metadata_default.py

# Hosted Agent FinOps (your Agent FinOps URL and an API key; never commit credentials):
export KAZENAI_DEMO_HOSTED=1
export KAZENAI_FINOPS_URL=https://finops.example.com   # your Agent FinOps URL
export KAZENAI_FINOPS_API_KEY=...
export KAZENAI_TIER_MISMATCH_MULTIPLIER=2   # required under Control
export KAZENAI_ORG_ID=...
export KAZENAI_WORKSPACE_ID=...
python examples/03_monitor_multisink_hosted.py
```

All default paths are synthetic. Do not treat timeline or console output as customer
billing, invoice truth, or guaranteed savings.

## Framework recipes (examples 14–20)

These show how to put KazenAI around the frameworks you already use. Each one
runs **offline by default** (a local fake provider, no keys, no cost) and against
the real providers with `--live`.

```bash
python -m pip install -r requirements-frameworks.txt   # LangChain, LangGraph, OpenAI, Anthropic
python examples/16_langchain_multi_model_chain.py       # offline
python examples/16_langchain_multi_model_chain.py --live  # real calls (needs keys)
```

CrewAI pins its own dependencies, so give it a separate virtualenv:

```bash
python3.11 -m venv .venv-crew && source .venv-crew/bin/activate
python -m pip install -r requirements-crewai.txt
python examples/19_crewai_crew.py
```

| Script | Framework | Pattern you can copy |
|--------|-----------|----------------------|
| `examples/14_shared_budget_two_providers.py` | plain SDKs | One `SharedBudget` across an OpenAI and an Anthropic client |
| `examples/15_langchain_chat_models.py` | LangChain | `ChatOpenAI` / `ChatAnthropic` bound to monitored clients: `invoke`, `stream`, `ainvoke`, `with_structured_output` |
| `examples/16_langchain_multi_model_chain.py` | LangChain LCEL | A two-model chain (plan on OpenAI, reply on Anthropic) on one budget; declare the chain's Control boundary |
| `examples/17_langgraph_multi_provider_workflow.py` | LangGraph | plan → draft → review on three models / two providers; per-step spend; the step that would overspend is refused |
| `examples/18_langgraph_approval_checkpoint.py` | LangGraph | Human approval with `interrupt_before` + SQLite checkpoint; resume after a restart without re-charging finished steps |
| `examples/19_crewai_crew.py` | CrewAI | Two-agent crew on two providers, one budget, via `bind_crew_llm_client` + `wrap_crew(guarded_clients=[...])` |
| `examples/20_litellm_proxy.py` | LiteLLM proxy | `monitor()` around an OpenAI client pointed at the proxy; priced per requested model |

The three lines that matter in every recipe:

```python
from kazenai import SharedBudget, BudgetExceeded
from kazenai.integrations.langchain import bind_monitored_chat_openai

budget = SharedBudget(max_usd=0.50, name="support-workflow")      # one budget for the workflow
bind_monitored_chat_openai(llm, OpenAI(max_retries=0), async_client=AsyncOpenAI(max_retries=0),
                           budget=budget, workflow_id="support", feature_id="reply")
# ... run your chain / graph / crew; the call that would overspend raises BudgetExceeded
# before it reaches the provider.
```

`SharedBudget` is in-process. To share one budget across processes, hosts or
restarts, use Agent FinOps and set a `workflow_id` (or customer / feature) limit
there; the binding code stays the same.

### Running with `--live`

`--live` (or `KAZENAI_DEMO_LIVE=1`) uses `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`
from your environment. Each recipe uses a budget of a few cents or less, and the
point of every recipe is that the budget stops it. Use keys with a low spend cap.
Models default to `gpt-4o-mini` and `claude-haiku-4-5`; override them with
`KAZENAI_DEMO_OPENAI_MODEL` and `KAZENAI_DEMO_ANTHROPIC_MODEL` (the model must be
in KazenAI's price table; unpriced models are refused). Example 20 also needs a
running LiteLLM proxy: `KAZENAI_DEMO_LITELLM_URL` and `KAZENAI_DEMO_LITELLM_KEY`.

### Tips that save you a debugging session

- **Bind every model.** A graph or chain declares every guarded client its steps
  use (`declare_langgraph_control_boundary(graph, *clients)`); `wrap_graph` refuses
  to run a Control graph with a missing or unrelated client.
- **Turn off framework retries for refusals** (for LangChain models,
  `max_retries=0`). Otherwise the framework retries the refused call and
  KazenAI's loop guard trips instead of a clear `BudgetExceeded`.
- **Turn off proxy retries/fallbacks** (`num_retries: 0` in LiteLLM) so one app
  call is one provider attempt.
- The recipes set `soft_pause_pct=100.0` so the demo reaches the hard budget
  stop; in production, leave the default to get an early soft pause.

## Supported / unsupported boundaries

| Path | Status |
|------|--------|
| OpenAI Chat Completions sync/async, streaming and not, incl. `.parse()` structured output | Supported, live-verified |
| Anthropic Messages sync/async, streaming and not | Supported, live-verified |
| LangChain `ChatOpenAI` / `ChatAnthropic` (bound), LangGraph graphs | Supported, live-verified |
| LiteLLM proxy (application-owned or gateway-owned accounting) | Supported, live-verified |
| OpenAI Responses (`create`, `parse`, `stream`) | Supported from 1.2.0, live-verified |
| CrewAI 1.15.26 native LLMs (`kickoff`, `akickoff`, `kickoff_async`) | Supported, live-verified (example 19); memory, knowledge, `Crew(stream=True)` and `llm_overlay` are refused under Control |
| OpenAI Realtime, Anthropic `beta.messages`, Bedrock / Vertex wrappers, AutoGen | Unsupported (refused under Control, or not intercepted) |

Provider SDK ranges: `openai>=1.40,<3`, `anthropic>=0.39,<1`. Framework pins are in
`requirements-frameworks.txt` and `requirements-crewai.txt`.
