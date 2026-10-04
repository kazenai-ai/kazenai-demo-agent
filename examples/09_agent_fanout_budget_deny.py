#!/usr/bin/env python3
"""09 — Parent agent fans out subagents; shared budget catches oversubscription.

Hermetic fake provider. No keys.

Story: one parent task launches N parallel subagents that share a single
process-local max_budget_usd. While the first subagent holds projected spend
inside the provider, siblings are denied with BudgetExceeded before dispatch.

Evidence tier: local process integration fixture (thread-safe Enforcement).
Does NOT prove distributed / multi-host cluster budget authority.
"""

from __future__ import annotations

import itertools
import json
import os
import threading
import time
from types import SimpleNamespace
from typing import Any, List, Optional


class FakeCompletions:
    def __init__(self, *, hold: Optional[threading.Event] = None) -> None:
        self.calls = 0
        self.lock = threading.Lock()
        self._hold = hold
        self.in_provider = threading.Event()

    def create(self, *args: Any, **kwargs: Any) -> Any:
        with self.lock:
            self.calls += 1
        self.in_provider.set()
        if self._hold is not None:
            self._hold.wait(timeout=5)
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            choices=[SimpleNamespace(message=SimpleNamespace(content="subagent-ok"))],
        )


class FakeOpenAI:
    def __init__(self, *, hold: Optional[threading.Event] = None) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(hold=hold))


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

    fanout = 8
    model = "gpt-4o"
    projected = float(_precall_projection_usd({"model": model}, None))
    hold = threading.Event()
    client = FakeOpenAI(hold=hold)

    # Parent agent + shared local authority: headroom for ~one in-flight projection.
    monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="demo-parent-fanout",
        max_budget_usd=projected * 1.1,
        soft_pause_pct=100.0,
        loop_anomaly_threshold=1.0,
    )

    results: List[Optional[BaseException]] = []
    lock = threading.Lock()
    counter = itertools.count()

    def subagent() -> None:
        idx = next(counter)
        err: Optional[BaseException] = None
        try:
            client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        # Distinct text avoids LoopDetected before the budget check.
                        "content": f"subagent-{idx}-branch-{time.time_ns()}",
                    }
                ],
            )
        except BaseException as exc:  # noqa: BLE001 - collect exact outcomes
            err = exc
        with lock:
            results.append(err)

    # First subagent enters the provider and holds the reservation.
    first = threading.Thread(target=subagent, name="subagent-0")
    first.start()
    assert client.chat.completions.in_provider.wait(timeout=5)

    siblings = [threading.Thread(target=subagent, name=f"subagent-{i}") for i in range(1, fanout)]
    for t in siblings:
        t.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        with lock:
            if len(results) >= fanout - 1:
                break
        time.sleep(0.01)

    hold.set()
    first.join(timeout=5)
    for t in siblings:
        t.join(timeout=5)

    allowed = sum(1 for r in results if r is None)
    denied = sum(1 for r in results if isinstance(r, BudgetExceeded))
    other = len(results) - allowed - denied
    ok = (
        len(results) == fanout
        and allowed == 1
        and denied == fanout - 1
        and other == 0
        and client.chat.completions.calls == 1
    )

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "local_process_integration_fixture",
                "parent_agent_id": "demo-parent-fanout",
                "fanout_subagents": fanout,
                "max_budget_usd": projected * 1.1,
                "one_projection_usd": projected,
                "provider_calls": client.chat.completions.calls,
                "allowed_subagents": allowed,
                "denied_budget_exceeded": denied,
                "other_errors": other,
                "proves": (
                    "When a parent agent fans out parallel subagents against one "
                    "process-local budget, only one holds projected spend; siblings "
                    "are BudgetExceeded before provider dispatch."
                ),
                "does_not_prove": (
                    "Distributed / multi-host reservation safety. Process-local "
                    "max_budget_usd alone is not a shared cluster budget authority. "
                    "Also does not prove semantic prediction of branch cost from prompts."
                ),
                "related_example": "07_concurrent_reservation.py (same local authority; this labels the agent-fanout story)",
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
