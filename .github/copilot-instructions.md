# rig-enhanced-evals copilot instructions

## What it is
Self-evolving LLM evaluation with proof-gated results. Compares
to `deepeval` or `promptfoo`: same scoring surface
(faithfulness, relevance, toxicity, format), with an L10
self-evolving harness that mutates detection state on repeated
failure, and proof-gated results sealed into HMAC-signed
ProofPackets.

## Layout
- `src/`: `l10_harness.py`, `evaluator.py`, `runner.py`,
  `report.py`, `cli.py`, `__main__.py`.
- `test/`: pytest suite.
- `examples/sample-suite.json`: end-to-end CLI fixture.
- `.rig/smoke.sh`: L10 smoke (the harness converges).
- `.github/workflows/ci.yml`: matrix pytest (3.10-3.13).

## Setup and tests
```
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
```

The CLI entry is `python3 -m src.cli`.

## Conventions
Conventional commits. Tests for every public-code change. No
secrets (`RIG_PROOF_HMAC_KEY` is per CI run only). No machine
paths (`/Users/...`, `~/Developer/...`, `$HOME/Developer/...`).
No prices; no client names; no credential/military/personnel
claims. Banned words: unlock, empower, synergy, leverage,
disrupt, hustle, utilize, iterate, optimize. No em dashes.

## Truth rule
Every README number must come from a command you just ran.

## Coverage
The CI `test` job runs `pytest -q` first (gates the build) and
`coverage run -m pytest` as a separate step with its own
timeout-minutes so a hung coverage subprocess cannot hold the
whole job open.

## Do not touch
The `Ver` HMAC algorithm, the `ProofPacket` v1 contract, and
the L10 harness state schema.

## Done-test
`ruff check .` and `pytest -q` clean on a fresh venv; the
smoke test bash `.rig/smoke.sh` exits 0.
