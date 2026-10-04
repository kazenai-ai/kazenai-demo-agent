# kazenai-demo-agent

Small, runnable demos for KazenAI **Control** budget and loop enforcement.

**Label honesty:** Hermetic examples use a fake provider. Hosted MultiSink is personal
HOSTED_DEMO only — not company staging certification, not production savings.

This repository is self-contained. Clone it alone, install from PyPI, and run the
hermetic path below. No sibling KazenAI checkout is required.

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

- `kazenai==1.1.1`
- `kazen-event-schema==0.6.3`

Dependencies install from public PyPI. This demo does **not** ship offline vendor
wheels. Prefer bounded provider extras when installing the customer SDK elsewhere:

```bash
python -m pip install "kazenai-finops[openai]==1.1.1"
```

Report issues: [github.com/kazenai-ai/kazenai-demo-agent/issues](https://github.com/kazenai-ai/kazenai-demo-agent/issues)

Optional env:

```bash
export KAZENAI_DEMO_QUERY="research KazenAI budget enforcement"
export KAZENAI_DEMO_BUDGET_USD="0.25"
```

## Hermetic scenarios (CI)

```bash
python -m pytest scenarios -q
```

Also:

```bash
python main.py
```

## SDK examples (ordered by user value)

| Script | What it shows | Evidence tier |
|--------|----------------|---------------|
| `examples/02_monitor_fake_provider.py` | Tiny cap → **0** provider calls | hermetic fake |
| `examples/05_customer_feature_attribution.py` | Two customers, one feature, retry cost difference | hermetic fake + local timeline |
| `examples/06_streaming_lifecycle.py` | Sync stream settle vs early-close pending | hermetic fake stream |
| `examples/07_concurrent_reservation.py` | Workers race local reservation authority | local process fixture |
| `examples/08_agent_runaway_then_deny.py` | Multi-step agent plans many calls; budget stops after one | hermetic fake |
| `examples/09_agent_fanout_budget_deny.py` | Parent fans out subagents; siblings denied while one holds | local process fixture |
| `examples/10_sequential_multi_agent_workflow.py` | Triage → research → reply; shared budget stops later stage | hermetic fake |
| `examples/11_fail_closed_vs_fail_open.py` | Fail-closed / fail-open / unknown-model block postures | hermetic config |
| `examples/12_anthropic_messages_monitor.py` | Anthropic-shaped `messages.create` via `monitor()` | hermetic fake |
| `examples/13_soft_pause_vs_hard_budget_deny.py` | Soft `KazenCircuitBreaker` vs hard `BudgetExceeded` | hermetic fake |
| `examples/01_local_enforcement.py` | `Enforcement.check_local()` via researcher agent | hermetic |
| `examples/04_capture_metadata_default.py` | Metadata-default capture (bodies omitted) | hermetic |
| `examples/03_monitor_multisink_hosted.py` | HttpSink → staging FinOps | hosted opt-in only |

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

# Hosted only (after staging URLs + API key; never commit credentials):
export KAZENAI_DEMO_HOSTED=1
export KAZENAI_FINOPS_URL=https://finops.staging.kazenai.com
export KAZENAI_FINOPS_API_KEY=...
export KAZENAI_ORG_ID=...
export KAZENAI_WORKSPACE_ID=...
python examples/03_monitor_multisink_hosted.py
```

All default paths are synthetic. Do not treat timeline or console output as customer
billing, invoice truth, or guaranteed savings.

## Supported / unsupported boundaries

| Path | Status |
|------|--------|
| Sync OpenAI `chat.completions.create` (non-streaming) via `monitor()` | Supported |
| Sync OpenAI `stream=True` / `.stream()` helper | Supported (see example 06) |
| Sync Anthropic Messages non-streaming + streaming | Supported in Core/FinOps; not required for this demo's default path |
| Async clients / OpenAI Responses / Realtime / Bedrock / Vertex | Unsupported |

Certified provider SDK ranges: `openai>=1.40,<2`, `anthropic>=0.39,<1`.
