"""Regression checks for FINAL POLISH public examples 05–07."""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _run(name: str) -> None:
    path = EXAMPLES / name
    ns = runpy.run_path(str(path))
    # Scripts exit via SystemExit when executed as __main__; run_path does not.
    # Invoke main() when present.
    assert "main" in ns, f"{name} must expose main()"
    code = ns["main"]()
    assert code == 0, f"{name} failed with exit {code}"


def test_example_05_customer_feature_attribution() -> None:
    _run("05_customer_feature_attribution.py")


def test_example_06_streaming_lifecycle() -> None:
    _run("06_streaming_lifecycle.py")


def test_example_07_concurrent_reservation() -> None:
    _run("07_concurrent_reservation.py")
