#!/usr/bin/env python3
"""05 — Customer/feature attribution across normal and expensive retry paths.

Hermetic fake provider. No keys.

Proves:
- monitor() kwargs / use_attribution ContextVars are visible at call time
- two synthetic customers keep distinct business_subject_ref values
- one feature can show different provider-cost evidence after retries

Does not prove customer billing, invoices, revenue, or gross margin.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


class _FakeCompletions:
    def __init__(self, ledger: List[Dict[str, Any]]) -> None:
        self.calls = 0
        self._ledger = ledger

    def create(self, *args: Any, **kwargs: Any) -> Any:
        from kazenai.attribution import get_attribution

        self.calls += 1
        attr = get_attribution()
        if self.calls == 1:
            usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        else:
            usage = SimpleNamespace(prompt_tokens=800, completion_tokens=700, total_tokens=1500)
        # Approximate local cost for the summary only (not provider invoice truth).
        cost_usd = float(usage.total_tokens) * 0.0000003
        self._ledger.append(
            {
                "business_subject_ref": attr.business_subject_ref if attr else None,
                "feature_id": attr.feature_id if attr else None,
                "workflow_id": attr.workflow_id if attr else None,
                "tokens_used": usage.total_tokens,
                "estimated_provider_cost_usd": cost_usd,
                "attempt": self.calls,
            }
        )
        return SimpleNamespace(
            usage=usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content="synthetic-ok"))],
        )


class FakeOpenAI:
    def __init__(self, ledger: List[Dict[str, Any]]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(ledger))


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


def _run_customer(
    *,
    subject: str,
    feature_id: str,
    workflow_id: str,
    retries: int,
) -> Dict[str, Any]:
    from kazenai import monitor

    ledger: List[Dict[str, Any]] = []
    client = FakeOpenAI(ledger)
    monitored = monitor(
        client,
        org_id="local",
        project_id="default",
        workspace_id="default",
        agent_id="support-agent",
        max_budget_usd=5.0,
        business_subject_ref=subject,
        feature_id=feature_id,
        workflow_id=workflow_id,
    )
    for attempt in range(1, retries + 1):
        monitored.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"synthetic ticket {subject} attempt {attempt}"}],
        )
    subjects = {row["business_subject_ref"] for row in ledger}
    features = {row["feature_id"] for row in ledger}
    workflows = {row["workflow_id"] for row in ledger}
    return {
        "business_subject_ref": subject,
        "feature_id": feature_id,
        "workflow_id": workflow_id,
        "provider_calls": client.chat.completions.calls,
        "rows": ledger,
        "subjects_seen_at_call": sorted(x for x in subjects if x),
        "features_seen_at_call": sorted(x for x in features if x),
        "workflows_seen_at_call": sorted(x for x in workflows if x),
        "estimated_provider_cost_usd": round(sum(r["estimated_provider_cost_usd"] for r in ledger), 8),
    }


def main() -> int:
    _hermetic_env()
    acme = _run_customer(
        subject="cust:acme-42",
        feature_id="support_assistant",
        workflow_id="customer_support_reply.v1",
        retries=1,
    )
    globex = _run_customer(
        subject="cust:globex-7",
        feature_id="support_assistant",
        workflow_id="customer_support_reply.v1",
        retries=2,
    )

    ok = (
        acme["provider_calls"] == 1
        and globex["provider_calls"] == 2
        and acme["subjects_seen_at_call"] == ["cust:acme-42"]
        and globex["subjects_seen_at_call"] == ["cust:globex-7"]
        and acme["features_seen_at_call"] == ["support_assistant"]
        and globex["features_seen_at_call"] == ["support_assistant"]
        and acme["workflows_seen_at_call"] == ["customer_support_reply.v1"]
        and globex["estimated_provider_cost_usd"] > acme["estimated_provider_cost_usd"]
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "customers": [acme, globex],
                "proves": (
                    "Attribution ContextVars from monitor() kwargs survive to the provider "
                    "call site, so the same AI feature can be inspected per synthetic customer "
                    "with different retry cost evidence."
                ),
                "does_not_prove": (
                    "Customer billing, invoicing, revenue, or gross-margin accounting. "
                    "Estimated costs here are local synthetic projections, not provider invoices."
                ),
                "synthetic": True,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
