#!/usr/bin/env python3
"""06 — Sync OpenAI streaming lifecycle with hermetic fake chunks.

Demonstrates:
  reserve maximum exposure -> provider_started -> observe stream
  -> authoritative usage at EOF -> settle actual
and a second path where early close leaves financial_pending / unknown
rather than inventing an exact-zero cost.

Certified range: openai>=1.40,<2 (this demo uses a fake client shape).
Client close does not prove the provider stopped billing.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Iterator, List


class _FakeOpenAIStream:
    def __init__(self, chunks: List[Any]) -> None:
        self._chunks = list(chunks)
        self._i = 0
        self.closed = False

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        if self._i >= len(self._chunks):
            raise StopIteration
        chunk = self._chunks[self._i]
        self._i += 1
        return chunk

    def close(self) -> None:
        self.closed = True


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0
        self.last_kwargs: dict[str, Any] = {}
        self.chunks: List[Any] = []

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.last_kwargs = dict(kwargs)
        self.calls += 1
        if kwargs.get("stream"):
            return _FakeOpenAIStream(self.chunks)
        raise AssertionError("this example expects stream=True")


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def _text(content: str) -> dict:
    return {"choices": [{"delta": {"content": content}}]}


def _usage(*, prompt: int = 10, completion: int = 6) -> dict:
    return {
        "choices": [],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


def _hermetic_env() -> None:
    for key in (
        "KAZENAI_FINOPS_URL",
        "KAZENAI_FINOPS_INGEST_URL",
        "KAZENAI_INGEST_URL",
        "OPENAI_API_KEY",
        "KAZENAI_DENY_STREAMING",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("KAZENAI_ENV", "dev")
    os.environ.setdefault("KAZENAI_DEPLOYMENT_MODE", "development")
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_CONTROL_PROFILE", "1")


def main() -> int:
    _hermetic_env()
    from kazenai import monitor
    from kazenai.streaming.lifecycle import StreamOutcome

    # Path A: complete stream with authoritative usage.
    complete_client = FakeOpenAI()
    complete_client.chat.completions.chunks = [_text("hello "), _text("world"), _usage()]
    monitor(complete_client, agent_id="demo-stream", max_budget_usd=1.0)
    complete_stream = complete_client.chat.completions.create(
        model="gpt-4o-mini",
        stream=True,
        messages=[{"role": "user", "content": "synthetic"}],
    )
    visible = list(complete_stream)
    complete_attempt = complete_stream._attempt

    # Path B: early client close before EOF / usage.
    cancel_client = FakeOpenAI()
    cancel_client.chat.completions.chunks = [_text("partial"), _usage()]
    monitor(cancel_client, agent_id="demo-stream-cancel", max_budget_usd=1.0)
    cancel_stream = cancel_client.chat.completions.create(
        model="gpt-4o-mini",
        stream=True,
        messages=[{"role": "user", "content": "synthetic"}],
    )
    next(iter(cancel_stream))
    cancel_stream.close()
    cancel_attempt = cancel_stream._attempt

    opts = complete_client.chat.completions.last_kwargs.get("stream_options") or {}
    ok = (
        len(visible) == 3
        and opts.get("include_usage") is True
        and complete_attempt.finalized
        and complete_attempt.terminal_outcome == StreamOutcome.COMPLETE
        and complete_attempt.financial_pending is False
        and complete_attempt.cost_confidence == "exact"
        and cancel_attempt.finalized
        and cancel_attempt.terminal_outcome == StreamOutcome.CLIENT_CANCELLED
        and cancel_attempt.financial_pending is True
        and getattr(cancel_stream._upstream, "closed", False) is True
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "certified_provider_sdk_range": "openai>=1.40,<2",
                "complete": {
                    "chunks_visible_to_caller": len(visible),
                    "terminal_outcome": str(complete_attempt.terminal_outcome),
                    "financial_pending": complete_attempt.financial_pending,
                    "cost_confidence": complete_attempt.cost_confidence,
                    "finalized_once": complete_attempt.finalized,
                },
                "early_close": {
                    "terminal_outcome": str(cancel_attempt.terminal_outcome),
                    "financial_pending": cancel_attempt.financial_pending,
                    "note": (
                        "Pending/unknown — not exact zero. Client close does not prove "
                        "the provider stopped generating or billing."
                    ),
                },
                "content_persisted_by_default": False,
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
