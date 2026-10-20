"""test_report.py - JSON, Markdown, and stdout summary writers."""

from __future__ import annotations

import io
import json

from src.report import print_summary, to_markdown, write_json, write_markdown
from src.runner import CaseResult, RunReport


def _sample_report() -> RunReport:
    return RunReport(
        dataset_paths=["a.json", "b.json"],
        total=4,
        passed=2,
        failed=1,
        mismatches=1,
        errors=1,
        by_metric={
            "toxicity": {"total": 2, "passed": 1, "failed": 1, "mismatches": 0, "errors": 0},
            "faithfulness": {"total": 2, "passed": 1, "failed": 0, "mismatches": 1, "errors": 1},
        },
        case_results=[
            CaseResult(case_id="p1", metric="toxicity", passed=True, expected_pass=True, score=1.0, mismatch=False),
            CaseResult(case_id="f1", metric="toxicity", passed=False, expected_pass=False, score=0.0, mismatch=False),
            CaseResult(case_id="m1", metric="faithfulness", passed=False, expected_pass=True, score=0.0, mismatch=True),
            CaseResult(
                case_id="e1", metric="faithfulness", passed=False, expected_pass=False,
                score=0.0, mismatch=False, error="BoomError: nope",
            ),
        ],
    )


def test_write_json_round_trip(tmp_path):
    rep = _sample_report()
    p = tmp_path / "report.json"
    write_json(rep, p)
    data = json.loads(p.read_text())
    assert data["total"] == 4
    assert data["by_metric"]["toxicity"]["total"] == 2


def test_to_markdown_includes_sections():
    md = to_markdown(_sample_report())
    assert "# Evaluation report" in md
    assert "## By metric" in md
    assert "## Mismatches (expected pass != actual)" in md
    assert "## Errors" in md
    assert "## Passing cases" in md
    assert "| toxicity |" in md
    assert "p1" in md
    assert "BoomError: nope" in md


def test_to_markdown_handles_empty_report():
    rep = RunReport(
        dataset_paths=[],
        total=0,
        passed=0,
        failed=0,
        mismatches=0,
        errors=0,
        by_metric={},
        case_results=[],
    )
    md = to_markdown(rep)
    assert "Passed: 0/0" in md
    assert "(no cases)" in md
    assert "## Mismatches" not in md
    assert "## Errors" not in md
    assert "## Passing cases" not in md


def test_write_markdown_creates_parent_dirs(tmp_path):
    p = tmp_path / "deep" / "nested" / "report.md"
    write_markdown(_sample_report(), p)
    assert p.exists()
    assert "# Evaluation report" in p.read_text()


def test_print_summary_one_line():
    buf = io.StringIO()
    print_summary(_sample_report(), stream=buf)
    line = buf.getvalue()
    assert "4/4 pass" in line
    assert "2 metric" in line
