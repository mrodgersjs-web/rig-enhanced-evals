# Architecture

`rig-enhanced-evals` is a self-evolving LLM evaluation harness with
proof-gated results. The Evaluator runs each case against a rule set,
seals the outcome in a signed ProofPacket, and (optionally) records
failures into a knowledge base that can harden future runs.

## Components

| Module | Role |
| :-- | :-- |
| `src/evaluator.py` | Runs cases against the rule set, seals results in ProofPackets, records failures |
| `src/l10_harness.py` | Multi-generation loop: re-runs the suite until mismatches stop |
| `src/verifier.py` | Independent verifier: checks signatures, output binding, and consistency |
| `src/runner.py` | Dataset loader, batch runner, and RunReport summariser |
| `src/report.py` | JSON, Markdown, and stdout report writers |
| `src/cli.py` | Command-line entry point (`python -m src.cli`) |

The CLI wraps the runner and the report writer. It does NOT touch the
knowledge base by default; pass `--learn` to route through
`Evaluator.evaluate_and_learn`.

## Public surface

```text
# evaluator
Evaluator(kb_path, proofs_dir, harden_threshold=2)
  .evaluate_case(case)         -> EvalResult
  .evaluate_and_learn(case)    -> (EvalResult, event_dict)
  .reset_knowledge_base()
  .banned_terms                -> set
  .hardened_schemas            -> dict
  .thresholds                  -> dict

# verifier
Verifier(key=None, key_id=None)
  .verify_packet(packet)        -> bool
  .detect_tamper(packet, score, passed) -> bool
  .verify_directory(path)        -> dict

# runner
load_dataset(path)              -> list[dict]
load_datasets(paths)            -> list[dict]
run_dataset(evaluator, cases)   -> list[CaseResult]
summarise(results, dataset_paths) -> RunReport

# report
write_json(report, path)
write_markdown(report, path)
to_markdown(report)             -> str
print_summary(report, stream=None)

# cli
python -m src.cli DATASET.json [DATASET.json ...]
```

## Dataset format

A dataset is a JSON document: either a single object or a list of
objects. Each case:

```json
{
  "id": "string (unique within the file)",
  "metric": "toxicity|faithfulness|format_compliance|answer_relevance|...",
  "inputs": { ... metric-specific ... },
  "expected_pass": true|false,
  "tags": ["optional", "list"]
}
```

`load_dataset` validates required fields and raises `ValueError` on the
first violation. `load_datasets` enforces unique IDs across files.

## Proof packet shape

Every `evaluate_case` writes a signed JSON document to
`proofs/<case-id>__<metric>.json` containing the per-check results, the
expected pass, the actual pass, the score, the mismatch flag, and a
hex HMAC-SHA256 signature. The Verifier recomputes the signature from
the canonical payload and rejects tampered packets.

## L10 learning loop

When a case's evaluator verdict disagrees with `expected_pass`, the
failure is recorded in the knowledge base. After the same pattern
appears `harden_threshold` times, the Evaluator adds the offending term
to `banned_terms` (for toxicity) or hardens the schema threshold (for
format_compliance or answer_relevance). The L10Harness drives a
multi-generation run that pinpoints hardened behaviour and writes a
permanent regression case back into the suite.

## Out of scope

- Semantic correctness of an LLM under test. The evaluator measures
  behaviour against a rule set; it does not judge the model itself.
- Cross-process coordination. The knowledge base is a single local
  JSON file; there is no locking for multi-process runs.
