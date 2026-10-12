# kazenai-demo-agent v0.2.0

Framework recipes for teams adding KazenAI to existing agent workflows. Aligned
with Core/FinOps **1.1.3**.

## New examples (offline by default, `--live` for real providers)

- 14: one `SharedBudget` across OpenAI and Anthropic clients
- 15: LangChain `ChatOpenAI` / `ChatAnthropic` (invoke, stream, ainvoke, structured output)
- 16: LangChain LCEL chain mixing two providers on one budget
- 17: LangGraph plan → draft → review across three models, with per-step spend
- 18: LangGraph human approval with SQLite checkpoint and resume
- 19: CrewAI two-agent crew on one budget (preview)
- 20: LiteLLM proxy with per-model pricing

## Other changes

- Pins: `kazenai==1.1.3`, `kazen-event-schema==0.6.5`
- New `requirements-frameworks.txt` and `requirements-crewai.txt`
- Example 12 uses `claude-sonnet-4-6` (the previous model is retired and now refused)
- CI runs the framework recipes (offline) in their own jobs
- `.env.example` documents the `--live` variables

## Verified

All examples pass offline in CI. On 2026-10-12, examples 14–19 were also run with
`--live` against the paid OpenAI and Anthropic APIs; each spent less than one cent
and was stopped by its budget as designed. Example 20 live needs a LiteLLM proxy.
