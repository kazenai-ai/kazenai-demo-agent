"""Provider clients for the framework examples (14-20).

By default every example runs **offline**: it uses the real OpenAI / Anthropic
SDK clients, but their HTTP transport returns canned, provider-shaped responses
(with real-looking token usage). Nothing leaves your machine and no key is
needed, so the examples run in CI.

Run any example with ``--live`` to use the real APIs instead. That needs
``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` and spends a few cents. Models default
to cheap ones and can be changed:

    KAZENAI_DEMO_OPENAI_MODEL=gpt-4o-mini
    KAZENAI_DEMO_ANTHROPIC_MODEL=claude-haiku-4-5

Nothing in this file is KazenAI-specific: in your own code you pass your normal
``OpenAI()`` / ``Anthropic()`` clients to KazenAI exactly as the examples do.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

Reply = Callable[[Dict[str, Any]], str]

# Usage the fake provider reports for every call (tokens in / out).
FAKE_INPUT_TOKENS = 1200
FAKE_OUTPUT_TOKENS = 300


def live_mode() -> bool:
    return "--live" in sys.argv[1:] or os.getenv("KAZENAI_DEMO_LIVE", "").strip() in {"1", "true", "yes"}


def openai_model() -> str:
    return os.getenv("KAZENAI_DEMO_OPENAI_MODEL", "gpt-4o-mini")


def anthropic_model() -> str:
    return os.getenv("KAZENAI_DEMO_ANTHROPIC_MODEL", "claude-haiku-4-5")


def local_only_env() -> None:
    """Run KazenAI with local budgets only (no Agent FinOps service needed)."""
    for key in ("KAZENAI_FINOPS_URL", "KAZENAI_FINOPS_INGEST_URL", "KAZENAI_INGEST_URL", "KAZENAI_UNKNOWN_MODEL_POLICY"):
        os.environ.pop(key, None)
    os.environ.setdefault("KAZENAI_ENV", "dev")
    os.environ.setdefault("KAZENAI_DEPLOYMENT_MODE", "development")
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    _quiet_logs()
    if not live_mode():
        # Some frameworks build their own client at construction and want a key.
        os.environ.setdefault("OPENAI_API_KEY", "sk-offline-demo")
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-offline-demo")


def _quiet_logs() -> None:
    """Show only warnings so the example's JSON result is readable."""
    import logging

    logging.basicConfig(level=logging.WARNING)
    for name in ("httpx", "kazenai", "crewai", "LiteLLM"):
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        import structlog

        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    except Exception:
        pass


# Distinct support tickets for the examples (distinct prompts: repeating the
# same prompt to one client is what KazenAI's loop guard is built to catch).
TICKETS = [
    "A customer was charged twice for the annual plan and wants one charge refunded.",
    "A user cannot reset their password because the reset email never arrives.",
    "An order shipped to the wrong warehouse address and is now delayed by a week.",
    "The invoice shows the wrong company VAT number and finance needs a corrected copy.",
    "A team admin wants to transfer workspace ownership before leaving the company.",
    "The mobile app crashes on login after the latest update on older Android phones.",
    "A customer asks whether their data is stored in the EU and for a DPA copy.",
    "Bulk CSV import fails silently for files larger than ten thousand rows.",
    "A reseller wants volume pricing for two hundred seats across three regions.",
    "Webhooks stopped firing for subscription renewals since yesterday evening.",
    "A user reports that dark mode makes chart labels unreadable in exported PDFs.",
    "The SSO login loops back to the sign-in page for one specific Okta tenant.",
]


def _default_reply(body: Dict[str, Any]) -> str:
    messages = body.get("messages") or []
    last = messages[-1].get("content") if messages else ""
    if isinstance(last, list):
        last = " ".join(str(p.get("text", "")) for p in last if isinstance(p, dict))
    words = str(last).split()
    return "(offline reply) " + " ".join(words[:12])


class _FakeOpenAI:
    def __init__(self, reply: Reply, calls: list) -> None:
        self.reply, self.calls = reply, calls

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append(body.get("model"))
        text = self.reply(body)
        usage = {"prompt_tokens": FAKE_INPUT_TOKENS, "completion_tokens": FAKE_OUTPUT_TOKENS,
                 "total_tokens": FAKE_INPUT_TOKENS + FAKE_OUTPUT_TOKENS}
        if body.get("stream"):
            chunks = [
                {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": body.get("model"),
                 "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]},
                {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": body.get("model"),
                 "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": body.get("model"),
                 "choices": [], "usage": usage},
            ]
            sse = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())
        return httpx.Response(200, json={
            "id": "c", "object": "chat.completion", "created": 1, "model": body.get("model"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": usage,
        })


class _FakeAnthropic:
    def __init__(self, reply: Reply, calls: list) -> None:
        self.reply, self.calls = reply, calls

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append(body.get("model"))
        text = self.reply(body)
        if body.get("stream"):
            events = [
                ("message_start", {"type": "message_start", "message": {
                    "id": "m", "type": "message", "role": "assistant", "content": [], "model": body.get("model"),
                    "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": FAKE_INPUT_TOKENS, "output_tokens": 1}}}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                   # Like the real API: final usage is cumulative.
                                   "usage": {"input_tokens": FAKE_INPUT_TOKENS, "output_tokens": FAKE_OUTPUT_TOKENS}}),
                ("message_stop", {"type": "message_stop"}),
            ]
            sse = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())
        return httpx.Response(200, json={
            "id": "m", "type": "message", "role": "assistant", "model": body.get("model"),
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
            "usage": {"input_tokens": FAKE_INPUT_TOKENS, "output_tokens": FAKE_OUTPUT_TOKENS},
        })


OFFLINE_OPENAI_BASE_URL = "https://api.openai.offline-demo/v1"
OFFLINE_ANTHROPIC_BASE_URL = "https://api.anthropic.offline-demo"


def openai_clients(reply: Optional[Reply] = None, calls: Optional[list] = None) -> Tuple[Any, Any]:
    """(OpenAI, AsyncOpenAI) — real SDK clients; offline transport unless --live."""
    import openai

    if live_mode():
        return openai.OpenAI(max_retries=0), openai.AsyncOpenAI(max_retries=0)
    fake = _FakeOpenAI(reply or _default_reply, calls if calls is not None else [])
    return (
        openai.OpenAI(api_key="sk-offline-demo", base_url=OFFLINE_OPENAI_BASE_URL, max_retries=0,
                      http_client=httpx.Client(transport=httpx.MockTransport(fake))),
        openai.AsyncOpenAI(api_key="sk-offline-demo", base_url=OFFLINE_OPENAI_BASE_URL, max_retries=0,
                           http_client=httpx.AsyncClient(transport=httpx.MockTransport(fake))),
    )


def anthropic_clients(reply: Optional[Reply] = None, calls: Optional[list] = None) -> Tuple[Any, Any]:
    """(Anthropic, AsyncAnthropic) — real SDK clients; offline transport unless --live."""
    import anthropic

    if live_mode():
        return anthropic.Anthropic(max_retries=0), anthropic.AsyncAnthropic(max_retries=0)
    fake = _FakeAnthropic(reply or _default_reply, calls if calls is not None else [])
    return (
        anthropic.Anthropic(api_key="sk-ant-offline-demo", base_url=OFFLINE_ANTHROPIC_BASE_URL, max_retries=0,
                            http_client=httpx.Client(transport=httpx.MockTransport(fake))),
        anthropic.AsyncAnthropic(api_key="sk-ant-offline-demo", base_url=OFFLINE_ANTHROPIC_BASE_URL, max_retries=0,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(fake))),
    )


def report(result: Dict[str, Any]) -> int:
    """Print the example's result as JSON and return its exit code."""
    result.setdefault("mode", "live" if live_mode() else "offline (fake provider transport)")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1
