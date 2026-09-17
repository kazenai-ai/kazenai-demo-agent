# Demo Package Policy

This directory is a supported, non-product demo package (soft-frozen).

- Status: runnable demo / non-release
- Canonical replacement: see the active KazenAI stack in `../docs/CANONICAL_ARCHITECTURE.md`
- Scope: deterministic local search plus budget and loop enforcement scenarios

Keep it aligned with the public `kazenai-core` API and ensure `pytest scenarios -q`
passes before changing the demo contract.
