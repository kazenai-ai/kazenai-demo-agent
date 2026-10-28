# Changelog

Notable changes to the KazenAI demo agent, newest first. Each release is also published on
[GitHub Releases](https://github.com/kazenai-ai/kazenai-demo-agent/releases).

## 0.3.0 - 2026-10-28

Updated for `kazenai` 1.2.0.

- Runs on `kazenai` 1.2.0 and `kazen-event-schema` 0.6.6.
- The CrewAI example uses the certified `wrap_crew` setup. A budget denial now
  stops the crew without retries.
- The supported-surfaces table includes the OpenAI Responses API.

```bash
python -m pip install "kazenai[openai]==1.2.0"
```

## 0.2.0 - 2026-10-13

Published on `main` without a tag or GitHub Release.

Framework recipes for teams adding KazenAI to existing agent workflows. Aligned
with Core/FinOps **1.1.3**.

### New examples (offline by default, `--live` for real providers)

- 14: one `SharedBudget` across OpenAI and Anthropic clients
- 15: LangChain `ChatOpenAI` / `ChatAnthropic` (invoke, stream, ainvoke, structured output)
- 16: LangChain LCEL chain mixing two providers on one budget
- 17: LangGraph plan → draft → review across three models, with per-step spend
- 18: LangGraph human approval with SQLite checkpoint and resume
- 19: CrewAI two-agent crew on one budget (preview)
- 20: LiteLLM proxy with per-model pricing

### Other changes

- Pins: `kazenai==1.1.3`, `kazen-event-schema==0.6.5`
- New `requirements-frameworks.txt` and `requirements-crewai.txt`
- Example 12 uses `claude-sonnet-4-6` (the previous model is retired and now refused)
- CI runs the framework recipes (offline) in their own jobs
- `.env.example` documents the `--live` variables

### Verified

All examples pass offline in CI. On 2026-10-12, examples 14–19 were also run with
`--live` against the paid OpenAI and Anthropic APIs; each spent less than one cent
and was stopped by its budget as designed. Example 20 live needs a LiteLLM proxy.

## 0.1.1 - 2026-10-04

Offline demo aligned with Core/FinOps **1.1.1**.

### Install

```bash
git clone https://github.com/kazenai-ai/kazenai-demo-agent.git
cd kazenai-demo-agent
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python examples/02_monitor_fake_provider.py
```

Pins: `kazenai==1.1.1`, `kazen-event-schema==0.6.3`.

### What changed

- New keyless examples: customer/feature attribution, streaming lifecycle, concurrent local reservation
- `SECURITY.md` and issue templates
- README documents supported sync streaming and bounded FinOps extras

### Supported / unsupported

- Supported in Core/FinOps 1.1.x: sync OpenAI/Anthropic non-streaming and selected streaming
- Unsupported: async, Responses, Realtime, Bedrock/Vertex

### Links

- Docs: https://docs.kazenai.com/guides/control-demo/
- Issues: https://github.com/kazenai-ai/kazenai-demo-agent/issues

Earlier releases: [GitHub Releases](https://github.com/kazenai-ai/kazenai-demo-agent/releases).
