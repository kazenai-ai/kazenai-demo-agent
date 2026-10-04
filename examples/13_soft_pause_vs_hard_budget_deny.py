#!/usr/bin/env python3
"""13 — Soft KazenCircuitBreaker vs hard BudgetExceeded.

Hermetic fake provider. No keys.

Shows two different failure modes developers often confuse:
1) Soft trajectory pause → KazenCircuitBreaker AFTER a provider call completes
2) Hard local cap → BudgetExceeded BEFORE provider dispatch (0 calls)

Evidence tier: hermetic fake.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


class _FakeCompletions:
    def __init__(self, usage: Any) -> None:
        self.calls = 0
        self.usage = usage

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            usage=self.usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )


class FakeOpenAI:
    def __init__(self, usage: Any) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(usage))


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


def _soft_pause_case() -> Dict[str, Any]:
    from kazenai import BudgetExceeded, KazenCircuitBreaker, monitor

    # Large recorded usage so soft trajectory pause trips after the call.
    usage = SimpleNamespace(prompt_tokens=50_000, completion_tokens=50_000, total_tokens=100_000)
    client = FakeOpenAI(usage)
    monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="demo-soft-pause",
        max_budget_usd=0.50,
        soft_pause_pct=0.10,
        loop_anomaly_threshold=1.0,
    )
    raised: List[BaseException] = []
    for i in range(5):
        try:
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": f"soft-pause-{i}"}],
            )
        except KazenCircuitBreaker as exc:
            raised.append(exc)
            break
        except BudgetExceeded as exc:
            return {
                "case": "soft_pause",
                "terminal": "budget_exceeded",
                "error": str(exc),
                "provider_calls": client.chat.completions.calls,
                "ok": False,
                "note": "expected KazenCircuitBreaker, got hard BudgetExceeded",
            }
    return {
        "case": "soft_pause",
        "terminal": "kazen_circuit_breaker" if raised else "none",
        "error": str(raised[0]) if raised else None,
        "provider_calls": client.chat.completions.calls,
        "ok": bool(raised) and client.chat.completions.calls >= 1,
        "timing": "after_provider_call",
    }


def _hard_deny_case() -> Dict[str, Any]:
    from kazenai import BudgetExceeded, KazenCircuitBreaker, monitor

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=10, total_tokens=20)
    client = FakeOpenAI(usage)
    monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="demo-hard-deny",
        max_budget_usd=0.000001,
        soft_pause_pct=100.0,
        loop_anomaly_threshold=1.0,
    )
    terminal: Optional[str] = None
    error: Optional[str] = None
    try:
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hard-deny"}],
        )
        terminal = "allowed"
    except BudgetExceeded as exc:
        terminal = "budget_exceeded"
        error = str(exc)
    except KazenCircuitBreaker as exc:
        terminal = "kazen_circuit_breaker"
        error = str(exc)
    except BaseException as exc:  # noqa: BLE001
        terminal = type(exc).__name__
        error = str(exc)
    return {
        "case": "hard_budget_deny",
        "terminal": terminal,
        "error": error,
        "provider_calls": client.chat.completions.calls,
        "ok": terminal == "budget_exceeded" and client.chat.completions.calls == 0,
        "timing": "before_provider_dispatch",
    }


def main() -> int:
    _hermetic_env()
    soft = _soft_pause_case()
    hard = _hard_deny_case()
    ok = bool(soft.get("ok")) and bool(hard.get("ok"))

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "hermetic_fake",
                "cases": [soft, hard],
                "proves": (
                    "KazenCircuitBreaker is a soft post-call trajectory pause; "
                    "BudgetExceeded is a hard pre-dispatch deny with zero provider calls."
                ),
                "does_not_prove": (
                    "That soft pause stops provider-side billing already in flight, or "
                    "that soft pause alone is a hard spending ceiling."
                ),
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
