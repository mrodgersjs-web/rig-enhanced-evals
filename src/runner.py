"""runner.py - dataset loader and batch runner for rig-enhanced-evals.

A dataset is a JSON document: either a single case object or a list of
case objects. Each case follows the schema:

    {
      "id": "string (required, unique within the file)",
      "metric": "toxicity|faithfulness|format_compliance|answer_relevance|...",
      "inputs": { ... metric-specific ... },
      "expected_pass": true|false,
      "tags": ["optional", "list", "of", "strings"]
    }

The runner loads one or more datasets, runs every case through the
Evaluator, and returns a RunReport with per-case results and aggregate
metrics.

The runner does NOT change the Evaluator's knowledge base (no hardening,
no recording). Use ``Evaluator.evaluate_and_learn`` when you want the
learning loop. The runner is for evaluation only.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from src.evaluator import Evaluator, EvaluationResult

REQUIRED_KEYS = ("id", "metric", "inputs", "expected_pass")


@dataclass
class CaseResult:
    case_id: str
    metric: str
    passed: bool
    expected_pass: bool
    score: float
    mismatch: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class RunReport:
    dataset_paths: list[str]
    total: int
    passed: int
    failed: int
    mismatches: int
    errors: int
    by_metric: dict[str, dict[str, int]]
    case_results: list[CaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_paths": self.dataset_paths,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "mismatches": self.mismatches,
            "errors": self.errors,
            "by_metric": self.by_metric,
            "case_results": [
                {
                    "case_id": r.case_id,
                    "metric": r.metric,
                    "passed": r.passed,
                    "expected_pass": r.expected_pass,
                    "score": r.score,
                    "mismatch": r.mismatch,
                    "evidence": r.evidence,
                    "error": r.error,
                }
                for r in self.case_results
            ],
        }


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """Load a dataset file (JSON) and return a list of validated cases.

    Accepts either a single object or a list of objects. Each case must
    have id, metric, inputs, expected_pass; raises ``ValueError`` on the
    first violation.
    """
    p = Path(path)
    raw = json.loads(p.read_text())
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(f"{p}: top-level JSON must be object or list, got {type(raw).__name__}")
    out: list[dict[str, Any]] = []
    for i, case in enumerate(raw):
        if not isinstance(case, dict):
            raise ValueError(f"{p}: case #{i} is not an object")
        missing = [k for k in REQUIRED_KEYS if k not in case]
        if missing:
            raise ValueError(f"{p}: case #{i} missing required field(s): {missing}")
        if not isinstance(case["id"], str) or not case["id"]:
            raise ValueError(f"{p}: case #{i} id must be a non-empty string")
        if case["expected_pass"] not in (True, False):
            raise ValueError(f"{p}: case #{i} expected_pass must be true or false")
        out.append(case)
    return out


def load_datasets(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Load and concatenate datasets from many files. Duplicate case ids
    across files raise ``ValueError``."""
    seen: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for path in paths:
        for case in load_dataset(path):
            if case["id"] in seen:
                raise ValueError(
                    f"duplicate case id {case['id']!r} in {path} (first seen in {seen[case['id']]})"
                )
            seen[case["id"]] = str(path)
            out.append(case)
    return out


def run_dataset(evaluator: Evaluator, cases: Iterable[dict[str, Any]]) -> list[CaseResult]:
    """Run a sequence of cases through the Evaluator and collect results.

    A case that raises during evaluation is captured with ``error`` set
    and counted in ``errors`` in the final report.
    """
    results: list[CaseResult] = []
    for case in cases:
        try:
            r: EvaluationResult = evaluator.evaluate_case(case)
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
        except Exception as exc:  # noqa: BLE001 - the runner captures all errors
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
    return results


def summarise(results: list[CaseResult], dataset_paths: list[str]) -> RunReport:
    by_metric: dict[str, dict[str, int]] = {}
    for r in results:
        m = by_metric.setdefault(r.metric, {"total": 0, "passed": 0, "failed": 0, "mismatches": 0, "errors": 0})
        m["total"] += 1
        if r.error is not None:
            m["errors"] += 1
        elif r.passed:
            m["passed"] += 1
        else:
            m["failed"] += 1
        if r.mismatch:
            m["mismatches"] += 1

    return RunReport(
        dataset_paths=dataset_paths,
        total=len(results),
        passed=sum(1 for r in results if r.error is None and r.passed),
        failed=sum(1 for r in results if r.error is None and not r.passed),
        mismatches=sum(1 for r in results if r.mismatch),
        errors=sum(1 for r in results if r.error is not None),
        by_metric=by_metric,
        case_results=results,
    )


def iter_datasets(paths: Iterable[str | Path]) -> Iterator[Path]:
    for p in paths:
        yield Path(p)
