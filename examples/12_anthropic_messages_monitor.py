#!/usr/bin/env python3
"""12 — monitor() on an Anthropic-shaped messages.create client.

Hermetic fake Anthropic surface (no anthropic package / no API key required).

Shows:
- monitor() detects `.messages.create` and patches the Anthropic path
- usage uses input_tokens / output_tokens
- tiny max_budget_usd → BudgetExceeded with 0 provider calls
- a second run with a normal cap allows one call

Evidence tier: hermetic fake.
Certified range when using the real SDK: anthropic>=0.39,<1.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, Optional


class _FakeMessages:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
            content=[SimpleNamespace(type="text", text="synthetic-ok")],
            stop_reason="end_turn",
        )


class FakeAnthropic:
    def __init__(self) -> None:
        self.messages = _FakeMessages()


def _hermetic_env() -> None:
    for key in (
        "KAZENAI_FINOPS_URL",
        "KAZENAI_FINOPS_INGEST_URL",
        "KAZENAI_INGEST_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "KAZENAI_UNKNOWN_MODEL_POLICY",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("KAZENAI_ENV", "dev")
    os.environ.setdefault("KAZENAI_DEPLOYMENT_MODE", "development")
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")


def _attempt(*, max_budget_usd: float, label: str) -> Dict[str, Any]:
    from kazenai import BudgetExceeded, monitor

    client = FakeAnthropic()
    monitored = monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="demo-anthropic",
        max_budget_usd=max_budget_usd,
        soft_pause_pct=100.0,
        loop_anomaly_threshold=1.0,
        business_subject_ref="cust:acme-42",
        feature_id="anthropic_support_reply",
        workflow_id="support_ticket.v1",
    )
    terminal: Optional[str] = None
    error: Optional[str] = None
    try:
        monitored.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=64,
            messages=[{"role": "user", "content": f"hermetic anthropic {label}"}],
        )
        terminal = "allowed"
    except BudgetExceeded as exc:
        terminal = "budget_exceeded"
        error = str(exc)
    except BaseException as exc:  # noqa: BLE001
        terminal = type(exc).__name__
        error = str(exc)
    return {
        "label": label,
        "max_budget_usd": max_budget_usd,
        "terminal": terminal,
        "error": error,
        "provider_calls": client.messages.calls,
        "method": "anthropic.messages.create",
    }


def main() -> int:
    _hermetic_env()
    denied = _attempt(max_budget_usd=0.000001, label="tiny-cap")
    allowed = _attempt(max_budget_usd=1.0, label="normal-cap")

    ok = (
        denied["terminal"] == "budget_exceeded"
        and denied["provider_calls"] == 0
        and allowed["terminal"] == "allowed"
        and allowed["provider_calls"] == 1
    )

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "hermetic_fake",
                "certified_provider_sdk_range": "anthropic>=0.39,<1",
                "cases": [denied, allowed],
                "proves": (
                    "The same monitor() entrypoint wraps an Anthropic-shaped "
                    "messages.create client; tiny budgets deny before dispatch and "
                    "usage settles from input_tokens/output_tokens."
                ),
                "does_not_prove": (
                    "Live Anthropic network I/O, Anthropic streaming managers, or "
                    "installing the anthropic package (this fake only needs the Core surface)."
                ),
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
