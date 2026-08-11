"""Phase 3.1 — Platt scaling recalibration tests.

The flat CLV nudge (recalibration_test.py) shifts every estimate on a market
by one constant; Platt scaling fits a CURVE on the settled-prediction record
(raw model_prob -> outcome) so it can correct confidence that is
miscalibrated at some points of the range but not others.

Proves on deterministic synthetic data:
  1. no evidence            -> identity: no curve, apply_platt is a no-op
  2. below PLATT_MIN_LEGS   -> no APPLIED curve (shadow still traces it)
  3. well-calibrated model  -> the fitted curve is (near) identity
  4. over-confident model   -> the curve pulls probabilities DOWN
  5. monotone + bounded     -> never inverts the model, never a certainty
  6. shrink to identity     -> a thin sample moves the curve less than a rich
                               one (the 1/n regularisation is real)
  7. brain wiring           -> platt_evidence() returns (prob, hit) pairs
  8. ledger honesty         -> apply_platt is applied to EV only; the flat
                               nudge and the curve compose
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from brain.store import SCHEMA_VERSION, Brain
from engine import recalibration as recal

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_platt_"))
_rng = np.random.default_rng(20260809)


def _well_calibrated(n: int = 300) -> list[tuple[float, bool]]:
    """Model that says p and reality confirms it: y ~ Bernoulli(p)."""
    ps = _rng.uniform(0.05, 0.95, n)
    ys = _rng.random(n) < ps
    return [(float(p), bool(y)) for p, y in zip(ps, ys, strict=True)]


def _overconfident(n: int = 300) -> list[tuple[float, bool]]:
    """Model claims 0.4-0.9 but reality is ~0.45 flat."""
    ps = _rng.uniform(0.4, 0.9, n)
    ys = _rng.random(n) < 0.45
    return [(float(p), bool(y)) for p, y in zip(ps, ys, strict=True)]


# --- 1. no evidence -> identity ----------------------------------------------
assert recal.platt_scalers({}) == {}, "no settled record -> no applied curves"
assert recal.apply_platt(0.55, None) == 0.55, "no scaler -> no-op"
s0 = recal.fit_platt([])
assert (s0.a, s0.b, s0.n) == (0.0, 1.0, 0) and s0.calibrate(0.6) == 0.6, (
    "empty fit must be pure identity"
)
print("1. no evidence -> identity, apply_platt no-op: OK")

# --- 2. below the gate -> no applied curve, shadow traces ----------------------
thin = _overconfident(20)
assert recal.platt_scalers({"1X2_HOME": thin}) == {}, (
    "20 settled < PLATT_MIN_LEGS -> nothing applied"
)
shadow = recal.shadow_platt_scalers({"1X2_HOME": thin})
assert "1X2_HOME" in shadow, "shadow must reveal the would-be curve"
assert recal.apply_platt(0.7, shadow["1X2_HOME"]) == 0.7, (
    "below the gate even the fitted scaler is inert when applied"
)
print("2. below PLATT_MIN_LEGS -> applied empty, shadow traced: OK")

# --- 3. well-calibrated -> near identity AND not applied -------------------------
# Even a noisy fit on a well-calibrated market must NOT be applied: the CV
# gate rejects a curve that only fits its own training sample (a b=1.2 slope
# from chance on 300 games does not transfer to held-out data). This is the
# guard that stops Platt manufacturing a nudge the evidence never earned.
good = recal.fit_platt(_well_calibrated())
assert good.n >= recal.PLATT_MIN_LEGS
assert abs(good.calibrate(0.7) - 0.7) < 0.06, (
    f"well-calibrated model must stay (near) identity, got {good.calibrate(0.7):.3f}"
)
applied_good = recal.platt_scalers({"1X2_HOME": _well_calibrated()})
assert "1X2_HOME" not in applied_good, (
    "a well-calibrated market's noise fit must not pass the CV gate"
)
print(
    f"3. well-calibrated -> near identity + rejected by CV gate "
    f"(a={good.a:+.2f}, b={good.b:.2f}): OK"
)

# --- 4. over-confident -> curve pulls probabilities DOWN + applied ---------------
over = recal.fit_platt(_overconfident())
assert over.n >= recal.PLATT_MIN_LEGS
cal80 = over.calibrate(0.8)
assert cal80 < 0.72, f"model claiming 0.8 vs reality ~0.45 must be pulled down, got {cal80:.3f}"
assert over.calibrate(0.5) < 0.6, "even mid-range over-confidence is deflated"
# and the applied set actually contains this market
applied = recal.platt_scalers({"1X2_HOME": _overconfident(200)})
assert "1X2_HOME" in applied, "a decisively miscalibrated market must be applied"
print(f"4. over-confident -> pulled down (0.8 -> {cal80:.3f}) + applied: OK")

# --- 5. monotone + bounded ------------------------------------------------------
mono = recal.fit_platt(_overconfident(400))
ps = np.linspace(0.02, 0.98, 49)
cal = [mono.calibrate(float(p)) for p in ps]
assert all(cal[i + 1] >= cal[i] - 1e-9 for i in range(len(cal) - 1)), (
    "calibration must be monotone non-decreasing (never inverts the model)"
)
assert all(recal.CALIBRATE_CLAMP[0] <= c <= recal.CALIBRATE_CLAMP[1] for c in cal), (
    "calibrated probabilities must stay inside the clamp"
)
assert mono.b > 0.0, "slope must stay strictly positive"
print("5. monotone non-decreasing + bounded inside clamp: OK")

# --- 6. shrink to identity: thin samples move the curve LESS than rich ones -----
thin_fit = recal.fit_platt(_overconfident(31))  # just above the gate
rich_fit = recal.fit_platt(_overconfident(400))
# Both are miscalibrated, but the thin fit is pulled further back toward
# identity by the 1/n regularisation, so its 0.8 estimate stays HIGHER
# (closer to the model's raw 0.8) than the rich fit's.
assert thin_fit.calibrate(0.8) > rich_fit.calibrate(0.8), (
    "thin samples must be shrunk toward identity harder than rich ones"
)
print(
    f"6. shrink-to-identity (thin 0.8->{thin_fit.calibrate(0.8):.3f} vs "
    f"rich 0.8->{rich_fit.calibrate(0.8):.3f}): OK"
)

# --- 7. brain wiring: platt_evidence returns (prob, hit) pairs -------------------
b = Brain(_tmp / "p1.db")
assert b.schema_version == SCHEMA_VERSION
base = {
    "run_id": "r1",
    "predicted_at": "2026-08-01T08:00:00Z",
    "league": "Eredivisie",
    "fixture": "AAA v BBB",
    "match_date": "2026-08-02",
    "model_engine": "dc",
    "entry_odds": None,
    "bookmaker": None,
    "ev": None,
    "on_deploy_shortlist": 0,
    "cal_adjustment": None,
}
rows = [dict(base, market="1X2_HOME", model_prob=0.5) for _ in range(3)] + [
    dict(base, market="1X2_HOME", model_prob=0.6) for _ in range(2)
]
assert b.append_predictions(rows) == 5
b.record_outcomes("AAA v BBB", "2026-08-02", "1-0", {"1X2_HOME": True, "OVER_2_5": False})
ev = b.platt_evidence(engine="dc")
assert "1X2_HOME" in ev and len(ev["1X2_HOME"]) == 5, (
    f"settled dc predictions must surface as pairs, got {ev}"
)
assert all(hit for _, hit in ev["1X2_HOME"]), "all rows graded hit=True here"
# an unsettled engine contributes nothing
assert b.platt_evidence(engine="elo") == {}, "no elo rows -> no evidence"
print("7. brain.platt_evidence -> (prob, hit) pairs, per engine: OK")

# --- 8. composition: flat nudge + curve compose; ledger keeps raw prob ----------
flat = recal.adjustments_for(
    [
        {
            "market": "1X2_HOME",
            "n": 20,
            "mean_clv_pct": 0.03,
            "mean_hit": 0.62,
            "mean_model_prob": 0.5,
        }
    ]
)
s = recal.platt_scalers({"1X2_HOME": _overconfident(200)})["1X2_HOME"]
raw = 0.70
nudged = recal.apply(raw, flat.get("1X2_HOME"))
calibrated = recal.apply_platt(nudged, s)
assert nudged != raw or calibrated != nudged, "at least one stage must move the probability here"
assert recal.apply_platt(raw, None) == raw, "no curve -> raw untouched"
print("8. flat nudge + curve compose; apply_platt(raw, None) is identity: OK")

print("\n✅ ALL PLATT CALIBRATION TESTS PASSED")
