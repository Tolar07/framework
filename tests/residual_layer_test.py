"""Residual layer + reliability + selection tests (ported from closing_edge).

Run: PYTHONIOENCODING=utf-8 py -3.12 tests/residual_layer_test.py
or: python -m pytest tests/residual_layer_test.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from engine.residual_layer import (
    fit_residual, calibrate, _logit, _sigmoid, ResidualFit,
    RESIDUAL_MIN_SAMPLE, RESIDUAL_KAPPA
)
from engine.reliability import (
    reliability_map, is_deployable_in_bin,
    deployable_bins, RELIABILITY_TOL, RELIABILITY_MIN_LEGS
)

_results = []
_fails = 0


def check(name, cond, detail=""):
    global _fails
    if not cond:
        _fails += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    _results.append((name, cond))


def main():
    # ============================================================
    # LOGIT helpers
    # ============================================================
    check("logit(sigmoid(x)) = x", abs(_logit(_sigmoid(1.5)) - 1.5) < 1e-6)
    check("sigmoid(logit(p)) = p", abs(_sigmoid(_logit(0.3)) - 0.3) < 1e-6)
    check("logit clamps", _logit(0.0) < -10 and _logit(1.0) > 10)

    # ============================================================
    # Residual layer: away-overconfidence case (the documented fix)
    # ============================================================
    # Synthetic data where model claims p=0.39 (logit=-0.447) but market says 0.30 (logit=-0.847)
    # True hit rate is 0.30 (market is right). The residual should shrink p_cal toward market.
    p_model_true = 0.39
    p_market_true = 0.30
    u = _logit(p_model_true) - _logit(p_market_true)  # +0.40 disagreement
    # Fitted params (a=0.05, g=0.25, b=0.90) from the plan:
    a, g, b = 0.05, 0.25, 0.90
    z = a + g * u + b * _logit(p_market_true)
    p_cal = _sigmoid(z)
    # Should shrink from 0.39 toward 0.30
    check("away shrink: p_cal between market and model",
          p_market_true < p_cal < p_model_true, f"p_cal={p_cal:.4f}")
    check("away shrink: edge reduced", p_cal - p_market_true < p_model_true - p_market_true)

    # ============================================================
    # fit_residual: inactive below min_sample
    # ============================================================
    small = [(0.4, 0.3, 0), (0.5, 0.4, 1)]
    check("inactive below 200", fit_residual("test", small) is None)

    # ============================================================
    # fit_residual: recovers market-only under (a=0, g=0, b=1)
    # ============================================================
    rng = np.random.default_rng(42)
    pairs = []
    for p_m in np.linspace(0.1, 0.9, 9):
        for _ in range(50):
            hit = 1 if rng.random() < p_m else 0
            pairs.append((p_m, p_m, hit))  # p_model == p_market
    fit = fit_residual("test", pairs, min_sample=100, kappa=20)
    check("recovers market-only: active", fit is not None and fit.active)
    check("recovers market-only: a≈0", abs(fit.a) < 0.2, f"a={fit.a:.3f}")
    check("recovers market-only: g≈0", abs(fit.g) < 0.2, f"g={fit.g:.3f}")
    check("recovers market-only: b≈1", abs(fit.b - 1.0) < 0.2, f"b={fit.b:.3f}")
    # calibrate returns p_market
    for p_m in [0.2, 0.5, 0.8]:
        p_c = calibrate(fit, p_m, p_m)
        check(f"calibrate returns p_market ({p_m})", abs(p_c - p_m) < 0.02, f"p_c={p_c:.4f}")

    # ============================================================
    # fit_residual: earn-your-keep rejects noise-only slope
    # ============================================================
    # p_model is pure noise (uncorrelated with hit), p_market is calibrated.
    pairs2 = []
    for p_m in np.linspace(0.1, 0.9, 9):
        for _ in range(50):
            hit = 1 if rng.random() < p_m else 0
            p_model_noise = rng.random() * 0.6 + 0.2  # noise in [0.2, 0.8]
            pairs2.append((p_model_noise, p_m, hit))
    fit2 = fit_residual("test", pairs2, min_sample=100, kappa=20)
    check("noise-only slope rejected", fit2 is None or not fit2.active)

    # ============================================================
    # Reliability: calibrated source -> deployable bins
    # ============================================================
    rng2 = np.random.default_rng(123)
    pairs_cal = []
    for p in np.linspace(0.1, 0.9, 9):
        for _ in range(200):
            hit = 1 if rng2.random() < p else 0
            pairs_cal.append((p, hit))
    stats = reliability_map(pairs_cal)
    deployable_cal = [s for s in stats if s.deployable]
    check("calibrated source: most bins deployable", len(deployable_cal) >= 7)
    for s in deployable_cal:
        check(f"bin {s.lo:.2f}-{s.hi:.2f} residual within tol",
              abs(s.residual) <= max(RELIABILITY_TOL, 2 * s.se))

    # ============================================================
    # Reliability: overconfident source -> refused bins
    # ============================================================
    pairs_over = []
    for p in np.linspace(0.1, 0.9, 9):
        true_p = p - 0.05
        for _ in range(200):
            hit = 1 if rng2.random() < true_p else 0
            pairs_over.append((p, hit))
    stats2 = reliability_map(pairs_over)
    deployable_over = [s for s in stats2 if s.deployable]
    check("overconfident: fewer deployable bins", len(deployable_over) < len(deployable_cal))

    # ============================================================
    # Reliability: deployable_bins per league
    # ============================================================
    trailing = {"1X2_HOME/Premier League": pairs_cal}
    bins = deployable_bins("1X2_HOME", "Premier League", trailing)
    check("deployable_bins returns ranges", len(bins) >= 7)

    # ============================================================
    # is_deployable_in_bin: no trailing data -> deployable (no evidence of miscalibration)
    # ============================================================
    trailing_bad = {}  # no data at all
    check("no trailing -> deployable (no evidence)", is_deployable_in_bin(0.55, "1X2_HOME", "Premier League", trailing_bad))

    print(f"\n{len(_results) - _fails}/{len(_results)} passed")
    sys.exit(1 if _fails else 0)


if __name__ == "__main__":
    main()