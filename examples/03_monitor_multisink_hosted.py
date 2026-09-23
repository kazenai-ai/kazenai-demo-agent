#!/usr/bin/env python3
"""03 — monitor() MultiSink → staging FinOps (+ optional Lens via separate ingest).

Refuses unless KAZENAI_DEMO_HOSTED=1. Fake provider only — no live model keys.
Personal HOSTED_DEMO; not company staging certification.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from types import SimpleNamespace
from typing import Any


def _refuse(msg: str, code: int = 3) -> int:
    print(json.dumps({"ok": False, "error": msg, "label": "personal_HOSTED_DEMO"}))
    return code


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            choices=[SimpleNamespace(message=SimpleNamespace(content="hosted-demo-ok"))],
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def main() -> int:
    if os.getenv("KAZENAI_DEMO_HOSTED", "").strip().lower() not in {"1", "true", "yes"}:
        return _refuse("Set KAZENAI_DEMO_HOSTED=1 after staging URLs + API key are configured")

    finops = (
        os.getenv("KAZENAI_FINOPS_INGEST_URL")
        or os.getenv("KAZENAI_FINOPS_URL")
        or os.getenv("FINOPS_URL")
        or ""
    ).strip().rstrip("/")
    api_key = (os.getenv("KAZENAI_FINOPS_API_KEY") or os.getenv("KAZENAI_API_KEY") or "").strip()
    if not finops or not api_key:
        return _refuse("Need KAZENAI_FINOPS_URL (or INGEST_URL) and KAZENAI_FINOPS_API_KEY")

    # Ensure HttpSink activates inside monitor().
    os.environ["KAZENAI_FINOPS_URL"] = finops
    os.environ["KAZENAI_FINOPS_API_KEY"] = api_key
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)

    from kazenai import BudgetExceeded, monitor

    run_id = f"demo-hosted-{uuid.uuid4().hex[:10]}"
    client = FakeOpenAI()
    monitored = monitor(
        client,
        org_id=os.getenv("KAZENAI_ORG_ID", "local"),
        project_id=os.getenv("KAZENAI_PROJECT_ID")
        or os.getenv("KAZENAI_WORKSPACE_ID", "default"),
        workspace_id=os.getenv("KAZENAI_WORKSPACE_ID", "default"),
        agent_id="demo-monitor-hosted",
        max_budget_usd=float(os.getenv("KAZENAI_DEMO_BUDGET_USD", "1.0")),
        timeline_path=os.getenv("KAZENAI_TIMELINE_PATH") or None,
    )
    try:
        monitored.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"hosted demo run {run_id}"}],
        )
    except BudgetExceeded as exc:
        print(
            json.dumps(
                {
                    "ok": True,
                    "denied": True,
                    "run_hint": run_id,
                    "provider_calls": client.chat.completions.calls,
                    "error": str(exc),
                    "finops": finops,
                    "note": "Open FinOps /ui/ and Lens with your org scope after sink flush",
                },
                indent=2,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "ok": True,
                "denied": False,
                "run_hint": run_id,
                "provider_calls": client.chat.completions.calls,
                "finops": finops,
                "lens": os.getenv("KAZENAI_LENS_URL") or os.getenv("LENS_URL"),
                "note": "Events fan out via HttpSink when FinOps URL is set; allow a few seconds then search Lens",
                "label": "personal_HOSTED_DEMO_not_company_staging_cert",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
