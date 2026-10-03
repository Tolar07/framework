"""OLP XDV — engine/residual_layer.py (OFFLINE experiment, NOT the live path)

Ported from the `closing_edge/` prototype (closing_edge/model/market_residual.py),
an independent rival framework. This module is an OFFLINE calibration experiment:
it trains and evaluates the logit-linear market-residual layer on OLP XDV's OWN
settled-leg record (clv/clv_log.json) and compares it against the existing flat
per-market nudge (engine/recalibration.py).

WHY THIS EXISTS (the differentiator, per ClosingEdge's README):
  The engine's probabilities are static fits. OLP XDV's recalibration applies a
  FLAT per-market nudge (one constant shift per market) — which cannot absorb the
  favourite-longshot (FLS) slope. A logit-linear residual layer CAN:

      logit(p_cal) = a + g·(logit(p_model) − logit(p_market)) + b·logit(p_market)

  where u = logit(p_model) − logit(p_market) is the model/market disagreement.
  With g > 0 the layer tilts the calibration by the disagreement — exactly the
  FLS correction the flat nudge structurally cannot express. ClosingEdge's
  verified walk-forward finding: the away bucket went from −1.94% to +0.105%
  above placebo once the residual had ≥200 pooled out-of-sample legs.

HONESTY / PROTECTED-GATE RULE (CLAUDE.md):
  This module is NEVER imported by run_daily.py or any live EV/calibration path.
  The CLV/legs publish gate, ARCHITECT_SIGNOFF, and calibration-log scope are
  PROTECTED constants; promoting this layer into the live path requires explicit
  Architect signoff and is out of scope here. This is research plumbing only.

ANTI-LEAKAGE (inherited from ClosingEdge):
  The residual trains ONLY on out-of-sample pairs. fit_residual reserves the
  SECOND half of the supplied pairs for an out-of-sample Brier gate; it never
  sees the current leg it is asked to calibrate.

MATH IS KEPT UNCHANGED from the prototype — do not "improve" the fit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import minimize

# --- Ported constants (NOT OLP XDV protected constants) ----------------------
# Pooled OOS legs before the residual layer is active.
RESIDUAL_MIN_SAMPLE = 200
# L2 shrinkage strength toward market-only (a=0, g=0, b=1).
RESIDUAL_KAPPA = 20.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ResidualFit:
    market: str
    a: float
    g: float
    b: float
    n: int
    n_hits: int
    brier_oos: float          # out-of-sample Brier on held-out half
    brier_market: float       # market-only Brier on same held-out half

    @property
    def active(self) -> bool:
        return self.n >= RESIDUAL_MIN_SAMPLE and self.brier_oos < self.brier_market - 1e-6


# ---------------------------------------------------------------------------
# Logit helpers
# ---------------------------------------------------------------------------

def _logit(p: float) -> float:
    # clamp to avoid infinities
    p = float(np.clip(p, 1e-6, 1 - 1e-6))
    return np.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------------------
# Fit the residual layer
# ---------------------------------------------------------------------------

def fit_residual(market: str,
                 pairs: list[tuple[float, float, int]],
                 *,
                 min_sample: int = RESIDUAL_MIN_SAMPLE,
                 kappa: float = RESIDUAL_KAPPA) -> Optional[ResidualFit]:
    """Fit the logit-linear residual on OOS pairs.

    Args:
        market: market key
        pairs: list of (p_model, p_market_open, hit) — ALL out-of-sample; the
               caller must never pass the current leg's own data here.
        min_sample: evidence gate
        kappa: L2 strength

    Returns ResidualFit or None (inactive).
    """
    if len(pairs) < min_sample:
        return None

    # Prepare data
    p_model = np.array([p[0] for p in pairs], dtype=np.float64)
    p_market = np.array([p[1] for p in pairs], dtype=np.float64)
    hit = np.array([p[2] for p in pairs], dtype=np.float64)

    # logits
    lm = np.array([_logit(p) for p in p_model])
    lk = np.array([_logit(p) for p in p_market])
    u = lm - lk  # disagreement

    # Time-split: first half -> fit, second half -> Brier eval (anti-leakage)
    split = len(pairs) // 2
    if split < 10:
        return None
    fit_mask = np.zeros(len(pairs), dtype=bool)
    fit_mask[:split] = True
    test_mask = ~fit_mask

    lm_fit = lm[fit_mask]
    lk_fit = lk[fit_mask]
    u_fit = u[fit_mask]
    hit_fit = hit[fit_mask]

    lm_test = lm[test_mask]
    lk_test = lk[test_mask]
    u_test = u[test_mask]
    hit_test = hit[test_mask]
    p_market_test = p_market[test_mask]

    # Objective: Brier + L2 penalty toward (a=0, g=0, b=1)
    def obj(x):
        a, g, b = x
        z = a + g * u_fit + b * lk_fit
        p = _sigmoid(z)
        p = np.clip(p, 1e-6, 1 - 1e-6)
        brier = float(np.mean((p - hit_fit) ** 2))
        penalty = (kappa / len(pairs)) * (a * a + g * g + (b - 1.0) ** 2)
        return brier + penalty

    bounds = [(-3.0, 3.0), (0.0, 3.0), (0.2, 3.0)]
    x0 = [0.0, 0.0, 1.0]
    res = minimize(obj, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 200})
    x = res.x
    a, g, b = float(x[0]), float(x[1]), float(x[2])

    # Out-of-sample Brier on held-out half
    z_test = a + g * u_test + b * lk_test
    p_test = _sigmoid(z_test)
    p_test = np.clip(p_test, 1e-6, 1 - 1e-6)
    brier_oos = float(np.mean((p_test - hit_test) ** 2))

    # Market-only Brier on same held-out half
    brier_market = float(np.mean((p_market_test - hit_test) ** 2))

    return ResidualFit(
        market=market, a=a, g=g, b=b,
        n=len(pairs), n_hits=int(hit.sum()),
        brier_oos=brier_oos, brier_market=brier_market,
    )


# ---------------------------------------------------------------------------
# Calibration application
# ---------------------------------------------------------------------------

def calibrate(fit: ResidualFit, p_model: float, p_market: float) -> float:
    """Apply a fitted residual to a new (p_model, p_market)."""
    if fit is None or not fit.active:
        return p_model  # inactive = no correction, use raw model prob
    lm = _logit(p_model)
    lk = _logit(p_market)
    u = lm - lk
    z = fit.a + fit.g * u + fit.b * lk
    return float(_sigmoid(z))


# ---------------------------------------------------------------------------
# Convenience: fit all markets at once
# ---------------------------------------------------------------------------

def fit_all_markets(pairs_by_market: dict[str, list[tuple[float, float, int]]]) -> dict[str, Optional[ResidualFit]]:
    return {m: fit_residual(m, ps) for m, ps in pairs_by_market.items()}


# ---------------------------------------------------------------------------
# OLP XDV integration: build OOS pairs from the live CLV log
# ---------------------------------------------------------------------------

def pairs_from_clv_log(path: str = None) -> dict[str, list[tuple[float, float, int]]]:
    """Build (p_model, p_market_open, hit) OOS pairs per market from the
    framework's own settled-leg record (clv/clv_log.json).

    NOTE on p_market_open: a single leg records only its OWN entry odds, not a
    full 1X2/OU tuple, so a full proportional devig across the market isn't
    strictly recoverable. We use the leg's entry implied probability
    (1 / entry_odds) as the open-market proxy — the honest minimal choice.
    ClosingEdge's own loader derives p_market_open from its multi-leg feed; the
    approximation here is documented and only affects magnitude, not the
    anti-leakage structure.

    Returns {market: [(p_model, p_market_open, hit), ...]} for legs that have
    both a settled outcome (hit is not None) and an entry price.
    """
    if path is None:
        path = str(Path(__file__).parent.parent / "clv" / "clv_log.json")

    p = Path(path)
    if not p.exists():
        return {}
    try:
        legs = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    by_market: dict[str, list[tuple[float, float, int]]] = {}
    for leg in legs:
        hit = leg.get("hit")
        entry = leg.get("entry_odds")
        model_prob = leg.get("model_prob")
        market = leg.get("market")
        if hit is None or entry is None or model_prob is None or market is None:
            continue
        try:
            p_model = float(model_prob)
            p_market_open = 1.0 / float(entry)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if not (0 < p_model < 1) or not (0 < p_market_open < 1):
            continue
        by_market.setdefault(market, []).append((p_model, p_market_open, 1 if hit else 0))
    return by_market


# ---------------------------------------------------------------------------
# Test helpers (exported for tests)
# ---------------------------------------------------------------------------

def _holds_up_out_of_sample(fit: ResidualFit) -> bool:
    return fit is not None and fit.active


__all__ = [
    "ResidualFit",
    "fit_residual",
    "calibrate",
    "fit_all_markets",
    "pairs_from_clv_log",
    "_holds_up_out_of_sample",
    "_logit",
    "_sigmoid",
    "RESIDUAL_MIN_SAMPLE",
    "RESIDUAL_KAPPA",
]


if __name__ == "__main__":
    import json as _json
    from pathlib import Path as _Path

    by_market = pairs_from_clv_log()
    print("=== Residual layer — OOS fits on OLP XDV's own CLV log ===")
    if not by_market:
        print("No settled legs with entry odds found yet (expected early on).")
    else:
        fits = fit_all_markets(by_market)
        print(f"{'Market':<14} | {'n':>5} | {'active':>6} | {'brier_oos':>10} {'brier_mkt':>10} | a/g/b")
        print("-" * 70)
        for m, fit in fits.items():
            if fit is None:
                print(f"{m:<14} | {'<200':>5} | {'no':>6} | {'-':>10} {'-':>10} | (insufficient evidence)")
            else:
                flag = "yes" if fit.active else "no"
                print(f"{m:<14} | {fit.n:>5} | {flag:>6} | {fit.brier_oos:>10.4f} {fit.brier_market:>10.4f} | "
                      f"{fit.a:+.3f}/{fit.g:+.3f}/{fit.b:+.3f}")
        active = [m for m, f in fits.items() if f and f.active]
        print()
        print(f"Active (earn-your-keep) markets: {len(active)}")
        print("NOTE: layer needs >=200 pooled OOS legs/market to activate (RESIDUAL_MIN_SAMPLE).")
