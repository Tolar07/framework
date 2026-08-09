"""
HR46 — CLV Log on Lock.
A closing line must be captured and logged for every capital/paper leg.
Three capture paths: CL-LIVE (session running), CL-ARCHIVE (odds archive),
CL-PM (Polymarket, shelved).

This is the ONLY instrument that separates a real edge from a good run
(Section 13 of the master doc). Phase 3 is gated on >=30 Phase 2 legs with
logged CLV + positive mean CLV + Architect (V7) sign-off.
"""
from __future__ import annotations
import csv
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PAPER_PHASE, assert_paper_only  # noqa: E402

PHASE3_GATE_MIN_LEGS = 30

# The phase prefix backtest legs carry. Defined HERE, next to the gate that
# excludes it, rather than as a magic string in a distant module — so anyone
# reading the Phase 3 gate can see what is and isn't counted toward it.
BACKTEST_PHASE = "backtest"

# Default on-disk location. Was a POSIX absolute path ("/home/claude/...")
# which on Windows silently resolves to C:\home\claude\... — surprising, and
# it put the capital-gate ledger outside the project.
DEFAULT_LOG_PATH = Path(__file__).parent / "clv_log.json"


@dataclass
class LoggedLeg:
    leg_id: str
    date_logged: str
    league: str
    fixture: str  # "Home v Away"
    market: str   # e.g. "O1.5", "BTTS Yes", "1X2 Home"
    model_prob: float
    # KICKOFF date of the match this leg is on (ISO), as distinct from
    # date_logged. Without it, grading matched a leg only on (home, away) — and
    # since the same pairing recurs every season, a leg on a FUTURE fixture was
    # settled against LAST season's meeting of the same two clubs, inventing
    # both a result and a closing price. Appended per HR48; legs written before
    # this field existed carry None and are refused for grading.
    match_date: Optional[str] = None
    entry_odds: Optional[float] = None       # price taken at pick time (paper or capital)
    entry_capture_path: str = "CL-LIVE"      # CL-LIVE / CL-ARCHIVE / CL-PM
    closing_odds: Optional[float] = None
    closing_capture_path: Optional[str] = None
    clv_pct: Optional[float] = None          # (entry_implied_prob... see clv formula below
    ft_result: Optional[str] = None
    hit: Optional[bool] = None
    stake: Optional[float] = None            # None for Phase 2 paper legs
    phase: str = "phase2_paper"
    notes: str = ""


def implied_prob(decimal_odds: float) -> float:
    return 1.0 / decimal_odds


def compute_clv(entry_odds: float, closing_odds: float) -> float:
    """CLV as % edge vs the closing line. POSITIVE means you beat the close.

        CLV% = (entry_odds / closing_odds - 1) * 100

    You beat the close when you took a LONGER price than the market settled
    on: entry 2.10 into a 2.00 close is +5.0%. Entry 2.00 into a 2.10 close is
    -4.8% — the market moved away from you.

    SIGN CORRECTION (2026-08-03): this previously computed
    (closing/entry - 1)*100, which returned NEGATIVE for a leg that beat the
    close while its own docstring claimed positive meant beating it. Because
    phase2_status() gates Phase 3 on `mean_clv > 0`, the effect was that a
    framework consistently beating the closing line could never open the
    capital gate, while one consistently getting worse prices would. Fixed to
    the standard convention with the Architect's approval.
    """
    return round((entry_odds / closing_odds - 1) * 100, 3)


class CLVLog:
    def __init__(self, path: str | Path = DEFAULT_LOG_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.legs: list[LoggedLeg] = self._load()

    def _load(self) -> list[LoggedLeg]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            raw = json.load(f)
        return [LoggedLeg(**r) for r in raw]

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump([asdict(l) for l in self.legs], f, indent=2)

    def log_entry(self, league: str, fixture: str, market: str, model_prob: float,
                  entry_odds: Optional[float], entry_capture_path: str = "CL-LIVE",
                  phase: str = "phase2_paper", stake: Optional[float] = None,
                  match_date: Optional[str] = None) -> LoggedLeg:
        """Record a pick at pick-time. HR46: entry_odds should be captured NOW,
        not reconstructed later — if it's unavailable, pass None and it will
        show as NO DATA — PENDING on the board, never backfilled with a guess."""
        # Capital bright line, enforced on the WRITE PATH rather than in
        # commentary: below Phase 3 a stake cannot reach disk at all.
        assert_paper_only(stake, phase)
        leg = LoggedLeg(
            leg_id=f"{fixture.replace(' ', '_')}_{market.replace(' ', '_')}_{datetime.now(timezone.utc).timestamp():.0f}",
            date_logged=datetime.now(timezone.utc).isoformat(),
            league=league, fixture=fixture, market=market,
            model_prob=model_prob, entry_odds=entry_odds,
            entry_capture_path=entry_capture_path, phase=phase, stake=stake,
            match_date=match_date,
        )
        self.legs.append(leg)
        self._save()
        return leg

    def log_close(self, leg_id: str, closing_odds: float,
                  closing_capture_path: str = "CL-ARCHIVE") -> LoggedLeg:
        for leg in self.legs:
            if leg.leg_id == leg_id:
                leg.closing_odds = closing_odds
                leg.closing_capture_path = closing_capture_path
                if leg.entry_odds:
                    leg.clv_pct = compute_clv(leg.entry_odds, closing_odds)
                self._save()
                return leg
        raise KeyError(f"No leg with id {leg_id}")

    def log_batch(self, legs: list[LoggedLeg]) -> int:
        """Append many pre-built legs with a SINGLE disk write.

        log_entry/log_close each call _save(), rewriting the whole JSON — fine
        for one pick at a time, O(n^2) across the thousands of legs a backtest
        produces. Returns the number appended."""
        for leg in legs:
            assert_paper_only(leg.stake, leg.phase)
        self.legs.extend(legs)
        self._save()
        return len(legs)

    def log_result(self, leg_id: str, ft_result: str, hit: bool) -> LoggedLeg:
        for leg in self.legs:
            if leg.leg_id == leg_id:
                leg.ft_result = ft_result
                leg.hit = hit
                self._save()
                return leg
        raise KeyError(f"No leg with id {leg_id}")

    def phase2_status(self) -> dict:
        """Reports honestly against the Phase 3 gate — never rounds up."""
        # Exact match on PAPER_PHASE is what keeps backtest legs (phase
        # "backtest_<run_id>") out of the capital gate.
        legs_with_clv = [l for l in self.legs
                          if l.phase == PAPER_PHASE and l.clv_pct is not None]
        n = len(legs_with_clv)
        mean_clv = round(sum(l.clv_pct for l in legs_with_clv) / n, 3) if n else None
        gate_met = n >= PHASE3_GATE_MIN_LEGS and (mean_clv or 0) > 0
        return {
            "legs_logged_total": len(self.legs),
            "legs_with_clv": n,
            "gate_requirement": PHASE3_GATE_MIN_LEGS,
            "mean_clv_pct": mean_clv,
            "positive_mean_clv": (mean_clv or 0) > 0,
            "gate_met_pending_architect_signoff": gate_met,
            "note": "CLV logged: ZERO" if n == 0 else f"{n} legs with logged CLV",
        }

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            if not self.legs:
                return
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.legs[0]).keys()))
            writer.writeheader()
            for leg in self.legs:
                writer.writerow(asdict(leg))


# ---------------------------------------------------------------------------
# ENSEMBLE WEIGHTS (Phase 3.3) — how much each engine's opinion counts.
#
# The cross-engine consensus (engine/consensus.py) gives every opinion an equal
# vote and averages them arithmetically. That assumes all engines are equally
# good, which the settled record can test. These weights answer, per engine:
#   - does it BEAT THE CLOSE on the markets it calls?  (CLV — the plan's signal)
#   - is it well-calibrated on its own settled record? (hit vs model_prob)
# and turn the answer into a bounded multiplier on that engine's say in the
# consensus. A proven engine's opinion moves the blend more; a losing one's,
# less.
#
# HONESTY (the same rules as the recalibration, HR35):
#   - WHAT THE CLV TERM MEANS: paper legs are authored by the canonical DC pick,
#     so a leg's CLV is a MARKET-level fact, not an author's claim. It is
#     attributed to every engine that published a value opinion on that market
#     — the weight reads "this engine calls markets whose prices then move our
#     way", never "this engine wrote the leg". Stated plainly so it is never
#     mistaken for an author scorecard.
#   - EVIDENCE-GATED: an engine needs MIN_ENGINE_CAL_LEGS settled predictions
#     AND MIN_ENGINE_CLV_LEGS legs-with-CLV before either term earns it a
#     weight; below that its weight is exactly 1.0. With no settled record the
#     consensus is bit-identical to the classic equal-vote engine.
#   - BOUNDED: a weight never leaves [WEIGHT_MIN, WEIGHT_MAX] (0.5..1.5), so
#     no engine can be silenced or made omnipotent.
#   - SHRUNK: each term scales linearly with its own evidence up to a full ramp,
#     so a thin sample moves the needle far less than a mature one.
#   - NO FEEDBACK LOOP: weights shape the DISPLAY-only consensus (and its
#     brain record for learning). DC stays canonical for paper legs, CLV and
#     calibration — the weight never feeds what is logged or settled.
#   - LOUD: ensemble_weights() returns info with the flag and per-engine
#     detail; run_daily surfaces it on the board.
# ---------------------------------------------------------------------------

# Settled predictions an engine needs before its calibration earns a weight.
MIN_ENGINE_CAL_LEGS = 15
# Legs-with-CLV on its markets before the CLV term earns a weight.
MIN_ENGINE_CLV_LEGS = 5
# The weight reaches full strength at this much evidence (linear ramp before).
FULL_CAL_EVIDENCE = 45
FULL_CLV_EVIDENCE = 15
# Bounds: an engine's say in the consensus stays within +/-50% of equal.
WEIGHT_MIN = 0.5
WEIGHT_MAX = 1.5
# Blend: how much of the weight comes from calibration vs the CLV drift.
CAL_WEIGHT = 0.7
CLV_WEIGHT = 0.3
# CLV (a price ratio) is not a probability; scale it down before adding it as a
# drift term. A +2% mean CLV contributes ~0.2 toward the weight's offset.
CLV_SCALE = 0.1
# Sub-5% weight changes are noise — round them back to equal say.
WEIGHT_NOISE = 0.05


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _ramp(n: int, full: int) -> float:
    """0 -> 1 as evidence grows from 0 to `full`."""
    return max(0.0, min(1.0, n / full))


def ensemble_weights(clv_rows: list[dict], cal_rows: list[dict]
                     ) -> tuple[dict[str, float], dict]:
    """Per-engine consensus weights from historical performance.

    `clv_rows` comes from brain.engine_clv() — [{model_engine, n, mean_clv_pct}]
    on the markets each engine called. `cal_rows` from brain.engine_calibration()
    — [{model_engine, n, mean_hit, mean_model_prob}] from each engine's OWN
    settled predictions. Returns ({engine: weight}, info); every weight is 1.0
    unless the evidence provably earns a move, so an engine with no settled
    record is untouched (the caller treats a missing key as 1.0)."""
    cal = {r["model_engine"]: r for r in cal_rows}
    clv = {r["model_engine"]: r for r in clv_rows}
    engines = sorted(set(cal) | set(clv))
    weights: dict[str, float] = {}
    details: dict[str, dict] = {}
    applied = False
    for eng in engines:
        n_cal = int(cal.get(eng, {}).get("n") or 0)
        n_clv = int(clv.get(eng, {}).get("n") or 0)
        d: dict = {"n_cal": n_cal, "n_clv": n_clv}
        if n_cal < MIN_ENGINE_CAL_LEGS and n_clv < MIN_ENGINE_CLV_LEGS:
            d["reason"] = "no evidence"
            weights[eng] = 1.0
            details[eng] = d
            continue
        residual = (float(cal.get(eng, {}).get("mean_hit") or 0.0)
                    - float(cal.get(eng, {}).get("mean_model_prob") or 0.0))
        clv_drift = _clamp(
            float(clv.get(eng, {}).get("mean_clv_pct") or 0.0) * CLV_SCALE,
            -(WEIGHT_MAX - 1.0), WEIGHT_MAX - 1.0)
        delta = (CAL_WEIGHT * residual * _ramp(n_cal, FULL_CAL_EVIDENCE)
                 + CLV_WEIGHT * clv_drift * _ramp(n_clv, FULL_CLV_EVIDENCE))
        w = _clamp(1.0 + delta, WEIGHT_MIN, WEIGHT_MAX)
        if abs(w - 1.0) < WEIGHT_NOISE:
            w = 1.0
        weights[eng] = round(w, 3)
        applied = applied or w != 1.0
        d.update({"mean_clv_pct": (clv.get(eng, {}).get("mean_clv_pct")),
                  "mean_hit": cal.get(eng, {}).get("mean_hit"),
                  "mean_model_prob": cal.get(eng, {}).get("mean_model_prob"),
                  "weight": weights[eng]})
        details[eng] = d
    if applied:
        flag = ("ENSEMBLE WEIGHTS ACTIVE — " + ", ".join(
            f"{e} w={w}" for e, w in sorted(weights.items()) if w != 1.0)
            + " (CLV-gated, bounded, consensus display only)")
    else:
        flag = ("ensemble weights: no engine has enough settled evidence "
                "(cal >= " + str(MIN_ENGINE_CAL_LEGS) + " settled predictions "
                "and clv >= " + str(MIN_ENGINE_CLV_LEGS) + " legs-with-CLV) "
                "— consensus unweighted")
    return weights, {"applied": applied, "weights": weights,
                     "details": details, "flag": flag}
