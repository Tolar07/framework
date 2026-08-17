"""OLP XDV — engine/residual_compare.py (OFFLINE experiment, NOT the live path)

Read-only comparison harness: for each market present in OLP XDV's CLV log,
compute THREE calibrated traces over the settled legs:

  1. RAW       — model_prob (no correction)
  2. FLAT NUDGE — recalibration.adjustments_for(...) applied (existing OLP path)
  3. RESIDUAL   — residual_layer.calibrate(...) applied (offline port)

Reports per-market: legs, mean corrected prob vs raw, and (where a closing line
exists) a CLV-style scoreboard so the user can see whether the residual beats
the flat nudge on OLP XDV's OWN data.

HONESTY / PROTECTED-GATE RULE (CLAUDE.md):
  This module is NEVER imported by run_daily.py or any live EV/calibration path.
  The CLV/legs publish gate, ARCHITECT_SIGNOFF, and calibration-log scope are
  PROTECTED constants; promoting this layer into the live path requires explicit
  Architect signoff and is out of scope here. This is research plumbing only.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

# OLP XDV modules (read-only)
from clv.clv_logger import CLVLog, compute_clv
from engine import recalibration as recal
from engine import residual_layer as reslayer


# ---------------------------------------------------------------------------
# Market key mapping (OLP XDV keys -> residual layer canonical keys)
# OLP XDV uses market keys like "1X2_HOME", "OVER_2_5" in the CLV log.
# ClosingEdge uses "1X2_HOME", "OVER_2_5", "UNDER_2_5" etc. These align well.
# ---------------------------------------------------------------------------
_MARKET_ORDER = ["1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_2_5", "UNDER_2_5", "OVER_1_5", "UNDER_1_5"]


def _load_clv_legs() -> list[dict]:
    """Load settled legs from the CLV log that have hit + entry_odds + closing_odds."""
    log = CLVLog()
    legs = []
    for leg in log.legs:
        if leg.hit is None or leg.entry_odds is None or leg.model_prob is None:
            continue
        # Only phase2_paper legs (the framework's paper record)
        if leg.phase != "phase2_paper":
            continue
        legs.append({
            "market": leg.market,
            "league": leg.league,
            "fixture": leg.fixture,
            "model_prob": leg.model_prob,
            "entry_odds": leg.entry_odds,
            "closing_odds": leg.closing_odds,
            "hit": leg.hit,
            "clv_pct": leg.clv_pct,
        })
    return legs


def _entry_implied_prob(entry_odds: float) -> float:
    """Simple implied prob from entry odds (1/odds).
    NOTE: a single leg only knows its own price, not the full market tuple,
    so full proportional devig is not possible. This is the honest minimal choice.
    """
    return 1.0 / entry_odds


def _market_implied_from_log(legs: list[dict]) -> dict[str, float]:
    """Approximate market-open implied prob per market by averaging entry implied probs.
    This is an approximation — ClosingEdge's loader has full devigged market opens.
    """
    by_mkt: dict[str, list[float]] = defaultdict(list)
    for leg in legs:
        by_mkt[leg["market"]].append(_entry_implied_prob(leg["entry_odds"]))
    return {mkt: float(np.mean(vals)) for mkt, vals in by_mkt.items() if vals}


def _compute_clv_for_corrected(legs: list[dict], p_cal_map: dict[str, float]) -> dict[str, dict]:
    """For each market, compute CLV-style score using calibrated probability as the 'entry'."""
    # Map from market -> list of CLV% where we have a closing line
    by_mkt: dict[str, list[float]] = defaultdict(list)
    for leg in legs:
        mkt = leg["market"]
        if leg["closing_odds"] is None:
            continue
        p_cal = p_cal_map.get(mkt, leg["model_prob"])
        if p_cal is None or p_cal <= 0:
            continue
        # Simulated entry odds from calibrated prob
        entry_odds_cal = 1.0 / p_cal
        clv = compute_clv(entry_odds_cal, leg["closing_odds"])
        by_mkt[mkt].append(clv)

    out = {}
    for mkt, clvs in by_mkt.items():
        if clvs:
            out[mkt] = {
                "n": len(clvs),
                "mean_clv": round(float(np.mean(clvs)), 3),
                "t_match": round(float(np.mean(clvs)) / (float(np.std(clvs, ddof=1)) / np.sqrt(len(clvs))) if len(clvs) > 1 and float(np.std(clvs, ddof=1)) > 0 else 0.0, 2)
            }
        else:
            out[mkt] = {"n": 0, "mean_clv": 0.0, "t_match": 0.0}
    return out


def run_comparison() -> str:
    """Run the three-way comparison and return a formatted report."""
    legs = _load_clv_legs()
    if not legs:
        return "No settled paper legs with entry/close found yet."

    # --- Build market-implied probabilities from the log (approx) ---
    market_implied = _market_implied_from_log(legs)

    # --- RAW: just model_prob ---
    p_raw_map = {}
    for leg in legs:
        mkt = leg["market"]
        if mkt not in p_raw_map:
            p_raw_map[mkt] = leg["model_prob"]

    # --- FLAT NUDGE: recalibration adjustments ---
    # recalibration uses brain.calibration_by_market() internally; we replicate
    # the same rows format and call adjustments_for / shadow_adjustments
    cal_rows = []
    for mkt in _MARKET_ORDER:
        mkt_legs = [l for l in legs if l["market"] == mkt]
        if not mkt_legs:
            continue
        mean_hit = float(np.mean([l["hit"] for l in mkt_legs]))
        mean_model = float(np.mean([l["model_prob"] for l in mkt_legs]))
        clvs = [l["clv_pct"] for l in mkt_legs if l["clv_pct"] is not None]
        mean_clv = float(np.mean(clvs)) if clvs else 0.0
        cal_rows.append({
            "market": mkt,
            "n": len(mkt_legs),
            "mean_hit": mean_hit,
            "mean_model_prob": mean_model,
            "mean_clv_pct": mean_clv,
        })
    adj = recal.adjustments_for(cal_rows)
    shadow = recal.shadow_adjustments(cal_rows)

    p_nudge_map = {}
    for mkt in _MARKET_ORDER:
        delta = adj.get(mkt, shadow.get(mkt, 0.0))
        p_nudge_map[mkt] = recal.apply(p_raw_map.get(mkt, 0.5), delta)

    # --- RESIDUAL LAYER: fit from CLV log OOS pairs ---
    # Build OOS pairs per market: (p_model, p_market_open, hit)
    pairs_by_mkt = reslayer.pairs_from_clv_log()
    fits = reslayer.fit_all_markets(pairs_by_mkt)

    p_res_map = {}
    for mkt in _MARKET_ORDER:
        p_model = p_raw_map.get(mkt, 0.5)
        p_market = market_implied.get(mkt, p_model)
        fit = fits.get(mkt)
        p_res_map[mkt] = reslayer.calibrate(fit, p_model, p_market)

    # --- Compute CLV-style score for each trace ---
    clv_raw = _compute_clv_for_corrected(legs, p_raw_map)
    clv_nudge = _compute_clv_for_corrected(legs, p_nudge_map)
    clv_res = _compute_clv_for_corrected(legs, p_res_map)

    # --- Build report ---
    lines = [
        "=== OFFLINE Calibration Comparison (OLP XDV own CLV log) ===",
        f"Total settled paper legs: {len(legs)}",
        f"Markets with data: {[m for m in _MARKET_ORDER if m in p_raw_map]}",
        "",
        f"{'Market':<12} | {'RAW mean_p':>10} {'NUDGE mean_p':>12} {'RES mean_p':>11} | "
        f"{'RAW CLV%':>9} {'NUDGE CLV%':>11} {'RES CLV%':>9} | "
        f"{'RAW t':>6} {'NUDGE t':>8} {'RES t':>7}",
        "-" * 105,
    ]

    for mkt in _MARKET_ORDER:
        if mkt not in p_raw_map:
            continue
        cr = clv_raw.get(mkt, {"n": 0, "mean_clv": 0.0, "t_match": 0.0})
        cn = clv_nudge.get(mkt, {"n": 0, "mean_clv": 0.0, "t_match": 0.0})
        cs = clv_res.get(mkt, {"n": 0, "mean_clv": 0.0, "t_match": 0.0})

        lines.append(
            f"{mkt:<12} | {p_raw_map[mkt]:>10.4f} {p_nudge_map.get(mkt, 0.0):>12.4f} {p_res_map.get(mkt, 0.0):>11.4f} | "
            f"{cr['mean_clv']:>+9.3f} {cn['mean_clv']:>+11.3f} {cs['mean_clv']:>+9.3f} | "
            f"{cr['t_match']:>+6.2f} {cn['t_match']:>+8.2f} {cs['t_match']:>+7.2f}"
        )

    # Overall: compute from the legs directly for each trace
    def overall_clv(p_cal_map: dict[str, float]) -> tuple[float, float, int]:
        clvs = []
        for leg in legs:
            mkt = leg["market"]
            if leg["closing_odds"] is None:
                continue
            p_cal = p_cal_map.get(mkt, leg["model_prob"])
            if p_cal is None or p_cal <= 0:
                continue
            entry_odds_cal = 1.0 / p_cal
            clv = compute_clv(entry_odds_cal, leg["closing_odds"])
            clvs.append(clv)
        if clvs:
            mean = float(np.mean(clvs))
            std = float(np.std(clvs, ddof=1)) if len(clvs) > 1 else 0.0
            t = mean / (std / np.sqrt(len(clvs))) if std > 0 else 0.0
            return round(mean, 3), round(t, 2), len(clvs)
        return 0.0, 0.0, 0

    raw_overall = overall_clv(p_raw_map)
    nudge_overall = overall_clv(p_nudge_map)
    res_overall = overall_clv(p_res_map)

    # Residual layer activation status
    lines.extend([
        "",
        f"--- Overall CLV Comparison ---",
        f"  RAW:      n={raw_overall[2]:>3}  mean CLV={raw_overall[0]:+7.3f}%  t_match={raw_overall[1]:+6.2f}",
        f"  NUDGE:    n={nudge_overall[2]:>3}  mean CLV={nudge_overall[0]:+7.3f}%  t_match={nudge_overall[1]:+6.2f}",
        f"  RESIDUAL: n={res_overall[2]:>3}  mean CLV={res_overall[0]:+7.3f}%  t_match={res_overall[1]:+6.2f}",
        "",
        "--- Residual Layer Activation (earn-your-keep gate: n>=200 + OOS Brier < market-only) ---",
    ])
    for mkt in _MARKET_ORDER:
        if mkt in pairs_by_mkt:
            fit = fits.get(mkt)
            if fit is None:
                lines.append(f"  {mkt:<12}: INACTIVE  (n={len(pairs_by_mkt[mkt])} < 200)")
            else:
                flag = "ACTIVE" if fit.active else "INACTIVE (OOS Brier >= market)"
                lines.append(f"  {mkt:<12}: {flag:>30}  n={fit.n:>4}  brier_oos={fit.brier_oos:.4f}  brier_mkt={fit.brier_market:.4f}  a/g/b={fit.a:+.3f}/{fit.g:+.3f}/{fit.b:+.3f}")
        else:
            lines.append(f"  {mkt:<12}: NO DATA")

    lines.extend([
        "",
        "--- Recalibration (flat nudge) adjustments ---",
    ])
    for mkt in _MARKET_ORDER:
        if mkt in adj or mkt in shadow:
            lines.append(f"  {mkt:<12}: applied={adj.get(mkt, 0.0):+.4f}  shadow={shadow.get(mkt, 0.0):+.4f}")

    lines.extend([
        "",
        "NOTE: This is an OFFLINE experiment. The residual layer is NOT imported by run_daily.py.",
        "Any promotion to the live EV/calibration path requires explicit Architect signoff",
        "(CLAUDE.md protected constants: CLV/legs gate, ARCHITECT_SIGNOFF, calibration-log scope).",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    print(run_comparison())