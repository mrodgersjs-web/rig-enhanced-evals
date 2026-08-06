"""Independent Verifier — re-checks ProofPackets sealed by the Evaluator.

The Verifier never re-runs metric logic and never trusts the `passed`
field on its face. It recomputes the HMAC-SHA256 signature over the
packet's own recorded fields (case_id, metric, score, passed, evidence,
timestamp) using the shared RIG_PROOF_SECRET and compares it, byte for
byte, against the signature the Evaluator stored at seal time. Any
post-hoc edit to a packet — a score bumped up, a `passed` flag flipped,
evidence quietly rewritten — breaks the signature and is caught here.

This is the "proof" and "gate" layers of L8: nothing downstream may
treat an eval result as real until it has passed through this module.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from src.evaluator import ProofPacket


class Verifier:
    def __init__(self, secret: Optional[str] = None):
        self.secret = secret

    def verify_packet(self, packet: ProofPacket) -> bool:
        return packet.verify(secret=self.secret)

    def verify_file(self, path: "str | Path") -> dict:
        data = json.loads(Path(path).read_text())
        packet = ProofPacket.from_dict(data)
        valid = self.verify_packet(packet)
        return {
            "path": str(path),
            "case_id": packet.case_id,
            "metric": packet.metric,
            "passed": packet.passed,
            "valid_signature": valid,
        }

    def verify_directory(self, directory: "str | Path") -> dict:
        directory = Path(directory)
        files = sorted(directory.glob("*.json")) if directory.exists() else []
        reports = [self.verify_file(f) for f in files]
        invalid = [r for r in reports if not r["valid_signature"]]
        return {
            "directory": str(directory),
            "total": len(reports),
            "valid": len(reports) - len(invalid),
            "invalid": invalid,
            "reports": reports,
        }

    def detect_tamper(self, packet: ProofPacket, **overrides) -> bool:
        """True if applying `overrides` to a sealed packet is caught by verify().

        Used to prove the signature actually binds to the packet's content
        rather than being a decorative field nobody checks.
        """
        tampered = ProofPacket(**{**packet.to_dict(), **overrides})
        return not self.verify_packet(tampered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RIG ProofPackets")
    parser.add_argument("target", help="a proof packet JSON file, or a directory of them")
    args = parser.parse_args()

    verifier = Verifier()
    target = Path(args.target)

    if target.is_dir():
        report = verifier.verify_directory(target)
        print(json.dumps(report, indent=2))
        ok = report["total"] > 0 and not report["invalid"]
    elif target.exists():
        report = verifier.verify_file(target)
        print(json.dumps(report, indent=2))
        ok = report["valid_signature"]
    else:
        print(json.dumps({"error": f"no such path: {target}"}, indent=2))
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
