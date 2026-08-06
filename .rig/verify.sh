#!/usr/bin/env bash
# .rig/verify.sh — L8 verification
#
# Eight independent layers, each gating the next. A failure in any layer
# still runs the remaining layers (so a single run reports the full
# picture), but the final exit code is non-zero if ANY layer failed, and
# the sealed sign-off report records every layer's individual status.
#
#   1. syntax      - every module compiles
#   2. unit         - pytest suite passes
#   3. integration  - the L10 harness runs end to end from a clean state
#   4. eval         - the harness actually produced eval artifacts
#   5. proof        - every sealed ProofPacket independently re-verifies
#   6. gate         - ground-truth accuracy and zero mismatches clear the release bar
#   7. audit        - the knowledge base shows real hardening occurred
#   8. sign-off     - an HMAC-signed summary of all seven layers is sealed
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p .rig
STATUS_LOG=".rig/_layer_status.log"
: > "$STATUS_LOG"
FAIL=0
record() { echo "$1 $2" >> "$STATUS_LOG"; }

echo "== L8/1 syntax =="
if python3 -m py_compile src/evaluator.py src/l10_harness.py src/verifier.py; then
  record syntax pass
else
  record syntax fail; FAIL=1
fi

echo "== L8/2 unit =="
if python3 -m pytest test/ -q; then
  record unit pass
else
  record unit fail; FAIL=1
fi

echo "== L8/3 integration =="
if python3 -m src.l10_harness --reset --generations 5; then
  record integration pass
else
  record integration fail; FAIL=1
fi

echo "== L8/4 eval =="
if [ -f .rig/l10_state.json ] && [ -f .rig/failures.json ]; then
  record eval pass
else
  record eval fail; FAIL=1
fi

echo "== L8/5 proof =="
if python3 -m src.verifier .rig/proofs; then
  record proof pass
else
  record proof fail; FAIL=1
fi

echo "== L8/6 gate =="
if python3 - <<'PY'
import json
import sys

state = json.load(open(".rig/l10_state.json"))
last = state["generations"][-1]
total = last["passed"] + last["failed"]
# Gate on ground-truth accuracy (1 - mismatch rate), not raw pass rate:
# this suite intentionally contains cases whose *correct* verdict is a
# failure (toxicity/format-invalid negative cases), so raw pass-rate is
# not a meaningful release signal here.
accuracy = (total - last["mismatches"]) / total if total else 0
sys.exit(0 if (accuracy >= 0.8 and last["mismatches"] == 0) else 1)
PY
then
  record gate pass
else
  record gate fail; FAIL=1
fi

echo "== L8/7 audit =="
if python3 - <<'PY'
import json
import sys

kb = json.load(open(".rig/failures.json"))
sys.exit(0 if kb["hardening_events"] else 1)
PY
then
  record audit pass
else
  record audit fail; FAIL=1
fi

echo "== L8/8 sign-off =="
python3 - "$FAIL" "$STATUS_LOG" <<'PY'
import hashlib
import hmac
import json
import os
import sys
import time

fail = int(sys.argv[1])
log_path = sys.argv[2]

layers = []
with open(log_path) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        name, status = line.split()
        layers.append({"layer": name, "status": status})

payload = {"layers": layers, "overall": "fail" if fail else "pass", "timestamp": time.time()}
secret = os.environ.get("RIG_PROOF_SECRET", "rig-enhanced-evals-insecure-dev-secret").encode()
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
payload["signature"] = hmac.new(secret, canonical, hashlib.sha256).hexdigest()

with open(".rig/verify_report.json", "w") as fh:
    json.dump(payload, fh, indent=2)

print(json.dumps(payload, indent=2))
PY

if [ "$FAIL" -ne 0 ]; then
  echo "[verify] L8 FAILED"
  exit 1
fi
echo "[verify] L8 PASSED — report at .rig/verify_report.json"
