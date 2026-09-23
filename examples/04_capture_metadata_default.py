#!/usr/bin/env python3
"""04 — Private-by-default capture (metadata mode; bodies omitted).

Shows that monitor() defaults to metadata capture unless consent/full mode is set.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any


class _FakeCompletions:
    def create(self, *args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="SECRET_BODY_SHOULD_NOT_BE_CAPTURED_BY_DEFAULT")
                )
            ],
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def main() -> int:
    for key in ("KAZENAI_FINOPS_URL", "KAZENAI_FINOPS_INGEST_URL", "KAZENAI_INGEST_URL"):
        os.environ.pop(key, None)
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.setdefault("KAZENAI_ENV", "dev")
    os.environ.setdefault("KAZENAI_DEPLOYMENT_MODE", "development")
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")

    from kazenai import monitor
    from kazenai.capture_policy import capture_disclosure, resolve_capture_mode

    mode = resolve_capture_mode(explicit=None, consent=None)
    disclosure = capture_disclosure(mode)
    client = FakeOpenAI()
    monitored = monitor(
        client,
        org_id="local",
        project_id="default",
        agent_id="demo-capture",
        max_budget_usd=1.0,
        capture_mode=None,  # default metadata
        capture_consent=False,
    )
    resp = monitored.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "include a canary body"}],
    )
    print(
        json.dumps(
            {
                "ok": True,
                "capture_mode": str(mode),
                "disclosure": disclosure,
                "response_content": resp.choices[0].message.content,
                "note": "Default capture is metadata; request/response bodies are omitted from sinks unless explicitly opted in with consent.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
