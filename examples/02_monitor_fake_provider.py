#!/usr/bin/env python3
"""02 — monitor() + fake OpenAI client; tiny max_budget_usd → 0 provider calls.

Control-certified surface (FINAL_1): sync chat.completions via kazenai.monitor.
No paid I/O. D3 story: BudgetExceeded before the first provider dispatch.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any, Dict


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=2000, completion_tokens=2000, total_tokens=4000),
            choices=[SimpleNamespace(message=SimpleNamespace(content="should-not-run"))],
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def main() -> int:
    # Clear remote ingest so this stays hermetic.
    for key in (
        "KAZENAI_FINOPS_URL",
        "KAZENAI_FINOPS_INGEST_URL",
        "KAZENAI_INGEST_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")

    from kazenai import BudgetExceeded, monitor

    client = FakeOpenAI()
    monitored = monitor(
        client,
        org_id=os.getenv("KAZENAI_ORG_ID", "local"),
        project_id=os.getenv("KAZENAI_PROJECT_ID", "default"),
        workspace_id=os.getenv("KAZENAI_WORKSPACE_ID", "default"),
        agent_id="demo-monitor-fake",
        max_budget_usd=float(os.getenv("KAZENAI_DEMO_BUDGET_USD", "0.000001")),
    )
    try:
        monitored.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "tiny cap must deny before invoke"}],
        )
    except BudgetExceeded as exc:
        print(
            {
                "ok": True,
                "terminal_reason": "budget_exceeded",
                "provider_calls": client.chat.completions.calls,
                "error": str(exc),
            }
        )
        return 0 if client.chat.completions.calls == 0 else 1

    print({"ok": False, "error": "expected BudgetExceeded", "provider_calls": client.chat.completions.calls})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
