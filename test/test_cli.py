"""test_cli.py - argparse + end-to-end runner behavior."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.cli import main as cli_main


def test_cli_runs_dataset_and_writes_json(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([
        {"id": "p1", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": True},
        {"id": "f1", "metric": "toxicity", "inputs": {"response": "I hate this"}, "expected_pass": False},
    ]))
    out_json = tmp_path / "report.json"
    rc = cli_main([
        str(suite),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
        "--json", str(out_json),
    ])
    assert rc == 0  # both cases passed expected_pass
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data["total"] == 2
    assert data["passed"] == 1
    assert data["failed"] == 1
    assert data["mismatches"] == 0


def test_cli_exits_nonzero_on_mismatch(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([
        # evaluator says pass but expected_pass is True is consistent -> ok
        # mismatches: evaluator says fail but expected is True
        {"id": "m1", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": False},
    ]))
    rc = cli_main([
        str(suite),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
    ])
    assert rc == 1


def test_cli_exit_zero_flag_overrides_mismatch_exit(tmp_path):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([
        {"id": "m1", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": False},
    ]))
    rc = cli_main([
        str(suite),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
        "--exit-zero",
    ])
    assert rc == 0


def test_cli_invalid_dataset_exits_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not a json object or list")
    rc = cli_main([
        str(bad),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
    ])
    assert rc == 2


def test_cli_missing_required_field_exits_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"id": "x", "metric": "toxicity", "inputs": {}}))
    rc = cli_main([
        str(bad),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
    ])
    assert rc == 2


def test_cli_learn_flag_invokes_evaluate_and_learn(tmp_path, capsys):
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([
        {"id": "l1", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": True},
    ]))
    rc = cli_main([
        str(suite),
        "--kb", str(tmp_path / "kb.json"),
        "--proofs", str(tmp_path / "proofs"),
        "--learn",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "pass" in captured.out


def test_cli_module_invocation(tmp_path):
    """`python -m src.cli` from the repo root must work end-to-end."""
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps([
        {"id": "x", "metric": "toxicity", "inputs": {"response": "calm text"}, "expected_pass": True},
    ]))
    proc = subprocess.run(
        [sys.executable, "-m", "src.cli", str(suite),
         "--kb", str(tmp_path / "kb.json"),
         "--proofs", str(tmp_path / "proofs")],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert proc.returncode == 0, proc.stderr
    assert "pass" in proc.stdout
