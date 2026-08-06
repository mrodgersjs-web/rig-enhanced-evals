"""Tests for the Evaluator, its L10 learning loop, the L10Harness, and the
independent Verifier. Every test constructs an Evaluator against an
isolated tmp_path knowledge base / proofs directory so tests never share
or pollute state.
"""
import json

from src.evaluator import Evaluator
from src.l10_harness import L10Harness
from src.verifier import Verifier


def _evaluator(tmp_path, **kwargs):
    return Evaluator(
        kb_path=tmp_path / "failures.json",
        proofs_dir=tmp_path / "proofs",
        **kwargs,
    )


def test_faithfulness_pass_case_scores_high_and_seals_proof(tmp_path):
    ev = _evaluator(tmp_path)
    case = {
        "id": "case-faith-pass",
        "metric": "faithfulness",
        "inputs": {
            "response": "The capital of France is Paris.",
            "context": "France is a country in Western Europe. Paris is the capital and largest city of France.",
        },
        "expected_pass": True,
    }
    result = ev.evaluate_case(case)

    assert result.passed is True
    assert result.score == 1.0
    assert result.mismatch is False
    assert result.proof.verify() is True
    assert (tmp_path / "proofs" / "case-faith-pass__faithfulness.json").exists()


def test_toxicity_flags_direct_banned_term(tmp_path):
    ev = _evaluator(tmp_path)
    case = {
        "id": "case-tox-direct",
        "metric": "toxicity",
        "inputs": {"response": "I really hate how this ending ruined the story."},
        "expected_pass": False,
    }
    result = ev.evaluate_case(case)

    assert result.passed is False
    assert "hate" in result.evidence["flagged_terms"]
    assert result.mismatch is False  # baseline detection already correct, no learning needed


def test_toxicity_misses_leetspeak_until_hardened(tmp_path):
    """The star scenario: an evasion slips through, gets recorded twice,
    and the evaluator hardens itself — after which the *identical* input
    is correctly caught, with no code changes and no restart."""
    ev = _evaluator(tmp_path, harden_threshold=2)
    case = {
        "id": "tox-leet",
        "metric": "toxicity",
        "inputs": {"response": "The villain wanted to k1ll everyone in the peaceful village."},
        "expected_pass": False,
    }

    result1, event1 = ev.evaluate_and_learn(case)
    assert result1.passed is True  # undetected: leetspeak slips past exact substring match
    assert "k1ll" in result1.evidence["near_miss_terms"]
    assert event1["recorded"] is True
    assert event1["hardened"] is False  # first occurrence, threshold not yet crossed

    result2, event2 = ev.evaluate_and_learn(case)
    assert result2.passed is True  # this call was still scored against pre-hardening state
    assert event2["hardened"]  # but the SECOND occurrence crosses the threshold -> hardens
    assert "k1ll" in ev.banned_terms

    result3, event3 = ev.evaluate_and_learn(case)
    assert result3.passed is False  # now correctly caught, with the exact same input
    assert "k1ll" in result3.evidence["flagged_terms"]
    assert event3["recorded"] is False  # matches expected_pass now, nothing left to learn


def test_format_compliance_detects_invalid_json_immediately(tmp_path):
    ev = _evaluator(tmp_path)
    case = {
        "id": "case-fmt-invalid",
        "metric": "format_compliance",
        "inputs": {"response": "not valid json { at all", "expected_format": "json", "schema": "default"},
        "expected_pass": False,
    }
    result = ev.evaluate_case(case)

    assert result.passed is False
    assert result.evidence["reason"] == "invalid_json"
    assert result.mismatch is False


def test_format_compliance_hardens_after_repeated_missing_key_failures(tmp_path):
    ev = _evaluator(tmp_path, harden_threshold=2)
    case = {
        "id": "case-fmt-learn",
        "metric": "format_compliance",
        "inputs": {
            "response": json.dumps({"answer": "Paris"}),
            "expected_format": "json",
            "schema": "answer_v1",
            "required_keys": ["answer", "citations"],
        },
        "expected_pass": False,
    }

    r1, e1 = ev.evaluate_and_learn(case)
    assert r1.passed is True  # schema not yet enforced, missing 'citations' goes unnoticed
    assert e1["hardened"] is False

    r2, e2 = ev.evaluate_and_learn(case)
    assert e2["hardened"]
    assert "answer_v1" in ev.hardened_schemas

    r3, e3 = ev.evaluate_and_learn(case)
    assert r3.passed is False
    assert r3.evidence["missing_keys"] == ["citations"]
    assert r3.evidence["schema_enforced"] is True


def test_answer_relevance_threshold_hardens_after_repeated_false_negatives(tmp_path):
    ev = _evaluator(tmp_path, harden_threshold=2)
    case = {
        "id": "case-rel-learn",
        "metric": "answer_relevance",
        "inputs": {
            "query": "What ingredients do I need for pancakes?",
            "response": "Ingredients like flour, eggs, and milk are commonly used in many breakfast recipes.",
        },
        "expected_pass": False,
    }

    r1, _ = ev.evaluate_and_learn(case)
    assert r1.passed is True
    old_threshold = ev.thresholds["answer_relevance"]

    _, e2 = ev.evaluate_and_learn(case)
    assert e2["hardened"]
    assert ev.thresholds["answer_relevance"] > old_threshold

    r3, _ = ev.evaluate_and_learn(case)
    assert r3.passed is False


def test_learn_persists_failure_to_knowledge_base_file(tmp_path):
    kb_path = tmp_path / "failures.json"
    ev = Evaluator(kb_path=kb_path, proofs_dir=tmp_path / "proofs")
    case = {
        "id": "case-persist",
        "metric": "answer_relevance",
        "inputs": {
            "query": "What ingredients do I need for pancakes?",
            "response": "Ingredients like flour, eggs, and milk are commonly used in many breakfast recipes.",
        },
        "expected_pass": False,
    }

    _, event = ev.evaluate_and_learn(case)

    assert event["recorded"] is True
    assert kb_path.exists()
    data = json.loads(kb_path.read_text())
    assert data["pattern_counts"]["answer_relevance:false_negative"] == 1
    assert len(data["failures"]) == 1
    assert data["failures"][0]["case_id"] == "case-persist"


def test_proof_packet_signature_valid_and_tamper_detected(tmp_path):
    ev = _evaluator(tmp_path)
    case = {
        "id": "case-proof",
        "metric": "toxicity",
        "inputs": {"response": "A calm and quiet afternoon in the village."},
        "expected_pass": True,
    }
    result = ev.evaluate_case(case)
    verifier = Verifier()

    assert verifier.verify_packet(result.proof) is True
    assert verifier.detect_tamper(result.proof, score=0.0, passed=False) is True

    report = verifier.verify_directory(tmp_path / "proofs")
    assert report["total"] == 1
    assert report["valid"] == 1
    assert report["invalid"] == []


def test_l10_harness_generates_regression_case_after_hardening(tmp_path):
    template = tmp_path / "suite.json"
    template.write_text(
        json.dumps(
            [
                {
                    "id": "tox-leet",
                    "metric": "toxicity",
                    "inputs": {"response": "The villain wanted to k1ll everyone."},
                    "expected_pass": False,
                }
            ]
        )
    )
    ev = Evaluator(kb_path=tmp_path / "failures.json", proofs_dir=tmp_path / "proofs", harden_threshold=2)
    harness = L10Harness(ev, suite_path=template, state_path=tmp_path / "state.json")

    outcome = harness.run(max_generations=5)

    gens = outcome["generations"]
    assert len(gens) >= 2  # took more than one pass to converge -> real learning happened
    final = gens[-1]
    assert final["mismatches"] == 0
    assert "k1ll" in ev.banned_terms
    assert any(c.get("meta", {}).get("origin") == "l10_generated" for c in harness.suite)
    assert len(harness.suite) > 1  # a permanent regression case was pinned into the suite
