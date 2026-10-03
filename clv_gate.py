"""clv_gate.py — the fail-closed version of the Phase 3 gate.

Per OLP_XDV_MASTER_v303.15.md Section 8: Phase 3 requires ALL THREE —
>=30 paper legs with logged CLV, AND positive mean CLV, AND V7 Architect
sign-off. Per the 14-15 Aug audit, this was reportedly failing (12/30
legs, mean -1.631%) and running only on ARCHITECT_SIGNOFF override.

This does NOT compute or estimate CLV. It reads whatever your real
logging mechanism already recorded (the CLV log CSV/JSON your engine
writes per closed leg) and checks it against the three real conditions.
If the numbers don't clear, capital is BLOCKED — full stop, no override
bypasses this function silently. ARCHITECT_SIGNOFF is a separate,
explicit human action (see check_v7_signoff below); this function never
grants it on the gate's behalf.

This is the opposite of "loosen the gate." It's "make the gate's NO
actually stop anything," which per the 14-15 Aug finding, it currently
doesn't.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MIN_LEGS_REQUIRED = 30
CLV_LOG_PATH = Path("clv_log.jsonl")
SIGNOFF_FILE = Path("V7_ARCHITECT_SIGNOFF.json")


@dataclass
class GateResult:
    passed: bool
    legs_count: int
    mean_clv: float | None
    signoff_present: bool
    reasons_blocked: list[str]


def load_clv_legs() -> list[dict]:
    """
    Reads the REAL logged legs. Each line should be a JSON object with
    at minimum {"leg_id": ..., "clv_pct": <float>}. This function does
    not compute CLV itself — it trusts whatever your engine already
    wrote, because re-deriving it here risks silently disagreeing with
    the real log for reasons that have nothing to do with capital safety.

    Returns an empty list (not an error) if the log doesn't exist yet —
    zero legs correctly fails the gate, it doesn't need to look like a
    special case.
    """
    if not CLV_LOG_PATH.exists():
        return []
    legs = []
    with open(CLV_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                legs.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a malformed line doesn't count as a valid leg
    return legs


def check_v7_signoff() -> bool:
    """
    V7 sign-off is a specific, explicit Architect action — not inferred
    from anything else. This checks for a real, dated record of it,
    the same discipline as approved_commit_gate.py: a fact you wrote,
    not a default state.
    """
    if not SIGNOFF_FILE.exists():
        return False
    try:
        data = json.loads(SIGNOFF_FILE.read_text(encoding="utf-8"))
        return bool(data.get("signed_off") is True and data.get("architect") and data.get("date"))
    except (json.JSONDecodeError, KeyError):
        return False


def evaluate_gate() -> GateResult:
    legs = load_clv_legs()
    legs_count = len(legs)

    clv_values = [l["clv_pct"] for l in legs if isinstance(l.get("clv_pct"), (int, float))]
    mean_clv = sum(clv_values) / len(clv_values) if clv_values else None

    signoff = check_v7_signoff()

    reasons_blocked = []
    if legs_count < MIN_LEGS_REQUIRED:
        reasons_blocked.append(
            f"Only {legs_count}/{MIN_LEGS_REQUIRED} legs logged with CLV — "
            f"insufficient sample."
        )
    if mean_clv is None:
        reasons_blocked.append("No valid CLV values found in the log.")
    elif mean_clv <= 0:
        reasons_blocked.append(f"Mean CLV is {mean_clv:+.3f}% — not positive.")
    if not signoff:
        reasons_blocked.append("No valid V7 Architect sign-off record found.")

    return GateResult(
        passed=len(reasons_blocked) == 0,
        legs_count=legs_count,
        mean_clv=mean_clv,
        signoff_present=signoff,
        reasons_blocked=reasons_blocked,
    )


def enforce_or_block_capital() -> None:
    """
    Call this at the actual point capital would be deployed — not as a
    status report elsewhere in the pipeline. If it doesn't pass, this
    should be the thing standing between the code and a real stake,
    not a log line someone might not read.
    """
    result = evaluate_gate()
    print("=== Phase 3 CLV Gate ===")
    print(f"Legs logged: {result.legs_count}/{MIN_LEGS_REQUIRED}")
    print(f"Mean CLV: {result.mean_clv:+.3f}%" if result.mean_clv is not None else "Mean CLV: no data")
    print(f"V7 sign-off present: {result.signoff_present}")

    if not result.passed:
        print("\n🚫 GATE FAILED — capital deployment BLOCKED. Reasons:")
        for r in result.reasons_blocked:
            print(f"  - {r}")
        raise SystemExit(1)

    print("\n✓ Gate cleared — all three conditions genuinely met.")


if __name__ == "__main__":
    enforce_or_block_capital()