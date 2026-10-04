#!/usr/bin/env python3
"""10 — Sequential multi-agent workflow sharing one budget.

Hermetic fake provider. No keys.

Story: triage → research → reply agents run in order under one workflow_id
and shared Enforcement. Budget sized for ~two projections: first two stages
dispatch, the third is BudgetExceeded before provider dispatch.

Evidence tier: hermetic fake + shared local Enforcement.
Does not prove distributed FinOps or framework orchestration (LangGraph/Crew).
"""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple


class _FakeCompletions:
    def __init__(self, ledger: List[Dict[str, Any]], agent_id: str, settle_tokens: int) -> None:
        self.calls = 0
        self._ledger = ledger
        self._agent_id = agent_id
        self._settle_tokens = settle_tokens

    def create(self, *args: Any, **kwargs: Any) -> Any:
        from kazenai.attribution import get_attribution

        self.calls += 1
        attr = get_attribution()
        self._ledger.append(
            {
                "agent_id": self._agent_id,
                "business_subject_ref": attr.business_subject_ref if attr else None,
                "feature_id": attr.feature_id if attr else None,
                "workflow_id": attr.workflow_id if attr else None,
                "attempt": self.calls,
            }
        )
        # Settle near one pre-call projection so two stages fill a 2× cap and
        # the third stage is denied before dispatch (tiny usage would not).
        tok = self._settle_tokens
        return SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=tok,
                completion_tokens=tok,
                total_tokens=tok * 2,
            ),
            choices=[SimpleNamespace(message=SimpleNamespace(content=f"ok:{self._agent_id}"))],
        )


class FakeOpenAI:
    def __init__(self, ledger: List[Dict[str, Any]], agent_id: str, settle_tokens: int) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(ledger, agent_id, settle_tokens))


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


def main() -> int:
    _hermetic_env()
    from kazenai import BudgetExceeded, Enforcement
    from kazenai.cost_engine import TokenCostEngine
    from kazenai.finops import FinOpsConfig, FinOpsController
    from kazenai.monitor import _precall_projection_usd, patch_openai
    from kazenai.sinks import MemorySink

    model = "gpt-4o-mini"
    one = float(_precall_projection_usd({"model": model}, None))
    # Headroom for two sequential stages that each settle ~one projection.
    cap = one * 2.05
    engine = TokenCostEngine()
    lo, hi = 1, 500_000
    settle_tokens = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        cost = float(engine.cost_usd(model=model, input_tokens=mid, output_tokens=mid) or 0.0)
        if cost < one:
            lo = mid + 1
        else:
            settle_tokens = mid
            hi = mid - 1
    workflow_id = "support_ticket.v1"
    subject = "cust:acme-42"

    stages: List[Tuple[str, str, str]] = [
        ("triage_agent", "ticket_triage", "Classify the ticket"),
        ("research_agent", "ticket_research", "Gather policy context"),
        ("reply_agent", "ticket_reply", "Draft the customer reply"),
    ]

    enforcement = Enforcement(max_cost_usd=cap)
    finops = FinOpsController(
        cfg=FinOpsConfig(budget_usd=cap, soft_pause_pct=100.0, loop_anomaly_threshold=1.0)
    )
    sink = MemorySink(max_events=2000)
    ledger: List[Dict[str, Any]] = []
    outcomes: List[Dict[str, Any]] = []
    provider_calls = 0

    for agent_id, feature_id, prompt in stages:
        client = FakeOpenAI(ledger, agent_id, settle_tokens)
        patch_openai(
            client,
            org_id="local",
            project_id="default",
            workspace_id="default",
            agent_id=agent_id,
            enforcement=enforcement,
            finops=finops,
            event_sink=sink,
            certified_surface=True,
            business_subject_ref=subject,
            feature_id=feature_id,
            workflow_id=workflow_id,
        )
        try:
            client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt} [{uuid.uuid4().hex}]",
                    }
                ],
            )
            provider_calls += client.chat.completions.calls
            outcomes.append(
                {
                    "agent_id": agent_id,
                    "feature_id": feature_id,
                    "outcome": "allowed",
                    "provider_calls": client.chat.completions.calls,
                }
            )
        except BudgetExceeded as exc:
            outcomes.append(
                {
                    "agent_id": agent_id,
                    "feature_id": feature_id,
                    "outcome": "budget_exceeded",
                    "error": str(exc),
                    "provider_calls": client.chat.completions.calls,
                }
            )
            break
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(
                {
                    "agent_id": agent_id,
                    "feature_id": feature_id,
                    "outcome": "unexpected",
                    "error": f"{type(exc).__name__}: {exc}",
                    "provider_calls": client.chat.completions.calls,
                }
            )
            break

    allowed = sum(1 for o in outcomes if o["outcome"] == "allowed")
    denied = sum(1 for o in outcomes if o["outcome"] == "budget_exceeded")
    agents_seen = [row["agent_id"] for row in ledger]
    features_seen = [row["feature_id"] for row in ledger]
    ok = (
        allowed == 2
        and denied == 1
        and provider_calls == 2
        and agents_seen == ["triage_agent", "research_agent"]
        and features_seen == ["ticket_triage", "ticket_research"]
        and all(row.get("workflow_id") == workflow_id for row in ledger)
        and all(row.get("business_subject_ref") == subject for row in ledger)
        and outcomes[-1]["agent_id"] == "reply_agent"
    )

    print(
        json.dumps(
            {
                "ok": ok,
                "evidence_tier": "hermetic_fake",
                "workflow_id": workflow_id,
                "business_subject_ref": subject,
                "max_budget_usd": cap,
                "one_projection_usd": one,
                "stages": outcomes,
                "ledger": ledger,
                "provider_calls": provider_calls,
                "proves": (
                    "Multiple agent systems can run sequentially under one workflow_id "
                    "and shared local Enforcement; later stages are denied before "
                    "dispatch once cumulative budget is exhausted."
                ),
                "does_not_prove": (
                    "LangGraph/Crew/Autogen orchestration, distributed multi-host "
                    "reservation, or prompt-complexity cost prediction."
                ),
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
