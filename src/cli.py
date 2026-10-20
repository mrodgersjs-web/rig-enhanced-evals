"""cli.py - command-line entry point for rig-enhanced-evals.

Usage:
    python -m src.cli DATASET.json [DATASET.json ...]
                         [--kb PATH] [--proofs PATH]
                         [--json OUT.json] [--md OUT.md]
                         [--learn] [--harden-threshold N]
                         [--exit-zero]

By default the CLI runs evaluation without hardening (no knowledge-base
updates). With --learn, every case goes through Evaluator.evaluate_and_learn
and the runner tracks hardening events.

Exit code:
    0 all cases passed expected_pass
    1 at least one mismatch (expected != actual) OR a runner error
    2 eval failed (e.g. invalid dataset)

Use --exit-zero to force a 0 exit regardless of mismatches (useful for
CI dashboards that prefer non-zero for other signals).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.evaluator import Evaluator
from src.report import print_summary, write_json, write_markdown
from src.runner import RunReport, load_datasets, run_dataset, summarise

DEFAULT_HARDEN_THRESHOLD = 2


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rig-evals",
        description="Run an evaluation suite against the rig-enhanced-evals harness.",
    )
    p.add_argument("datasets", nargs="+", help="dataset JSON files (object or list per file)")
    p.add_argument("--kb", default=None, help="path to the knowledge base JSON (default: tmp)")
    p.add_argument("--proofs", default=None, help="directory to write proof packets (default: tmp)")
    p.add_argument("--json", dest="json_out", default=None, help="write JSON report to this path")
    p.add_argument("--md", dest="md_out", default=None, help="write Markdown report to this path")
    p.add_argument(
        "--learn",
        action="store_true",
        help="run Evaluator.evaluate_and_learn (records failures, may harden)",
    )
    p.add_argument("--harden-threshold", type=int, default=DEFAULT_HARDEN_THRESHOLD)
    p.add_argument(
        "--exit-zero",
        action="store_true",
        help="always exit 0 (suppress non-zero on mismatches; for dashboards)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        cases = load_datasets(args.datasets)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"rig-evals: error loading datasets: {exc}", file=sys.stderr)
        return 2

    kb_path = Path(args.kb) if args.kb else Path("/tmp/rig-evals-failures.json")
    proofs_dir = Path(args.proofs) if args.proofs else Path("/tmp/rig-evals-proofs")
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    proofs_dir.mkdir(parents=True, exist_ok=True)

    ev = Evaluator(
        kb_path=kb_path,
        proofs_dir=proofs_dir,
        harden_threshold=args.harden_threshold,
    )

    results = []
    for case in cases:
        try:
            if args.learn:
                r, _event = ev.evaluate_and_learn(case)
            else:
                r = ev.evaluate_case(case)
        except Exception as exc:  # noqa: BLE001 - capture all errors at the CLI boundary
            from src.runner import CaseResult  # local import to avoid a top-level cycle

            results.append(
                CaseResult(
                    case_id=case["id"],
                    metric=case["metric"],
                    passed=False,
                    expected_pass=bool(case["expected_pass"]),
                    score=0.0,
                    mismatch=bool(case["expected_pass"]),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        from src.runner import CaseResult  # local import

        results.append(
            CaseResult(
                case_id=case["id"],
                metric=case["metric"],
                passed=bool(r.passed),
                expected_pass=bool(case["expected_pass"]),
                score=float(r.score),
                mismatch=bool(r.mismatch),
                evidence=dict(r.evidence),
            )
        )

    rep = RunReport(
        dataset_paths=list(args.datasets),
        total=len(results),
        passed=sum(1 for r in results if r.error is None and r.passed),
        failed=sum(1 for r in results if r.error is None and not r.passed),
        mismatches=sum(1 for r in results if r.mismatch),
        errors=sum(1 for r in results if r.error is not None),
        by_metric={},
        case_results=results,
    )
    # Fill in the per-metric breakdown from summarise
    rep = summarise(results, list(args.datasets))

    if args.json_out:
        write_json(rep, args.json_out)
    if args.md_out:
        write_markdown(rep, args.md_out)
    print_summary(rep)

    if args.exit_zero:
        return 0
    if rep.mismatches or rep.errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
