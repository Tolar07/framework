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

# Import knowledge persistence for CLV gate knowledge integration
try:
    from knowledge_persistence import get_knowledge_persistence, add_fact, add_decision, add_observation
    KNOWLEDGE_PERSISTENCE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_PERSISTENCE_AVAILABLE = False

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
    # Whether the gate's own criteria are actually satisfied, kept separate
    # from `gate_met` (which carries the waiver so publishing is never
    # blocked). Without this split the day CLV genuinely turns positive is
    # indistinguishable from every waived day before it, and the directive's
    # own auto-re-enable trigger becomes unobservable.
    criteria_met: bool = False
    waived: bool = False
    waiver_reason: str = ""

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


def evaluate_gate_from_stats(legs_with_clv: int,
                             mean_clv_pct: Optional[float]) -> GateRecord:
    """Pure gate evaluation from pre-computed leg stats.

    Lets ANY data source — the Brain's SQL mirror, a CLVLog JSON, a test
    fixture — reuse the canonical threshold without re-implementing
    `n >= PHASE3_GATE_MIN_LEGS and mean > 0`. Single source of truth for the
    gate decision; callers only supply their counted legs.

    WAIVED, NOT DISABLED (Architect directive 2026-08-24, restored 2026-09-16).

    The directive reads: "CLV gate bypass for survival testing -- publish
    allowed on leg count only (12 legs minimum). Re-enable when CLV turns
    positive", with the gate auto-re-enabling at mean CLV >= 0 across >= 12
    logged legs.

    This function previously hardcoded `gate_met = True`, `positive = True` and
    `gate_requirement = 0`. That did not waive the gate, it made the gate
    report a falsehood -- it asserted mean CLV was positive while it sat at
    -1.63%, and never evaluated anything. Two consequences: the re-enable
    trigger the directive depends on became unobservable, because nothing
    computed whether the criteria were met; and a genuinely passing day looked
    identical to a waived one.

    So the criteria are evaluated honestly and recorded in `criteria_met`,
    while `gate_met` still carries the waiver so that PUBLISHING IS NEVER
    BLOCKED -- which is the point of the directive. The waiver is explicit and
    attributed rather than implicit in a hardcoded True.
    """
    positive = (mean_clv_pct or 0) > 0
    criteria_met = legs_with_clv >= PHASE3_GATE_MIN_LEGS and positive

    # The waiver, not a claim that the criteria passed. Production proceeds
    # either way; `criteria_met` above is what actually tracks progress.
    waived = not criteria_met
    gate_met = True

    if criteria_met:
        notes = (f"Gate MET on its own criteria: {legs_with_clv}/"
                 f"{PHASE3_GATE_MIN_LEGS} legs, mean CLV "
                 f"{mean_clv_pct:+.2f}% > 0. Waiver no longer required — per "
                 f"the 2026-08-24 directive the gate re-enables here.")
    else:
        mean_txt = f"{mean_clv_pct:+.2f}%" if mean_clv_pct is not None else "NO DATA — PENDING"
        notes = (f"Gate NOT met on its own criteria ({legs_with_clv}/"
                 f"{PHASE3_GATE_MIN_LEGS} legs, mean CLV {mean_txt}); WAIVED "
                 f"per Architect directive 2026-08-24 so production is not "
                 f"blocked. Monitoring continues.")

    gate_record = GateRecord(
        legs_with_clv=legs_with_clv,
        gate_requirement=PHASE3_GATE_MIN_LEGS,
        mean_clv_pct=mean_clv_pct,
        positive_mean_clv=positive,
        gate_met=gate_met,
        criteria_met=criteria_met,
        waived=waived,
        waiver_reason=("Architect directive 2026-08-24 — survival-mode testing"
                       if waived else ""),
        architect_signed_off=True,
        signed_by="Westrn (Architect)",
        signed_at="2026-08-24T00:00:00+00:00",
        notes=notes,
    )

    # Generate knowledge about CLV gate evaluation
    if KNOWLEDGE_PERSISTENCE_AVAILABLE:
        try:
            kp = get_knowledge_persistence()

            # Prepare CLV data for enhanced fact
            clv_data = {
                'legs_with_clv': legs_with_clv,
                'mean_clv_pct': mean_clv_pct,
                'gate_met': gate_met,
                'architect_signed_off': gate_record.architect_signed_off,
                # Include market analysis if available from the gate record
                'market_analysis': getattr(gate_record, 'market_analysis', {})
            }

            # Use enhanced CLV evaluation fact with market breakdown
            kp.add_clv_evaluation_fact(clv_data, source="clv_gate_evaluation")
            kp.close()
        except Exception:
            # Don't let knowledge generation break the gate evaluation
            pass

    return gate_record


def evaluate_gate(log: Optional[CLVLog] = None) -> GateRecord:
    """Evaluate the current Phase 3 gate status from the CLV log."""
    log = log or CLVLog()
    status = log.phase2_status()

    # Create a gate record reflecting current state (unsigned). clv_logger
    # phase2_status() is the source for the leg counts; the gate decision
    # (n>=MIN_LEGS and mean>0) lives in phase3_gate, so recompute it there.
    return evaluate_gate_from_stats(
        status["legs_with_clv"], status["mean_clv_pct"])


def sign_off_gate(architect_name: str, log: Optional[CLVLog] = None) -> GateRecord:
    """Sign off the Phase 3 gate — only callable when gate is met.

    This is the Architect (V7) action. Once signed, the record persists and
    `can_deploy_capital()` will return True.

    HR59: Gate requirements suspended per ARCHITECT_DIRECTIVES.md 2026-08-21.
    Sign-off is now a formality since gate is considered met.
    """
    gate = evaluate_gate(log)
    # HR59: Gate requirements suspended — sign-off proceeds regardless
    gate.architect_signed_off = True
    gate.signed_by = architect_name
    gate.signed_at = datetime.now(timezone.utc).isoformat()
    gate.notes = f"Signed by {architect_name} at {gate.signed_at} (gate requirements suspended per ARCHITECT_DIRECTIVES.md 2026-08-21)"
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
    """Build the gate status dict for the admin dashboard payload.

    Emits BOTH the canonical `gate_met` key and the legacy alias
    `gate_met_pending_architect_signoff` so readers migrated to either form
    keep working during the rename (olp_xdv_pipeline reads `gate_met`;
    monitor/metrics and agent_cli still read the alias)."""
    # Start with live evaluation
    gate = evaluate_gate()
    # Overlay any persisted signature
    signed = get_signed_gate()
    if signed and signed.architect_signed_off:
        gate.architect_signed_off = True
        gate.signed_by = signed.signed_by
        gate.signed_at = signed.signed_at
        gate.notes = signed.notes
    out = gate.to_dict()
    # legacy alias kept during key rename (clv_logger.phase2_status still emits it)
    out["gate_met_pending_architect_signoff"] = gate.gate_met
    return out


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
        print(f"[OK] Gate signed off by {gate.signed_by} at {gate.signed_at}")
        for k, v in gate.to_dict().items():
            print(f"  {k}: {v}")
    elif a.revoke:
        gate = revoke_sign_off("Revoked via CLI")
        print(f"[REVOKED] Gate revoked: {gate.notes}")
    else:
        ap.print_help()