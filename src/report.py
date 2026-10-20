"""report.py - human-readable and JSON output for RunReport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from src.runner import RunReport


def write_json(report: RunReport, path: str | Path) -> None:
    """Write the RunReport as pretty-printed JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))


def to_markdown(report: RunReport) -> str:
    """Format the RunReport as a Markdown summary.

    Sections:
      - Header (datasets, totals)
      - Per-metric table
      - Mismatches (expected_pass vs actual)
      - Errors (cases that raised during evaluation)
      - Pass list (the accepted cases)
    """
    out: list[str] = []
    out.append("# Evaluation report")
    out.append("")
    out.append(f"- Datasets: {', '.join(report.dataset_paths)}")
    out.append(f"- Passed: {report.passed}/{report.total}")
    out.append(f"- Failed: {report.failed}/{report.total}")
    out.append(f"- Mismatches: {report.mismatches}")
    out.append(f"- Errors: {report.errors}")
    out.append("")

    out.append("## By metric")
    out.append("")
    if report.by_metric:
        out.append("| Metric | Total | Passed | Failed | Mismatches | Errors |")
        out.append("| :-- | --: | --: | --: | --: | --: |")
        for metric, counts in sorted(report.by_metric.items()):
            out.append(
                f"| {metric} | {counts['total']} | {counts['passed']} | "
                f"{counts['failed']} | {counts['mismatches']} | {counts['errors']} |"
            )
    else:
        out.append("(no cases)")
    out.append("")

    mismatches = [r for r in report.case_results if r.mismatch and r.error is None]
    if mismatches:
        out.append("## Mismatches (expected pass != actual)")
        out.append("")
        out.append("| Case | Metric | Expected | Actual |")
        out.append("| :-- | :-- | :-- | :-- |")
        for r in mismatches:
            actual = "pass" if r.passed else "fail"
            expected = "pass" if r.expected_pass else "fail"
            out.append(f"| {r.case_id} | {r.metric} | {expected} | {actual} |")
        out.append("")

    errors = [r for r in report.case_results if r.error is not None]
    if errors:
        out.append("## Errors")
        out.append("")
        for r in errors:
            out.append(f"- `{r.case_id}` ({r.metric}): {r.error}")
        out.append("")

    passes = [r for r in report.case_results if r.passed and r.expected_pass]
    if passes:
        out.append("## Passing cases")
        out.append("")
        for r in passes:
            out.append(f"- `{r.case_id}` ({r.metric})")
        out.append("")

    return "\n".join(out)


def write_markdown(report: RunReport, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_markdown(report))


def print_summary(report: RunReport, stream: TextIO | None = None) -> None:
    """Print a one-line summary to ``stream`` (default stdout)."""
    s = stream if stream is not None else __import__("sys").stdout
    s.write(
        f"eval: {report.passed}/{report.total} pass, "
        f"{report.failed} fail, {report.mismatches} mismatch, "
        f"{report.errors} error across {len(report.by_metric)} metric(s)\n"
    )
