# kazenai-demo-agent v0.1.1

Public hermetic demo aligned with Core/FinOps **1.1.1**.

## Install

```bash
git clone https://github.com/kazenai-ai/kazenai-demo-agent.git
cd kazenai-demo-agent
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python examples/02_monitor_fake_provider.py
```

Pins: `kazenai==1.1.1`, `kazen-event-schema==0.6.3`.

## What changed

- New keyless examples: customer/feature attribution, streaming lifecycle, concurrent local reservation
- `SECURITY.md` and issue templates
- README documents supported sync streaming and bounded FinOps extras

## Supported / unsupported

- Supported in Core/FinOps 1.1.x: sync OpenAI/Anthropic non-streaming and selected streaming
- Unsupported: async, Responses, Realtime, Bedrock/Vertex

## Links

- Docs: https://docs.kazenai.com/guides/control-demo/
- Issues: https://github.com/kazenai-ai/kazenai-demo-agent/issues
