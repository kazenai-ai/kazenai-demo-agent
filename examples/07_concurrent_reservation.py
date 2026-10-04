#!/usr/bin/env python3
"""07 — Concurrent workers racing a shared local max_budget_usd authority.

Evidence tier: local process integration fixture (thread-safe Enforcement),
NOT distributed multi-host concurrency proof.

While one call holds projected spend inside the provider, sibling workers must
be denied before dispatch. Naive unbounded races are labelled as simulations.
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
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
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

    projected = _precall_projection_usd({"model": "gpt-4o"}, None)
    hold = threading.Event()
    client = FakeOpenAI(hold=hold)
    # Shared local authority: headroom for roughly one in-flight projection.
    monitor(client, agent_id="demo-concurrent", max_budget_usd=projected * 1.1)

    results: List[Optional[BaseException]] = []
    lock = threading.Lock()
    counter = itertools.count()

    def worker() -> None:
        idx = next(counter)
        err: Optional[BaseException] = None
        try:
            client.chat.completions.create(
                model="gpt-4o",
                # Distinct text avoids LoopDetected before the budget check.
                messages=[{"role": "user", "content": f"concurrent-{idx}-{time.time_ns()}"}],
            )
        except BaseException as exc:  # noqa: BLE001 - collect exact outcomes
            err = exc
        with lock:
            results.append(err)

    first = threading.Thread(target=worker, name="allowed")
    first.start()
    assert client.chat.completions.in_provider.wait(timeout=5)

    rest = [threading.Thread(target=worker, name=f"denied-{i}") for i in range(7)]
    for t in rest:
        t.start()

    # Wait until siblings have finished (denied) before releasing the holder.
    deadline = time.time() + 5
    while time.time() < deadline:
        with lock:
            if len(results) >= 7:
                break
        time.sleep(0.01)

    hold.set()
    first.join(timeout=5)
    for t in rest:
        t.join(timeout=5)

    allowed = sum(1 for r in results if r is None)
    denied = sum(1 for r in results if isinstance(r, BudgetExceeded))
    ok = allowed == 1 and denied == 7 and client.chat.completions.calls == 1

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "local_process_integration_fixture",
                "provider_calls": client.chat.completions.calls,
                "allowed": allowed,
                "denied_budget_exceeded": denied,
                "workers": len(results),
                "proves": (
                    "Thread-safe local Enforcement prevents oversubscription while one "
                    "call holds projected spend in-process."
                ),
                "does_not_prove": (
                    "Distributed / multi-host reservation safety. Process-local "
                    "max_budget_usd alone is not a shared cluster budget authority."
                ),
                "naive_race_label": "simulation_only_if_shown_separately",
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
