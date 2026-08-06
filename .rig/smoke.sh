#!/usr/bin/env bash
# .rig/smoke.sh — L10 smoke test
#
# Runs the self-evolving evaluator against the fixture suite from a clean
# state and asserts, with real assertions against real output files, that
# the learning loop actually operated:
#   1. the evaluator was fooled at least once and recorded a mismatch
#   2. a repeated failure pattern hardened the evaluator's own state
#   3. the harness converged (zero mismatches, no more cases to generate)
#   4. every sealed ProofPacket independently re-verifies
#
# This script is designed to be re-run: it resets prior L10 state first,
# so it is deterministic across CI runs and across local re-invocations.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[smoke] running L10 harness from a clean state..."
python3 -m src.l10_harness --reset --generations 5

echo "[smoke] checking the knowledge base recorded real failures..."
python3 - <<'PY'
import json
import sys

kb = json.load(open(".rig/failures.json"))
if not kb["failures"]:
    print("[smoke] FAIL: no failures recorded — L10 never observed a mismatch")
    sys.exit(1)
if not kb["hardening_events"]:
    print("[smoke] FAIL: no hardening events — L10 recorded failures but never adapted")
    sys.exit(1)
print(f"[smoke] recorded {len(kb['failures'])} failures, {len(kb['hardening_events'])} hardening events")
for event in kb["hardening_events"]:
    print(f"[smoke]   hardened: {event['pattern_key']} -> {event['outcome']['action']}")
PY

echo "[smoke] checking the L10 harness converged over multiple generations..."
python3 - <<'PY'
import json
import sys

state = json.load(open(".rig/l10_state.json"))
gens = state["generations"]
if len(gens) < 2:
    print("[smoke] FAIL: harness converged in a single generation — no adaptation occurred")
    sys.exit(1)
last = gens[-1]
if last["mismatches"] != 0:
    print(f"[smoke] FAIL: {last['mismatches']} mismatches remain unresolved after {len(gens)} generations")
    sys.exit(1)
generated_total = sum(len(g["generated_case_ids"]) for g in gens)
print(f"[smoke] converged after {len(gens)} generations; {generated_total} regression cases generated")
PY

echo "[smoke] verifying every sealed ProofPacket..."
python3 -m src.verifier .rig/proofs

echo "[smoke] PASS: L10 learning loop verified end-to-end"
