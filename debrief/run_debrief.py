"""
DEBRIEF — the bounded self-correction loop (automation blueprint 2.7).

Runs after a matchday has finished. It grades what can be graded, reports what
cannot, and writes IMPROVEMENT PROPOSALS to a review file for the Architect to
accept or reject.

THE BOUNDARY, WHICH IS THE WHOLE POINT
  This module PROPOSES. It never rewrites a hard rule, never edits the softness
  table, never touches capital logic, never adjusts a threshold. Blueprint 2.7
  allows exactly two things to move automatically — source-trust scores and
  calibration — and everything else is a proposal with an Architect decision
  attached. A framework that can quietly retune its own pass mark has no pass
  mark.

  Proposals are APPENDED, never overwritten. Yesterday's observation staying on
  the record is what makes the file an audit trail instead of a rolling summary
  that loses its own history.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from clv.clv_logger import CLVLog, compute_clv, PHASE3_GATE_MIN_LEGS
from config import PAPER_PHASE, PHASE_LABEL

HERE = Path(__file__).parent
PROPOSALS_PATH = HERE / "proposals.json"
HISTORY_PATH = HERE / "history.json"

# Measured on the 2024/25 backtest, 5 leagues, corrected engine. These are the
# bars the framework must clear, taken from the MD2 Pressure Test's RULE 3:
# "if the framework can't out-CLV those, the 43 directives are decoration."
BASELINE_CLV = {
    "always-favourite": -0.047,
    "random selection": -0.530,
    "always-over": -0.754,
}


@dataclass
class Proposal:
    date_raised: str
    category: str        # calibration | data_gap | rule_observation | thesis
    observation: str
    proposed_action: str
    # Only the Architect ever changes this. Nothing in this file acts on a
    # proposal; it exists to be read and decided on.
    status: str = "pending"


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _append(path: Path, items: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load(path)
    existing.extend(items)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def build_proposals(status: dict, ungraded: list[str],
                     today: Optional[str] = None) -> list[Proposal]:
    """Observations worth the Architect's attention. Each one names what was
    seen and what could be done — never what has already been done."""
    today = today or date.today().isoformat()
    out: list[Proposal] = []
    n, mean = status["legs_with_clv"], status["mean_clv_pct"]

    if n > 0 and mean is not None and mean < 0:
        best_name = min(BASELINE_CLV, key=lambda k: -BASELINE_CLV[k])
        best = BASELINE_CLV[best_name]
        losing_to = mean < best
        out.append(Proposal(
            date_raised=today, category="calibration",
            observation=(
                f"Mean CLV is {mean:+.3f}% across {n} logged leg(s) — the model "
                f"is losing to the closing line, not merely running cold. The "
                f"best dumb baseline ({best_name}) scored {best:+.3f}% on the "
                f"2024/25 backtest, so the model is currently "
                f"{'BEHIND that baseline' if losing_to else 'ahead of it'}."),
            proposed_action=(
                "Do not add capital. Investigate whether the selection rule adds "
                "anything over always-favourite before logging further legs "
                "against it (MD2 Pressure Test, RULE 3)."
                if losing_to else
                "Continue logging. Negative absolute CLV with a positive margin "
                "over the baseline is consistent with a small real edge that the "
                "spread still swallows."),
        ))

    if ungraded:
        out.append(Proposal(
            date_raised=today, category="data_gap",
            observation=(f"{len(ungraded)} leg(s) could not be graded "
                         f"automatically: {', '.join(ungraded[:6])}"
                         + (" ..." if len(ungraded) > 6 else "")),
            proposed_action="Extend the settlement rules to cover these markets, "
                             "or grade them by hand. They remain NO DATA — PENDING "
                             "and are scored neither way.",
        ))

    if n < PHASE3_GATE_MIN_LEGS:
        out.append(Proposal(
            date_raised=today, category="rule_observation",
            observation=(f"{n} of {PHASE3_GATE_MIN_LEGS} Phase 3 gate legs logged "
                         f"with CLV."),
            proposed_action="No rule change needed — this is expected at this "
                             "stage. Note that the MD2 Pressure Test sets its own "
                             "bar at 100+ settled picks, which is the more "
                             "defensible number: at 30 legs the standard error "
                             "cannot distinguish a real edge from zero.",
        ))
    return out


def run_debrief(log: Optional[CLVLog] = None,
                 ungraded: Optional[list[str]] = None) -> str:
    """Grade what's gradable, propose what's worth proposing, write both."""
    log = log or CLVLog()
    ungraded = ungraded or []
    today = date.today().isoformat()

    legs = [l for l in log.legs if l.phase == PAPER_PHASE]
    graded = [l for l in legs if l.hit is not None]
    with_clv = [l for l in legs if l.clv_pct is not None]
    status = log.phase2_status()

    proposals = build_proposals(status, ungraded, today)
    text = _render(today, legs, graded, with_clv, status, proposals, ungraded)

    _append(PROPOSALS_PATH, [asdict(p) for p in proposals])
    _append(HISTORY_PATH, [{"date": today, "text": text,
                            "logged_at": datetime.now(timezone.utc).isoformat()}])
    return text


def _render(today, legs, graded, with_clv, status, proposals, ungraded) -> str:
    L = [f"DEBRIEF — {today}", "=" * 52, PHASE_LABEL, ""]
    L.append(f"Paper legs logged      : {len(legs)}")
    L.append(f"Graded (result known)  : {len(graded)}")
    if graded:
        hits = sum(1 for l in graded if l.hit)
        L.append(f"Hit rate               : {hits}/{len(graded)} "
                 f"({100*hits/len(graded):.1f}%)")
    L.append(f"With closing price/CLV : {len(with_clv)}")
    if ungraded:
        L.append(f"Ungraded               : {len(ungraded)} — NO DATA — PENDING, "
                 f"scored neither way")
    L.append("")

    mean = status["mean_clv_pct"]
    L.append(f"Mean CLV: {f'{mean:+.3f}%' if mean is not None else 'NO DATA — PENDING'}")
    L.append(f"Phase 3 gate: {status['legs_with_clv']}/{status['gate_requirement']} "
             f"legs — {'MET' if status['gate_met_pending_architect_signoff'] else 'not met'} "
             f"(Architect sign-off required regardless)")
    L.append("")

    L.append("BASELINES TO BEAT (2024/25 backtest, same fixtures, no model involved):")
    for name, val in sorted(BASELINE_CLV.items(), key=lambda kv: -kv[1]):
        L.append(f"   {name:<18} {val:+.3f}%")
    L.append("   A model that cannot out-CLV the best of these is not adding "
             "anything (MD2 RULE 3).")
    L.append("")

    if proposals:
        L.append("PROPOSED — awaiting your accept/reject. Nothing here is applied:")
        for p in proposals:
            L.append(f"   [{p.category}] {p.observation}")
            L.append(f"      -> {p.proposed_action}")
        L.append("")

    L.append("HONEST EDGE LINE: an excellent informed process, NOT a demonstrated "
             "profitable edge. Only logged closing lines prove otherwise.")
    return "\n".join(L)


if __name__ == "__main__":
    print(run_debrief())
