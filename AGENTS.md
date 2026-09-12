# AGENTS.md — rig-enhanced-evals

TAC (Tactical Agentic Coding) doctrine for any agent — human-directed or
autonomous — working in this repository. This file is hierarchical
context: read it before touching `src/`, `test/`, `spec/`, or `.rig/`.

## What this repo is

A self-evolving LLM evaluation harness. The interesting property is
that `src/evaluator.py` is meant to be **imperfect on purpose** —
its default thresholds and detection rules are deliberately lenient so
the L10 loop in `src/l10_harness.py` has real failures to learn from.
**Do not "fix" the lenient defaults directly.** If you find the
evaluator missing something, that is either (a) a genuine bug — fix
it and add a regression test — or (b) exactly the kind of gap the L10
loop is designed to close through `Evaluator.learn()` /
`Evaluator._harden()`, in which case the fix belongs in the hardening
mechanism, not a hardcoded threshold bump.

## Builder ≠ Verifier

This repo enforces a hard split between the agent that builds and the
agent (or process) that verifies:

- **Builder** writes code, fixtures, tests, and specs. A Builder MUST
  NOT mark work complete based on its own read of the code.
- **Verifier** is `.rig/verify.sh` (L8, eight independent layers) plus
  `.rig/smoke.sh` (L10 smoke). Both are read-only with respect to
  intent: they run the real evaluator against the real fixture suite
  and assert on real output files (`.rig/failures.json`,
  `.rig/l10_state.json`, `.rig/proofs/*.json`). Neither script trusts
  an in-process claim; both re-derive their verdict from disk.
- A Builder's loop is: **build → run `.rig/verify.sh` → read the exit
  code and the sealed report at `.rig/verify_report.json` → fix →
  repeat.** "It should work" is never a stopping condition. A green
  `.rig/verify.sh` exit code is.
- Nothing is "done" until `.rig/verify.sh` exits 0 AND you have looked
  at `.rig/verify_report.json` yourself — the exit code and the sealed
  report must agree.

## Proof gates (non-negotiable)

Every `Evaluator.evaluate_case()` call seals an HMAC-signed
`ProofPacket` to `.rig/proofs/<case_id>__<metric>.json`. Any change
that produces an eval result without going through `evaluate_case()`
(and therefore without a sealed proof) is a doctrine violation — there
is no "quick eval" path that skips proof sealing.

`src/verifier.py`'s `Verifier` never trusts a packet's `passed` field
on its own. It recomputes the signature from the packet's own
recorded fields and compares byte-for-byte. If you add a new field to
`ProofPacket`, update `_canonical_payload()` so the signature actually
covers it — an unsigned field is not proof of anything.

## L10 discipline

The self-evolving loop's contract, enforced by `.rig/smoke.sh`:

1. A mismatch (evaluator verdict disagrees with a case's
   `expected_pass`) is recorded via `learn()`, never silently dropped.
2. A repeated pattern (`harden_threshold`, default 2 occurrences)
   mutates evaluator state — never just logs louder.
3. Every hardening event pins a **permanent regression case** into
   the running suite (`meta.origin == "l10_generated"`). Regression
   cases are never deleted; they are the receipts that the fix
   actually fixed something.
4. `L10Harness.run()` must converge (zero mismatches, no newly
   generated cases) within the configured `max_generations`. A suite
   that never converges is a signal the hardening logic itself is
   wrong — investigate `Evaluator._harden()`, don't raise
   `max_generations` to hide it.

If you add a fifth metric or a new failure category, it MUST follow
the same shape: a `_metric_<name>` method returning `(score,
evidence)`, a `_pattern_key()` branch, and a `_harden()` branch that
mutates real evaluator state. A metric with no hardening path is not
L10-compliant.

## Closed loop for any change

1. Read the relevant section of `src/evaluator.py` or
   `src/l10_harness.py` in full before editing — these files are
   small and load-bearing; partial context produces broken hardening
   logic.
2. Make the change.
3. `python3 -m pytest test/ -v` — every test must pass, not just the
   ones you touched.
4. `bash .rig/smoke.sh` — confirms the learning loop still actually
   learns (failures recorded, hardening events fired, convergence
   reached, every proof re-verifies).
5. `bash .rig/verify.sh` — the full L8 gate. Read
   `.rig/verify_report.json` and confirm `"overall": "pass"`.
6. Only then is the change reportable as complete.

## Fixture suite conventions

`.rig/fixtures/eval_suite.template.json` is the source of truth; it is
never mutated in place. `src/l10_harness.py`'s CLI copies it to
`.rig/fixtures/eval_suite.runtime.json` before running, and the
harness mutates the runtime copy as it generates regression cases.
When adding a new template case:

- Give it an `expected_pass` — cases without ground truth are never
  scored for mismatch and can't drive learning.
- If it's meant to demonstrate learning, verify the exact score by
  running the metric function directly (`python3 -c "from
  src.evaluator import Evaluator; ..."`) before committing wording —
  the token-overlap and threshold math is exact, not approximate, and
  hand-calculating it is error-prone.
- If it's a baseline pass/immediate-fail case, confirm it stays
  correct both before and after hardening (baseline cases must not
  regress once thresholds move or schemas get enforced).

## RIG lattice contract (stamped)

This repository runs the shared RIG lattice: loops in `.rig/loop.yaml`, pre-tool
hooks in `.rig/hooks/`, CI gate in `.github/workflows/rig-lattice.yml`, execution
owner routing in `.rig/work-routing.yaml` (operator standard 2026-09-11), and a
results-driven MCP server at `mcp/server.py` returning verified results only.
D85 rules apply: every outward action needs a Gate-D request + typed approval;
durable builds need four ratios >= 0.85 and a sealed proof. Done-claims need TAC
close-gate sealed evidence. Shared agent substrate lives in Supabase schema
`rig_shared` (see PROGRAM.md in rig-lattice-retrofit).
