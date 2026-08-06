"""L10 self-evolving test harness.

Runs the Evaluator against a growing test suite. Every case that
disagrees with its own `expected_pass` ground truth is recorded to the
Evaluator's knowledge base. Once a specific failure PATTERN repeats
`harden_threshold` times, the Evaluator hardens itself (extends its
banned-term list, starts enforcing a JSON schema, or raises a
similarity threshold — see `Evaluator._harden`), and the harness pins a
permanent regression case into the suite so that exact failure can
never silently resurface.

This is a real fixed-point loop, not a scripted demo: each generation
re-evaluates the *entire* suite with whatever state the evaluator
currently holds, and the loop only stops once a generation produces
zero ground-truth mismatches and generates no new regression cases.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import time
from pathlib import Path

from src.evaluator import Evaluator, EvalResult


class L10Harness:
    def __init__(
        self,
        evaluator: Evaluator,
        suite_path: "str | Path",
        state_path: "str | Path" = ".rig/l10_state.json",
    ) -> None:
        self.evaluator = evaluator
        self.suite_path = Path(suite_path)
        self.state_path = Path(state_path)
        self.suite: list = self._load_suite()
        self.state: dict = self._load_state()

    # -- persistence ---------------------------------------------------------
    def _load_suite(self) -> list:
        return json.loads(self.suite_path.read_text())

    def _save_suite(self) -> None:
        self.suite_path.write_text(json.dumps(self.suite, indent=2))

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except json.JSONDecodeError:
                pass
        return {"generations": []}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2))

    # -- core loop -------------------------------------------------------------
    def run_generation(self) -> dict:
        generation_no = len(self.state["generations"]) + 1
        events = []
        results: "list[EvalResult]" = []

        for case in list(self.suite):
            result, event = self.evaluator.evaluate_and_learn(case)
            results.append(result)
            if event.get("recorded"):
                events.append({"case_id": case["id"], **event})

        generated = self._generate_cases_from_hardening(events, generation_no)
        self.suite.extend(generated)
        self._save_suite()

        summary = {
            "generation": generation_no,
            "timestamp": time.time(),
            "total_cases": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "mismatches": sum(1 for r in results if r.mismatch),
            "hardening_events": [e for e in events if e.get("hardened")],
            "generated_case_ids": [c["id"] for c in generated],
            "banned_terms": sorted(self.evaluator.banned_terms),
            "hardened_schemas": sorted(self.evaluator.hardened_schemas),
            "thresholds": dict(self.evaluator.thresholds),
        }
        self.state["generations"].append(summary)
        self._save_state()
        return {"summary": summary, "results": results}

    def _generate_cases_from_hardening(self, events: list, generation_no: int) -> list:
        """Pin a permanent regression case for every pattern that just hardened."""
        existing_ids = {c["id"] for c in self.suite}
        generated = []
        for event in events:
            if not event.get("hardened"):
                continue
            source = next((c for c in self.suite if c["id"] == event["case_id"]), None)
            if source is None:
                continue
            new_id = f"{source['id']}::l10-gen{generation_no}"
            if new_id in existing_ids:
                continue
            regression = copy.deepcopy(source)
            regression["id"] = new_id
            regression["meta"] = {
                **regression.get("meta", {}),
                "origin": "l10_generated",
                "source_case": source["id"],
                "pattern_key": event["pattern_key"],
                "generation": generation_no,
            }
            generated.append(regression)
            existing_ids.add(new_id)
        return generated

    def run(self, max_generations: int = 5) -> dict:
        for _ in range(max_generations):
            gen = self.run_generation()
            summary = gen["summary"]
            if summary["mismatches"] == 0 and not summary["generated_case_ids"]:
                break
        return {"generations": self.state["generations"], "suite_size": len(self.suite)}


def _bootstrap(args) -> "tuple[Evaluator, L10Harness]":
    if args.reset:
        for path in (args.kb, args.state, args.runtime):
            p = Path(path)
            if p.exists():
                p.unlink()
        proofs = Path(args.proofs)
        if proofs.exists():
            shutil.rmtree(proofs)
    Path(args.runtime).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.template, args.runtime)
    evaluator = Evaluator(kb_path=args.kb, proofs_dir=args.proofs, harden_threshold=args.harden_threshold)
    harness = L10Harness(evaluator, suite_path=args.runtime, state_path=args.state)
    return evaluator, harness


def main() -> int:
    parser = argparse.ArgumentParser(description="L10 self-evolving eval harness")
    parser.add_argument("--template", default=".rig/fixtures/eval_suite.template.json")
    parser.add_argument("--runtime", default=".rig/fixtures/eval_suite.runtime.json")
    parser.add_argument("--state", default=".rig/l10_state.json")
    parser.add_argument("--kb", default=".rig/failures.json")
    parser.add_argument("--proofs", default=".rig/proofs")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--harden-threshold", type=int, default=2, dest="harden_threshold")
    parser.add_argument("--reset", action="store_true", help="clear all prior L10 state before running")
    args = parser.parse_args()

    evaluator, harness = _bootstrap(args)
    outcome = harness.run(max_generations=args.generations)

    for gen in outcome["generations"]:
        print(
            f"gen {gen['generation']}: {gen['passed']}/{gen['total_cases']} passed, "
            f"{gen['mismatches']} mismatches, "
            f"{len(gen['hardening_events'])} hardening events, "
            f"+{len(gen['generated_case_ids'])} generated cases"
        )

    last = outcome["generations"][-1]
    converged = last["mismatches"] == 0 and not last["generated_case_ids"]
    total_hardening = sum(len(g["hardening_events"]) for g in outcome["generations"])
    print(
        f"suite size: {outcome['suite_size']}, converged: {converged}, "
        f"total hardening events: {total_hardening}"
    )
    return 0 if converged else 1


if __name__ == "__main__":
    raise SystemExit(main())
