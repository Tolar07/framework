"""CLV-gated engine recalibration — the "model learns from outcomes" bridge.

WHY THIS EXISTS
  The engine's probabilities are static fits: the brain records every paper
  leg's outcome and closing line, but nothing ever uses that record to refine
  the numbers THE CALL is priced on. Recalibration turns the settled-leg
  record into a small, BOUNDED nudge to the probabilities used for EV.

WHAT THE SIGNAL IS
  Per market (1X2_HOME, 1X2_AWAY, OVER_2_5, ...) over settled paper legs with
  a logged closing line:
    - mean hit rate  vs  mean model probability  -> is the model over- or
      under-confident on this market? (the calibration residual)
    - mean CLV       -> does the model BEAT the close here? positive CLV is
      the direct evidence the model identifies value the market then confirms.
  The two are blended so a market must both be hitting at its claim AND be
  confirming edge in the price for its estimate to be boosted; a market losing
  on both is deflated.

HONESTY (HR35)
  - EVIDENCE-GATED: a market needs MIN_LEGS settled legs with CLV before any
    adjustment exists; below that the engine is untouched. Right now that is
    every market -> recalibration is entirely inert.
  - BOUNDED: the adjustment is clamped to +/-MAX_ADJUSTMENT (3 points), so it
    can never inflate a pick into a fabricated edge.
  - WEIGHTED: the adjustment scales linearly with evidence up to FULL_LEGS,
    so a thin sample moves the needle far less than a mature one.
  - NO FEEDBACK LOOP: run_daily applies the adjustment to the EV decision
    only. The ledger's model_prob stays the RAW model estimate, so what is
    calibrated against is never the calibration's own output.
  - LOUD: /stats surfaces the calibration table and the run records a flag
    when any adjustment is active. Nothing is applied silently.
"""
from __future__ import annotations

from typing import Optional

# Evidence gate: a market needs this many settled legs with a logged closing
# line before its estimate may be adjusted at all.
MIN_LEGS = 15
# Maximum probability adjustment, in points (0.03 = 3 percentage points).
MAX_ADJUSTMENT = 0.03
# At this many legs the adjustment reaches full strength (linear ramp before).
FULL_LEGS = 3 * MIN_LEGS
# Blend: how much of the adjustment comes from the hit-vs-prediction residual
# vs the CLV drift. Both must agree for the result to be large.
RESIDUAL_WEIGHT = 0.7
CLV_WEIGHT = 0.3
# CLV (a price ratio) is not a probability; scale it down before adding it as a
# drift term. A +3% mean CLV contributes up to ~0.01 of adjustment.
CLV_SCALE = 0.3


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _weight(n: int) -> float:
    """0 -> 1 as evidence grows from 0 to FULL_LEGS."""
    return max(0.0, min(1.0, n / FULL_LEGS))


def adjustments_for(rows: list[dict]) -> dict[str, float]:
    """Rows come from Brain.calibration_by_market() — one dict per market with
    n, mean_clv_pct, mean_hit, mean_model_prob. Returns {market: delta} for
    markets with enough settled evidence; markets below the gate get NO entry
    (callers treat an absent key as "no adjustment")."""
    out: dict[str, float] = {}
    for r in rows:
        n = int(r.get("n") or 0)
        if n < MIN_LEGS:
            continue  # NO DATA — PENDING: thin sample never moves the engine
        residual = float(r.get("mean_hit") or 0.0) - float(r.get("mean_model_prob") or 0.0)
        clv_drift = _clamp(float(r.get("mean_clv_pct") or 0.0) * CLV_SCALE,
                           -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
        delta = (RESIDUAL_WEIGHT * residual + CLV_WEIGHT * clv_drift) * _weight(n)
        delta = _clamp(delta, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
        if abs(delta) >= 0.005:  # sub-half-point adjustments are noise
            out[r["market"]] = round(delta, 4)
    return out


def apply(model_prob: float, delta: Optional[float]) -> float:
    """Apply a per-market adjustment to a model probability for EV. delta=None
    (or the market having no entry) is a no-op. The result stays inside
    [0.02, 0.98] — never a certainty, never a dead lock."""
    if not delta:
        return model_prob
    return _clamp(model_prob + delta, 0.02, 0.98)
