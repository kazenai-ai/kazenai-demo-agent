#!/usr/bin/env python3
"""08 — Multi-step agent runaway stopped by max_budget_usd (not loop detector).

Hermetic fake provider. No keys.

Story: a planner schedules many sequential model calls (e.g. "keep solving").
Control does not guess task difficulty from the prompt. It admits the first
call under a one-projection cap, settles actual usage, then denies the next
dispatch with BudgetExceeded — remaining planned steps never hit the provider.

Evidence tier: hermetic fake + local Enforcement.
Does not prove distributed FinOps reservation or overnight wall-clock jobs.
"""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        # Actual usage is intentionally smaller than a full pre-call projection
        # so remaining headroom after settle is below another projection.
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=40, completion_tokens=20, total_tokens=60),
            choices=[SimpleNamespace(message=SimpleNamespace(content="synthetic-partial"))],
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def _hermetic_env() -> None:
    for key in (
        "KAZENAI_FINOPS_URL",
        "KAZENAI_FINOPS_INGEST_URL",
        "KAZENAI_INGEST_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        os.environ.pop(key, None)
    os.environ.setdefault("KAZENAI_ENV", "dev")
    os.environ.setdefault("KAZENAI_DEPLOYMENT_MODE", "development")
    os.environ.setdefault("KAZENAI_ENFORCEMENT_MODE", "fail_open")
    os.environ.setdefault("KAZENAI_FINOPS_RESERVATION_MODE", "fail_open")


def main() -> int:
    _hermetic_env()
    from kazenai import BudgetExceeded, monitor
    from kazenai.monitor import _precall_projection_usd

    planned_steps = 20
    model = "gpt-4o-mini"
    one_projection = float(_precall_projection_usd({"model": model}, None))
    # Cap equals one pre-call projection: first call allowed, second denied
    # before provider dispatch (same contract as private runaway_then_deny).
    cap = one_projection

    client = FakeOpenAI()
    monitored = monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="demo-runaway-agent",
        max_budget_usd=cap,
        # Keep soft CB / loop anomaly from stealing the budget-deny story.
        soft_pause_pct=100.0,
        loop_anomaly_threshold=1.0,
    )

    allowed = 0
    denied = 0
    terminal: Optional[str] = None
    steps: List[Dict[str, Any]] = []

    for i in range(planned_steps):
        try:
            monitored.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        # Distinct content avoids LoopDetected before budget check.
                        "content": f"Solve step {i} of the long task {uuid.uuid4().hex}",
                    }
                ],
            )
            allowed += 1
            steps.append({"step": i, "outcome": "allowed", "provider_calls": client.chat.completions.calls})
        except BudgetExceeded as exc:
            denied += 1
            terminal = "budget_exceeded"
            steps.append(
                {
                    "step": i,
                    "outcome": "budget_exceeded",
                    "error": str(exc),
                    "provider_calls": client.chat.completions.calls,
                }
            )
            break
        except BaseException as exc:  # noqa: BLE001 - surface unexpected terminals
            terminal = type(exc).__name__
            steps.append({"step": i, "outcome": "unexpected", "error": str(exc)})
            break

    never_dispatched = planned_steps - allowed - denied
    ok = (
        allowed == 1
        and denied == 1
        and client.chat.completions.calls == 1
        and terminal == "budget_exceeded"
        and never_dispatched == planned_steps - 2
    )

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "hermetic_fake",
                "planned_steps": planned_steps,
                "max_budget_usd": cap,
                "one_projection_usd": one_projection,
                "allowed_steps": allowed,
                "denied_budget_exceeded": denied,
                "never_dispatched_after_deny": never_dispatched,
                "provider_calls": client.chat.completions.calls,
                "terminal_reason": terminal,
                "steps": steps,
                "proves": (
                    "A multi-step agent loop is stopped by cumulative budget authority: "
                    "one call settles, the next is BudgetExceeded before provider dispatch, "
                    "and remaining planned steps never run."
                ),
                "does_not_prove": (
                    "Prompt-complexity cost prediction, 8–10 hour wall-clock jobs, or "
                    "distributed multi-host reservation. Control bounds max exposure per "
                    "call and cumulative budget — it does not infer task difficulty from "
                    "the user message."
                ),
                "guard": "BudgetExceeded (not LoopDetected)",
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
