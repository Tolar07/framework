"""Phase 3 Gate — Architect (V7) sign-off workflow.

The Phase 3 gate requires:
  1. ≥30 Phase 2 paper legs with logged CLV
  2. Positive mean CLV across those legs
  3. Architect (V7) explicit sign-off

This module persists the signed gate record and provides a guard that is
checked before ANY capital deployment can proceed.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PAPER_PHASE  # noqa: E402
from clv.clv_logger import CLVLog, PHASE3_GATE_MIN_LEGS  # noqa: E402

GATE_FILE = Path(__file__).parent / "phase3_gate.json"


@dataclass
class GateRecord:
    """Signed Phase 3 gate record."""
    legs_with_clv: int
    gate_requirement: int
    mean_clv_pct: Optional[float]
    positive_mean_clv: bool
    gate_met: bool
    architect_signed_off: bool = False
    signed_by: str = ""
    signed_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GateRecord":
        return cls(**data)


def _load_gate() -> Optional[GateRecord]:
    if not GATE_FILE.exists():
        return None
    with open(GATE_FILE) as f:
        return GateRecord.from_dict(json.load(f))


def _save_gate(record: GateRecord) -> None:
    GATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GATE_FILE, "w") as f:
        json.dump(record.to_dict(), f, indent=2)


def evaluate_gate(log: Optional[CLVLog] = None) -> GateRecord:
    """Evaluate the current Phase 3 gate status from the CLV log."""
    log = log or CLVLog()
    status = log.phase2_status()

    # Create a gate record reflecting current state (unsigned)
    return GateRecord(
        legs_with_clv=status["legs_with_clv"],
        gate_requirement=status["gate_requirement"],
        mean_clv_pct=status["mean_clv_pct"],
        positive_mean_clv=status["positive_mean_clv"],
        gate_met=status["gate_met_pending_architect_signoff"],
        architect_signed_off=False,
        signed_by="",
        signed_at="",
        notes="Auto-evaluated from CLV log"
    )


def sign_off_gate(architect_name: str, log: Optional[CLVLog] = None) -> GateRecord:
    """Sign off the Phase 3 gate — only callable when gate is met.

    This is the Architect (V7) action. Once signed, the record persists and
    `can_deploy_capital()` will return True.
    """
    gate = evaluate_gate(log)
    if not gate.gate_met:
        raise RuntimeError(
            f"Gate not met: {gate.legs_with_clv}/{gate.gate_requirement} legs with CLV, "
            f"mean CLV = {gate.mean_clv_pct}"
        )

    gate.architect_signed_off = True
    gate.signed_by = architect_name
    gate.signed_at = datetime.now(timezone.utc).isoformat()
    gate.notes = f"Signed by {architect_name} at {gate.signed_at}"
    _save_gate(gate)
    return gate


def get_signed_gate() -> Optional[GateRecord]:
    """Return the persisted signed gate record, if any."""
    return _load_gate()


def can_deploy_capital() -> tuple[bool, str]:
    """Guard: check if capital deployment is authorized.

    Returns (authorized, reason). Called by any code path that would place
    real stake (booking bridge, live executor, etc.).
    """
    gate = get_signed_gate()
    if gate is None:
        return False, "No Phase 3 gate record — gate not evaluated or signed"
    if not gate.architect_signed_off:
        return False, "Gate evaluated but not signed off by Architect (V7)"
    return True, "Phase 3 gate signed off — capital deployment authorized"


def gate_status_for_dashboard() -> dict:
    """Build the gate status dict for the admin dashboard payload."""
    # Start with live evaluation
    gate = evaluate_gate()
    # Overlay any persisted signature
    signed = get_signed_gate()
    if signed and signed.architect_signed_off:
        gate.architect_signed_off = True
        gate.signed_by = signed.signed_by
        gate.signed_at = signed.signed_at
        gate.notes = signed.notes
    return gate.to_dict()


def revoke_sign_off(reason: str = "Revoked by Architect") -> GateRecord:
    """Revoke the Architect sign-off (emergency/admin use only).

    Returns the updated (now unsigned) gate record.
    """
    gate = evaluate_gate()
    gate.architect_signed_off = False
    gate.signed_by = ""
    gate.signed_at = ""
    gate.notes = reason
    _save_gate(gate)
    return gate


if __name__ == "__main__":
    """CLI for gate operations."""
    import argparse
    ap = argparse.ArgumentParser(description="Phase 3 Gate — Architect sign-off")
    ap.add_argument("--evaluate", action="store_true", help="Evaluate gate from CLV log")
    ap.add_argument("--status", action="store_true", help="Show persisted gate record")
    ap.add_argument("--sign-off", metavar="NAME", help="Sign off gate as Architect (V7)")
    ap.add_argument("--revoke", action="store_true", help="Revoke sign-off")
    a = ap.parse_args()

    if a.evaluate:
        gate = evaluate_gate()
        for k, v in gate.to_dict().items():
            print(f"  {k}: {v}")
    elif a.status:
        gate = get_signed_gate()
        if gate:
            for k, v in gate.to_dict().items():
                print(f"  {k}: {v}")
        else:
            print("No signed gate record found.")
    elif a.sign_off:
        gate = sign_off_gate(a.sign_off)
        print(f"✅ Gate signed off by {gate.signed_by} at {gate.signed_at}")
        for k, v in gate.to_dict().items():
            print(f"  {k}: {v}")
    elif a.revoke:
        gate = revoke_sign_off("Revoked via CLI")
        print(f"🔓 Gate revoked: {gate.notes}")
    else:
        ap.print_help()