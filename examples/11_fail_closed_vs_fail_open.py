#!/usr/bin/env python3
"""11 — Fail-closed vs fail-open (and unknown-model block) posture.

Hermetic fake provider. No keys / no FinOps URL.

Shows three distinct pre-dispatch outcomes:
1) fail_closed + no FinOps URL → BudgetUnavailable (0 provider calls)
2) fail_open + KAZENAI_ENV=dev → call allowed under local budget
3) KAZENAI_UNKNOWN_MODEL_POLICY=block → UnknownModelError (0 provider calls)

Evidence tier: hermetic config fixture.
Does not prove hosted FinOps HA or production DNS/auth wiring.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def _clear_kazen_env() -> None:
    for key in list(os.environ):
        if key.startswith("KAZENAI_") or key in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}:
            os.environ.pop(key, None)


def _run_case(name: str, *, setup: Any, model: str) -> Dict[str, Any]:
    from kazenai import BudgetUnavailable, UnknownModelError, monitor

    _clear_kazen_env()
    setup()
    client = FakeOpenAI()
    monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id=f"demo-{name}",
        max_budget_usd=5.0,
        soft_pause_pct=100.0,
        loop_anomaly_threshold=1.0,
    )
    terminal: Optional[str] = None
    error: Optional[str] = None
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": f"case-{name}"}],
        )
        terminal = "allowed"
    except BudgetUnavailable as exc:
        terminal = "budget_unavailable"
        error = str(exc)
    except UnknownModelError as exc:
        terminal = "unknown_model"
        error = str(exc)
    except BaseException as exc:  # noqa: BLE001
        terminal = type(exc).__name__
        error = str(exc)
    return {
        "case": name,
        "terminal": terminal,
        "error": error,
        "provider_calls": client.chat.completions.calls,
        "env": {
            "KAZENAI_ENV": os.getenv("KAZENAI_ENV"),
            "KAZENAI_DEPLOYMENT_MODE": os.getenv("KAZENAI_DEPLOYMENT_MODE"),
            "KAZENAI_ENFORCEMENT_MODE": os.getenv("KAZENAI_ENFORCEMENT_MODE"),
            "KAZENAI_FINOPS_RESERVATION_MODE": os.getenv("KAZENAI_FINOPS_RESERVATION_MODE"),
            "KAZENAI_UNKNOWN_MODEL_POLICY": os.getenv("KAZENAI_UNKNOWN_MODEL_POLICY"),
        },
    }


def main() -> int:
    cases: List[Dict[str, Any]] = []

    def setup_fail_closed() -> None:
        os.environ["KAZENAI_ENV"] = "production"
        os.environ["KAZENAI_DEPLOYMENT_MODE"] = "production"
        os.environ["KAZENAI_ENFORCEMENT_MODE"] = "fail_closed"
        os.environ["KAZENAI_FINOPS_RESERVATION_MODE"] = "fail_closed"

    def setup_fail_open() -> None:
        os.environ["KAZENAI_ENV"] = "dev"
        os.environ["KAZENAI_DEPLOYMENT_MODE"] = "development"
        os.environ["KAZENAI_ENFORCEMENT_MODE"] = "fail_open"
        os.environ["KAZENAI_FINOPS_RESERVATION_MODE"] = "fail_open"

    def setup_unknown_block() -> None:
        os.environ["KAZENAI_ENV"] = "dev"
        os.environ["KAZENAI_DEPLOYMENT_MODE"] = "development"
        os.environ["KAZENAI_ENFORCEMENT_MODE"] = "fail_open"
        os.environ["KAZENAI_FINOPS_RESERVATION_MODE"] = "fail_open"
        os.environ["KAZENAI_UNKNOWN_MODEL_POLICY"] = "block"

    cases.append(_run_case("fail_closed_no_finops_url", setup=setup_fail_closed, model="gpt-4o-mini"))
    cases.append(_run_case("fail_open_local_dev", setup=setup_fail_open, model="gpt-4o-mini"))
    cases.append(
        _run_case(
            "unknown_model_block",
            setup=setup_unknown_block,
            model="unpriced-provider/model",
        )
    )

    ok = (
        cases[0]["terminal"] == "budget_unavailable"
        and cases[0]["provider_calls"] == 0
        and cases[1]["terminal"] == "allowed"
        and cases[1]["provider_calls"] == 1
        and cases[2]["terminal"] == "unknown_model"
        and cases[2]["provider_calls"] == 0
    )

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "hermetic_config_fixture",
                "cases": cases,
                "proves": (
                    "Fail-closed refuses dispatch when shared FinOps authority is absent "
                    "(BudgetUnavailable); fail-open local-dev still allows a known model; "
                    "unknown-model block policy denies before provider dispatch."
                ),
                "does_not_prove": (
                    "Hosted FinOps availability, DNS, auth, or that fail-open is safe in "
                    "production (prod-like deploys refuse fail-open posture)."
                ),
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
