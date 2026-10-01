# kazenai-demo-agent

Small, runnable demos for KazenAI **Control** budget and loop enforcement.

**Label honesty:** Hermetic examples use a fake provider. Hosted MultiSink is personal
HOSTED_DEMO only — not company staging certification, not production savings.

This repository is self-contained. Clone it alone, install from PyPI, and run the
hermetic path below. No sibling KazenAI checkout is required.

Docs: [Control demo guide](https://docs.kazenai.com/guides/control-demo/)
(after `docs.kazenai.com` is live). Until then, use the SDK examples in this repo.

## Install (PyPI)

```bash
git clone https://github.com/kazenai-ai/kazenai-demo-agent.git
cd kazenai-demo-agent
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Public package pins (reproducible demo):

- `kazenai==1.0.5`
- `kazen-event-schema==0.6.3`

Dependencies install from public PyPI. This demo does **not** ship offline vendor
wheels.

Optional env:

```bash
export KAZENAI_DEMO_QUERY="research KazenAI budget enforcement"
export KAZENAI_DEMO_BUDGET_USD="0.25"
```

## Hermetic scenarios (CI)

```bash
python -m pytest scenarios -q
```

- `BudgetExceeded` before a high-token task can run past the configured budget.
- `LoopDetected` after repeated recursive search suggestions.

Also:

```bash
python main.py
```

## Smoke: pre-dispatch denial (no provider keys)

Proves a tiny budget causes **zero** fake-provider calls:

```bash
python -m examples.02_monitor_fake_provider
# or:
python examples/02_monitor_fake_provider.py
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

# Hosted only (after staging URLs + API key; never commit credentials):
export KAZENAI_DEMO_HOSTED=1
export KAZENAI_FINOPS_URL=https://finops.staging.kazenai.com
export KAZENAI_FINOPS_API_KEY=...
export KAZENAI_ORG_ID=...
export KAZENAI_WORKSPACE_ID=...
python examples/03_monitor_multisink_hosted.py
```

CI runs **pytest scenarios** plus the hermetic monitor smoke. Hosted example 03
refuses without `KAZENAI_DEMO_HOSTED=1` and is not enabled for live network calls
in PR CI.

## Supported surfaces (demo scope)

| Path | Status |
|------|--------|
| Sync OpenAI `chat.completions.create` (non-streaming) via `monitor()` | Supported |
| Streaming / async / Responses / Realtime | Unsupported in this demo |
