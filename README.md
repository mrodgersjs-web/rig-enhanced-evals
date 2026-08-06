# RIG-Enhanced Evals

**Self-evolving LLM evaluation with proof-gated results.**

`rig-enhanced-evals` is a reference implementation of the RIG doctrine
overlay applied to LLM evaluation — the same job `deepeval` or
`promptfoo` do (score a model's response against faithfulness,
relevance, toxicity, format compliance), but with two things bolted on
that neither of those tools has:

1. **L10 self-evolving harness.** Eval metrics start lenient. When one
   gets fooled by a case whose ground truth says it should have
   failed, that mismatch is recorded. Once the *same failure pattern*
   repeats, the harness doesn't just log it again — it **mutates the
   evaluator's own detection state** (extends a banned-term list,
   turns on schema enforcement, raises a similarity threshold) and
   **permanently pins a regression case** into the suite so the exact
   failure can never silently resurface. The harness re-runs
   generation after generation until it converges: zero ground-truth
   mismatches, nothing left to learn.
2. **Proof-gated results.** Every single eval result — pass or fail —
   is sealed into an HMAC-SHA256-signed `ProofPacket` the moment it's
   produced. An independent `Verifier` re-derives the signature from
   the packet's own recorded fields and rejects anything that was
   edited after the fact. No eval result is "real" until it passes
   through the Verifier.

Nothing in this repo is scripted or faked. The three example failure
patterns baked into the fixture suite (leetspeak toxicity evasion,
missing-required-key JSON, unsupported-claim token overlap) are real
weaknesses of the corresponding heuristic metric, and the hardening
that fixes them is a real, inspectable code path — see
[`src/evaluator.py`](src/evaluator.py) `Evaluator._harden()`. Run
[`.rig/smoke.sh`](.rig/smoke.sh) yourself; it prints the exact
generation-by-generation convergence.

## Why this matters

Most eval frameworks treat a failing test as a line in a report. RIG
doctrine treats it as **unassimilated signal**: if the same category
of mistake keeps happening, the system that's supposed to catch
mistakes should get harder to fool, and the proof that it did should
be checkable by someone who wasn't in the room.

```
Evaluator.evaluate_case(case)
    -> runs one of 4 metrics against lenient default state
    -> seals an HMAC-signed ProofPacket for the result
    -> writes the proof to .rig/proofs/<case_id>__<metric>.json

Evaluator.learn(result, case)
    -> no-op if result.passed == case.expected_pass
    -> otherwise appends a failure record + bumps a pattern counter
    -> once a pattern crosses harden_threshold (default 2), mutates
       evaluator state so the SAME input now scores correctly

L10Harness.run_generation()
    -> evaluates the whole suite, calls learn() on every case
    -> for every pattern that just hardened, pins a permanent
       regression case (id "<source>::l10-gen<N>") into the suite
    -> repeats until a generation produces zero mismatches and
       generates no new cases (fixed point)
```

## Metrics

| metric | what it checks | lenient default | what hardening changes |
|---|---|---|---|
| `faithfulness` | response content words are supported by context | overlap threshold 0.3 | threshold raised toward 0.9 |
| `answer_relevance` | response content words cover the query | overlap threshold 0.3 | threshold raised toward 0.9 |
| `toxicity` | response contains no banned terms | small banned-term list, exact substring match | discovered evasions (e.g. leetspeak) are added to the banned-term list |
| `format_compliance` | response matches its declared format (`json`/`markdown`/`plain`), with required keys for JSON schemas | required-key enforcement is off per schema until hardened | schema is added to the enforced set, so its required keys are checked from then on |

Metrics are self-contained heuristics with no network calls — every
score is deterministic and reproducible, which is what makes the
learning loop something you can actually run and verify rather than
take on faith.

## Layout

```
src/evaluator.py       Evaluator, 4 metrics, ProofPacket, learn()
src/l10_harness.py     L10Harness — the self-evolving generation loop
src/verifier.py        independent Verifier — re-checks ProofPackets
.rig/fixtures/eval_suite.template.json   the 10-case reference suite
.rig/smoke.sh          L10 smoke test (fast, asserts the loop actually learned)
.rig/verify.sh         L8 verification (syntax -> ... -> sign-off)
spec/features/self-evolving-eval.feature BDD spec, 3 scenarios
test/test_evaluator.py 9 pytest cases
AGENTS.md              TAC doctrine for agents working in this repo
```

## Running it

```bash
python3 -m pytest test/ -v          # unit tests
bash .rig/smoke.sh                  # L10 smoke: prove the loop learns
bash .rig/verify.sh                 # L8: syntax -> unit -> ... -> sign-off
python3 -m src.l10_harness --reset --generations 5   # run the harness directly
python3 -m src.verifier .rig/proofs                  # re-verify every sealed proof
```

A single `bash .rig/smoke.sh` run against the reference fixtures
converges in exactly 3 generations: generation 1 surfaces 4 ground-truth
mismatches with zero hardening, generation 2 re-observes the same 4
patterns and crosses the hardening threshold on all of them (4
hardening events, 4 regression cases generated), and generation 3
re-evaluates the now-14-case suite with hardened state and converges
with zero mismatches.

## Proof secret

`ProofPacket` signatures use `RIG_PROOF_SECRET` from the environment,
falling back to an insecure development default so the repo runs
out of the box. **Set `RIG_PROOF_SECRET` in any real deployment** —
without it, anyone who can read this repo can forge a passing proof.

## License

MIT — see [`LICENSE`](LICENSE).
