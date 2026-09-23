# kazenai-demo-agent

Small, runnable demos for KazenAI **Control** budget and loop enforcement.

**Label honesty:** Hermetic examples use a fake provider. Hosted MultiSink is personal
HOSTED_DEMO only — not company staging certification, not production savings.

For the full D2–D7 admit/deny/tool-fail/corrected + Lens regression path, use
[`kazenai-examples/control-loop-and-failure`](../kazenai-examples/control-loop-and-failure/)
(see its `HOSTED_DEMO.md`).

## Install (PyPI)

```bash
cd kazenai-demo-agent
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Public packages: `kazenai==1.0.1`, `kazen-event-schema==0.6.0`.

Optional env:

```bash
export KAZENAI_DEMO_QUERY="research KazenAI budget enforcement"
export KAZENAI_DEMO_BUDGET_USD="0.25"
```

## Hermetic scenarios (CI)

```bash
pytest scenarios -q
```

- `BudgetExceeded` before a high-token task can run past the configured budget.
- `LoopDetected` after repeated recursive search suggestions.

Also:

```bash
python main.py
```

## SDK examples

Certified Control surface:

```python
from kazenai import monitor, BudgetExceeded

# client = monitor(openai_client, max_budget_usd=0.01, ...)
```

| Script | What it shows |
|--------|----------------|
| `examples/01_local_enforcement.py` | `Enforcement.check_local()` via the researcher agent (no network) |
| `examples/02_monitor_fake_provider.py` | `monitor()` + fake client; tiny cap → **0** provider calls |
| `examples/03_monitor_multisink_hosted.py` | HttpSink → staging FinOps; gated by `KAZENAI_DEMO_HOSTED=1` |
| `examples/04_capture_metadata_default.py` | Metadata-default capture (bodies omitted) |

```bash
python examples/01_local_enforcement.py
python examples/02_monitor_fake_provider.py
python examples/04_capture_metadata_default.py

# Hosted only (after staging URLs + API key):
export KAZENAI_DEMO_HOSTED=1
export KAZENAI_FINOPS_URL=https://finops.staging.kazenai.com
export KAZENAI_FINOPS_API_KEY=...
export KAZENAI_ORG_ID=...
export KAZENAI_WORKSPACE_ID=...
python examples/03_monitor_multisink_hosted.py
```

CI runs **pytest scenarios only**. Hosted example 03 refuses without the gate and is not enabled in PR CI.
