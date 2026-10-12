"""Framework examples 14-20 run offline (real SDK/framework objects, fake transport)."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])  # never --live in tests
    monkeypatch.delenv("KAZENAI_DEMO_LIVE", raising=False)
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def _run(name: str) -> None:
    ns = runpy.run_path(str(EXAMPLES / name))
    assert ns["main"]() == 0, f"{name} did not report ok"


@pytest.mark.parametrize("name,needs", [
    ("14_shared_budget_two_providers.py", ["openai", "anthropic"]),
    ("15_langchain_chat_models.py", ["langchain_openai", "langchain_anthropic"]),
    ("16_langchain_multi_model_chain.py", ["langchain_openai", "langchain_anthropic"]),
    ("17_langgraph_multi_provider_workflow.py", ["langgraph", "langchain_openai", "langchain_anthropic"]),
    ("18_langgraph_approval_checkpoint.py", ["langgraph.checkpoint.sqlite", "langchain_openai", "langchain_anthropic"]),
    ("20_litellm_proxy.py", ["openai"]),
])
def test_framework_example(name, needs):
    for module in needs:
        pytest.importorskip(module)
    _run(name)


def test_crewai_example():
    pytest.importorskip("crewai")
    pytest.importorskip("anthropic")
    _run("19_crewai_crew.py")
