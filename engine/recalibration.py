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

  BELOW THIS: PLATT SCALING (Phase 3.1) — the curve version. Where the nudge
  above shifts every estimate on a market by ONE constant, Platt fits a
  logistic map on the settled-prediction record (raw model_prob -> outcome)
  so confidence miscalibrated at some points of the range but not others can
  be corrected curve-by-curve. Same gates: evidence-minimum, shrunk to
  identity, bounded, no feedback loop. Inert until the record exists.

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

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

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
        clv_drift = _clamp(
            float(r.get("mean_clv_pct") or 0.0) * CLV_SCALE, -MAX_ADJUSTMENT, MAX_ADJUSTMENT
        )
        delta = (RESIDUAL_WEIGHT * residual + CLV_WEIGHT * clv_drift) * _weight(n)
        delta = _clamp(delta, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
        if abs(delta) >= 0.005:  # sub-half-point adjustments are noise
            out[r["market"]] = round(delta, 4)
    return out


def shadow_adjustments(rows: list[dict]) -> dict[str, float]:
    """The WOULD-BE adjustment for every market with ANY settled evidence —
    including markets below MIN_LEGS. NEVER applied: this is the shadow trace,
    so the Architect can watch the signal build honestly while the engine stays
    inert. Markets with zero legs are absent; the same bound applies."""
    out: dict[str, float] = {}
    for r in rows:
        n = int(r.get("n") or 0)
        if n < 1:
            continue  # no evidence at all -> nothing to trace
        residual = float(r.get("mean_hit") or 0.0) - float(r.get("mean_model_prob") or 0.0)
        clv_drift = _clamp(
            float(r.get("mean_clv_pct") or 0.0) * CLV_SCALE, -MAX_ADJUSTMENT, MAX_ADJUSTMENT
        )
        delta = (RESIDUAL_WEIGHT * residual + CLV_WEIGHT * clv_drift) * _weight(n)
        delta = _clamp(delta, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
        if abs(delta) >= 0.005:  # same noise floor as the applied path
            out[r["market"]] = round(delta, 4)
    return out


def apply(model_prob: float, delta: float | None) -> float:
    """Apply a per-market adjustment to a model probability for EV. delta=None
    (or the market having no entry) is a no-op. The result stays inside
    [0.02, 0.98] — never a certainty, never a dead lock."""
    if not delta:
        return model_prob
    return _clamp(model_prob + delta, 0.02, 0.98)


# ---------------------------------------------------------------------------
# PLATT SCALING — the curve-based recalibration (Phase 3.1).
#
# The nudge above is a FLAT adjustment: one constant per market, applied
# uniformly to every estimate. Platt scaling (Platt, 2000) is the curve
# version: it fits a logistic map
#
#       p_cal = sigmoid(a + b * logit(p_raw))
#
# on the model's OWN settled predictions (raw probability -> actual outcome),
# so it can correct confidence that is miscalibrated DIFFERENTLY at different
# points of the range — over-confident at 0.60 but fine at 0.75, say. A flat
# nudge cannot express that; a slope/intercept on the logit scale can.
#
# DATA: the brain's `predictions` table already stores every rated prediction's
# raw model_prob and, once the match settles, its hit. That is exactly the
# (p, y) pair Platt needs — no new logging required. The same record the daily
# run keeps for honesty becomes the calibration signal (Brain.platt_evidence).
#
# HONESTY — same rules as the flat nudge, applied to the curve:
#   - EVIDENCE-GATED: a market needs PLATT_MIN_LEGS settled predictions before
#     ANY curve is exposed; apply_platt() is identity below the gate.
#   - SHRUNK TO IDENTITY: the fit is L2-regularised toward b=1, a=0 with
#     strength ~ 1/n. Thin samples stay (near) identity even before the gate,
#     so the curve can never manufacture a confident opinion from a handful of
#     games — and, because it is continuous in n, there is no cliff at the
#     gate where a fit suddenly snaps into existence.
#   - MONOTONE: b is bounded strictly positive. The calibration can compress
#     or stretch the model's scale but never INVERT it — more raw confidence
#     always means more calibrated confidence.
#   - BOUNDED: calibrated output is clamped to [0.02, 0.98] like everything
#     else — never a certainty, never a dead lock.
#   - PROVEN OUT-OF-SAMPLE: a curve is only APPLIED if it beats the identity
#     model on data it was not fitted on (2-fold CV Brier, see
#     _holds_up_out_of_sample). A slope that only fits its own training noise
#     — a well-calibrated market that happens to fit b=1.2 by chance — is
#     rejected rather than applied.
#   - NO FEEDBACK LOOP: the ledger keeps the RAW model_prob; only the EV
#     decision is priced on the calibrated number. What is calibrated against
#     is never the calibration's own output.
# ---------------------------------------------------------------------------

# A market needs this many SETTLED predictions (model_prob + outcome) before a
# calibration curve exists at all. Higher than MIN_LEGS deliberately: a flat
# nudge needs 15 legs to shift a mean, but a two-parameter curve needs a
# steadier sample to estimate a slope on.
PLATT_MIN_LEGS = 30
# Bounds for (a, b) on the logit scale. a is the intercept (logit shift); b
# the slope (logit stretch/compress). b stays strictly positive so the map is
# monotone — a negative b would turn the model's opinion upside down.
PLATT_BOUNDS: tuple[tuple[float, float], tuple[float, float]] = ((-10.0, 10.0), (0.1, 10.0))
# Regularisation scale: penalty = PLATT_SHRINK / n * (a^2 + (b-1)^2). At the
# gate (30 legs) this pulls a mis-fit slope about a quarter of the way back to
# identity; by 300 legs the data owns the curve.
PLATT_SHRINK = 8.0
# Output clamp — the same never-certainty floor/ceiling as apply().
CALIBRATE_CLAMP = (0.02, 0.98)


def _logit(p: float) -> float:
    """Log-odds of a probability, clipped so the log is always finite. A raw
    model output of exactly 0.0 or 1.0 (which the engine never emits, but a
    defender should not trust) is moved just off the boundary rather than
    producing inf."""
    p = _clamp(p, 1e-4, 1.0 - 1e-4)
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    """Numerically stable logistic: computes exp(z) only when z is not
    positive-large, avoiding overflow on the happy path."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _sigmoid_vec(z: np.ndarray) -> np.ndarray:
    """Vectorised logistic for the fit's analytic gradient. z is clipped so
    exp never overflows — at |z| > 50 the sigmoid is 0.0 or 1.0 to 20+ dp,
    so the clip is numerically free."""
    z = np.clip(z, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class PlattScaler:
    """One market's fitted calibration curve: p_cal = sigmoid(a + b*logit(p)).

    `n` is the settled-prediction count the curve was fit on and `n_pos` the
    hits among them — reported so the Architect can see how much evidence each
    curve rests on. A scaler is only ever APPLIED once n >= PLATT_MIN_LEGS
    (apply_platt enforces this); below the gate it exists for the shadow trace.
    """

    a: float = 0.0
    b: float = 1.0
    n: int = 0
    n_pos: int = 0
    market: str = ""

    def calibrate(self, p: float) -> float:
        """Map a raw model probability through the fitted curve, clamped to
        CALIBRATE_CLAMP. Identity (a=0, b=1) returns p unchanged."""
        if self.n < PLATT_MIN_LEGS:
            return p  # not enough evidence for a curve — untouched
        return _clamp(_sigmoid(self.a + self.b * _logit(p)), *CALIBRATE_CLAMP)

    def delta(self, p: float) -> float:
        """The adjustment this curve applies AT a given probability — what a
        flat nudge would call its constant, here a function of p."""
        return self.calibrate(p) - p


def fit_platt(pairs: list[tuple[float, bool]]) -> PlattScaler:
    """Fit one market's calibration curve by penalised maximum likelihood.

    `pairs` is [(model_prob, outcome)] from the settled prediction record.
    Uses Platt's target smoothing (Platt 2000, eq. 3-4) — soft labels
    (n_+ + 1)/(n_+ + 2) for hits and 1/(n_- + 2) for misses — instead of hard
    0/1, so a small or one-sided sample cannot produce infinite log-odds. The
    L2 penalty toward identity means no-data -> no-change, continuously.

    Returns a PlattScaler ALWAYS (even for zero pairs: a=b identity, n=0).
    Gating on n happens at the call sites (platt_scalers / apply_platt)."""
    n = len(pairs)
    scaler = PlattScaler(n=n)
    if n == 0:
        return scaler
    n_pos = sum(1 for _, y in pairs if y)
    scaler.n_pos = n_pos
    n_neg = n - n_pos
    # Soft targets, smoothed away from the hard 0/1 ends.
    y_pos = (n_pos + 1.0) / (n_pos + 2.0)
    y_neg = 1.0 / (n_neg + 2.0)
    xs = np.array([_logit(p) for p, _ in pairs], dtype=float)
    ys = np.array([y_pos if y else y_neg for _, y in pairs], dtype=float)
    reg = PLATT_SHRINK / n

    def loss(z: np.ndarray) -> float:
        a, b = float(z[0]), float(z[1])
        lin = a + b * xs
        # softplus(lin) computed stably, then the binomial log-loss
        # sum(softplus(lin) - t*lin) plus the identity-shrink penalty.
        softplus = np.maximum(lin, 0.0) + np.log1p(np.exp(-np.abs(lin)))
        ll = float(np.sum(softplus - ys * lin))
        return ll + reg * (a * a + (b - 1.0) * (b - 1.0))

    def grad(z: np.ndarray) -> np.ndarray:
        a, b = float(z[0]), float(z[1])
        lin = a + b * xs
        residual = _sigmoid_vec(lin) - ys
        da = float(np.sum(residual)) + 2.0 * reg * a
        db = float(np.sum(residual * xs)) + 2.0 * reg * (b - 1.0)
        return np.array([da, db])

    res = minimize(
        loss, np.array([0.0, 1.0]), jac=grad, method="L-BFGS-B",
        bounds=PLATT_BOUNDS, options={"maxiter": 200}
    )
    scaler.a, scaler.b = float(res.x[0]), float(res.x[1])
    return scaler


def _brier(pairs: list[tuple[float, bool]], a: float, b: float) -> float:
    """Mean squared error of a (a, b) calibration curve on (p, y) pairs —
    the probability score: lower is better, identity (a=0, b=1) is the
    benchmark the curve has to beat."""
    if not pairs:
        return 1.0
    total = 0.0
    for p, y in pairs:
        c = _clamp(_sigmoid(a + b * _logit(p)), *CALIBRATE_CLAMP)
        total += (c - (1.0 if y else 0.0)) ** 2
    return total / len(pairs)


def _holds_up_out_of_sample(pairs: list[tuple[float, bool]]) -> bool:
    """Does the fitted curve beat the identity model on data it was NOT fitted
    on? 2-fold cross-validation: fit on one alternating half, score the other,
    then swap. A well-calibrated market's fit can drift to b=1.2 by chance on
    300 samples — such a curve does NOT transfer to held-out data, so it must
    not be applied (it would manufacture a nudge the evidence never earned).
    A genuinely miscalibrated market (b far from 1) improves held-out Brier by
    tens of points, far past the 2pp margin this uses as the floor."""
    evens, odds = pairs[::2], pairs[1::2]
    improvement = 0.0
    for train, test in ((evens, odds), (odds, evens)):
        st = fit_platt(train)
        improvement += _brier(test, 0.0, 1.0) - _brier(test, st.a, st.b)
    return improvement / 2.0 > 0.02


def platt_scalers(evidence: dict[str, list[tuple[float, bool]]]) -> dict[str, PlattScaler]:
    """{market: fitted curve} for markets that clear PLATT_MIN_LEGS AND whose
    curve beats the identity model out-of-sample (2-fold CV Brier) — the
    applied set. Markets below the gate get NO entry; callers treat an absent
    key as "no calibration" (same convention as adjustments_for)."""
    out: dict[str, PlattScaler] = {}
    for market, pairs in evidence.items():
        if len(pairs) < PLATT_MIN_LEGS:
            continue  # NO DATA — PENDING: thin sample never shapes a curve
        s = fit_platt(pairs)
        if _holds_up_out_of_sample(pairs):
            out[market] = s  # the curve earns its keep on held-out data
    return out


def shadow_platt_scalers(evidence: dict[str, list[tuple[float, bool]]]) -> dict[str, PlattScaler]:
    """The WOULD-BE curve for every market with ANY settled evidence —
    including markets below PLATT_MIN_LEGS. NEVER applied (the shadow trace,
    so the Architect watches the signal build while the engine stays inert).
    Identity fits (n=0) are absent."""
    out: dict[str, PlattScaler] = {}
    for market, pairs in evidence.items():
        if len(pairs) < 1:
            continue
        out[market] = fit_platt(pairs)
    return out


def apply_platt(model_prob: float, scaler: PlattScaler | None) -> float:
    """Map a raw model probability through a market's calibration curve for EV.
    scaler=None (or the market having no curve, or the curve being below the
    gate) is a no-op — returns model_prob unchanged."""
    if scaler is None:
        return model_prob
    return scaler.calibrate(model_prob)
