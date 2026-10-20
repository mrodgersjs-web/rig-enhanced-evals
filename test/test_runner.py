"""test_runner.py - dataset loader, runner, and summarise tests."""

from __future__ import annotations

import json

import pytest

from src.evaluator import Evaluator
from src.runner import (
    CaseResult,
    RunReport,
    load_dataset,
    load_datasets,
    run_dataset,
    summarise,
)


# --------------------------------------------------------------------------
# load_dataset
# --------------------------------------------------------------------------


def test_load_dataset_single_object(tmp_path):
    p = tmp_path / "single.json"
    p.write_text(json.dumps({
        "id": "c1",
        "metric": "toxicity",
        "inputs": {"response": "calm text"},
        "expected_pass": True,
    }))
    cases = load_dataset(p)
    assert len(cases) == 1
    assert cases[0]["id"] == "c1"


def test_load_dataset_list(tmp_path):
    p = tmp_path / "many.json"
    p.write_text(json.dumps([
        {"id": "a", "metric": "toxicity", "inputs": {"response": "x"}, "expected_pass": True},
        {"id": "b", "metric": "toxicity", "inputs": {"response": "y"}, "expected_pass": False},
    ]))
    cases = load_dataset(p)
    assert [c["id"] for c in cases] == ["a", "b"]


def test_load_dataset_missing_required_field_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"id": "x", "metric": "toxicity", "inputs": {}}))
    with pytest.raises(ValueError, match="missing required field"):
        load_dataset(p)


def test_load_dataset_expected_pass_must_be_bool(tmp_path):
    p = tmp_path / "bad2.json"
    p.write_text(json.dumps({"id": "x", "metric": "toxicity", "inputs": {"response": "y"}, "expected_pass": "yes"}))
    with pytest.raises(ValueError, match="expected_pass"):
        load_dataset(p)


def test_load_dataset_id_must_be_nonempty_string(tmp_path):
    p = tmp_path / "bad3.json"
    p.write_text(json.dumps({"id": "", "metric": "toxicity", "inputs": {"response": "y"}, "expected_pass": True}))
    with pytest.raises(ValueError, match="id"):
        load_dataset(p)


def test_load_dataset_top_level_must_be_object_or_list(tmp_path):
    p = tmp_path / "bad4.json"
    p.write_text(json.dumps(42))
    with pytest.raises(ValueError, match="object or list"):
        load_dataset(p)


# --------------------------------------------------------------------------
# load_datasets
# --------------------------------------------------------------------------


def test_load_datasets_concatenates(tmp_path):
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps({"id": "a", "metric": "toxicity", "inputs": {"response": "x"}, "expected_pass": True}))
    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps([{"id": "b", "metric": "toxicity", "inputs": {"response": "y"}, "expected_pass": True}]))
    out = load_datasets([p1, p2])
    assert sorted(c["id"] for c in out) == ["a", "b"]


def test_load_datasets_duplicate_id_raises(tmp_path):
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps({"id": "dup", "metric": "toxicity", "inputs": {"response": "x"}, "expected_pass": True}))
    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps({"id": "dup", "metric": "toxicity", "inputs": {"response": "y"}, "expected_pass": True}))
    with pytest.raises(ValueError, match="duplicate case id"):
        load_datasets([p1, p2])


# --------------------------------------------------------------------------
# run_dataset
# --------------------------------------------------------------------------


def _evaluator(tmp_path):
    return Evaluator(
        kb_path=tmp_path / "failures.json",
        proofs_dir=tmp_path / "proofs",
    )


def test_run_dataset_passes_and_records(tmp_path):
    ev = _evaluator(tmp_path)
    cases = [
        {"id": "p1", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": True},
        {"id": "f1", "metric": "toxicity", "inputs": {"response": "I hate this"}, "expected_pass": False},
    ]
    results = run_dataset(ev, cases)
    assert [r.case_id for r in results] == ["p1", "f1"]
    assert results[0].passed is True
    assert results[1].passed is False
    assert all(r.error is None for r in results)


def test_run_dataset_captures_errors(tmp_path):
    ev = _evaluator(tmp_path)
    cases = [
        {"id": "ok", "metric": "toxicity", "inputs": {"response": "calm"}, "expected_pass": True},
        {"id": "boom", "metric": "unknown_metric", "inputs": {"response": "x"}, "expected_pass": True},
    ]
    results = run_dataset(ev, cases)
    # First case passes; second is unknown metric -> the evaluator raises -> captured
    assert results[0].error is None
    assert results[1].error is not None


# --------------------------------------------------------------------------
# summarise
# --------------------------------------------------------------------------


def test_summarise_counts_by_metric(tmp_path):
    results = [
        CaseResult(case_id="a", metric="toxicity", passed=True, expected_pass=True, score=1.0, mismatch=False),
        CaseResult(case_id="b", metric="toxicity", passed=False, expected_pass=False, score=0.0, mismatch=False),
        CaseResult(case_id="c", metric="faithfulness", passed=False, expected_pass=True, score=0.0, mismatch=True),
        CaseResult(case_id="d", metric="faithfulness", passed=False, expected_pass=False, score=0.0, mismatch=False, error="BoomError: x"),
    ]
    rep = summarise(results, dataset_paths=["x.json"])
    assert rep.total == 4
    assert rep.passed == 1
    assert rep.failed == 2
    assert rep.mismatches == 1
    assert rep.errors == 1
    assert rep.by_metric["toxicity"] == {"total": 2, "passed": 1, "failed": 1, "mismatches": 0, "errors": 0}
    assert rep.by_metric["faithfulness"] == {"total": 2, "passed": 0, "failed": 1, "mismatches": 1, "errors": 1}
    assert isinstance(rep, RunReport)


def test_summarise_to_dict_is_json_safe(tmp_path):
    results = [CaseResult(case_id="a", metric="toxicity", passed=True, expected_pass=True, score=1.0, mismatch=False)]
    rep = summarise(results, dataset_paths=["x.json"])
    d = rep.to_dict()
    json.dumps(d)  # must not raise
    assert d["total"] == 1
    assert d["case_results"][0]["case_id"] == "a"
