"""
Backtest reporting.

Separated from the engine the same way output/produce_bet.py is separated from
engine/dixon_coles.py — measurement and presentation should not be able to
drift into each other.

Design principle here: a backtest that prints "412 legs, mean CLV +1.2%" and
nothing else is not a finding, it's a claim. Everything below exists so the
reader can see what was excluded, how much of the movement was bookmaker
margin rather than model skill, and how far the number is from evidence.
"""
from __future__ import annotations

import math
import statistics
from typing import Optional

# No softness imports — ID402 A/B/C/D tiers were removed 2026-08-10 (one
# unified pool). The A/B-vs-C/D control section that used softness_tier /
# DEPLOY_ELIGIBLE_TIERS was replaced with a single whole-pool summary.


def _pct(x: Optional[float], dp: int = 2) -> str:
    return "NO DATA — PENDING" if x is None else f"{x:.{dp}f}%"


def _mean(xs: list[float]) -> Optional[float]:
    return round(statistics.fmean(xs), 4) if xs else None


def summarise(legs: list, label: str) -> dict:
    """One bucket of legs -> the numbers. Raw-price and DERIVED legs are
    summarised separately by the caller and MUST NOT be pooled: derived CLV is
    computed in probability space and contains no margin drift, so averaging
    the two would mix two different quantities."""
    selected = [l for l in legs if l.status in ("OK", "NO_CLOSE")]
    measured = [l for l in legs if l.status == "OK" and l.clv_pct is not None]
    clvs = [l.clv_pct for l in measured]

    n = len(clvs)
    sd = round(statistics.stdev(clvs), 4) if n > 1 else None
    se = round(sd / math.sqrt(n), 4) if sd and n > 1 else None
    mean = _mean(clvs)

    graded = [l for l in measured if l.hit is not None]
    # Flat 1-unit stake, settled at the entry price.
    pnl = [(l.entry_odds - 1.0) if l.hit else -1.0 for l in graded if l.entry_odds]

    or_open = [l.overround_open for l in measured if l.overround_open is not None]
    or_close = [l.overround_close for l in measured if l.overround_close is not None]

    # Calibration view: what the model CLAIMED vs what reality did. The fair
    # implied probability strips each leg's own open/close overround (the
    # margin the book holds on that price), so model_p can be compared to a
    # margin-free market probability — the honest comparison for a reliability
    # check. This is why the away bucket was -2.1%: model_p sat ~8pp above
    # fair-implied AND above the realized hit rate, a calibration gap a raw-EV
    # screen cannot see (raw EV even amplifies it on long prices).
    def _fair_implied(odds, overround):
        if odds is None or not overround:
            return None
        return (1.0 / odds) / (1.0 + overround)

    model_ps = [l.model_prob for l in measured if l.model_prob is not None]
    fair_opens = [_fair_implied(l.entry_odds, l.overround_open)
                  for l in measured if l.entry_odds and l.overround_open is not None]
    fair_closes = [_fair_implied(l.closing_odds, l.overround_close)
                   for l in measured if l.closing_odds and l.overround_close is not None]

    return {
        "label": label,
        "n_legs_selected": len(selected),
        "n_with_clv": n,
        "n_no_close": sum(1 for l in legs if l.status == "NO_CLOSE"),
        "n_no_entry": sum(1 for l in legs if l.status == "NO_ENTRY"),
        "n_no_model": sum(1 for l in legs if l.status == "NO_MODEL"),
        "n_distinct_matches": len({(l.date, l.fixture) for l in measured}),
        "mean_clv_pct": mean,
        "median_clv_pct": round(statistics.median(clvs), 4) if clvs else None,
        "sd_clv": sd,
        "se_clv": se,
        "t_stat": round(mean / se, 3) if (mean is not None and se) else None,
        "pct_beat_close": round(100 * sum(1 for c in clvs if c > 0) / n, 2) if n else None,
        "pct_lost_to_close": round(100 * sum(1 for c in clvs if c < 0) / n, 2) if n else None,
        "pct_zero_movement": round(100 * sum(1 for c in clvs if c == 0) / n, 2) if n else None,
        "hit_rate_pct": round(100 * sum(1 for l in graded if l.hit) / len(graded), 2) if graded else None,
        "roi_pct": round(100 * sum(pnl) / len(pnl), 2) if pnl else None,
        "n_graded": len(pnl),
        "mean_overround_open": _mean(or_open),
        "mean_overround_close": _mean(or_close),
        "mean_model_prob": _mean(model_ps),
        "mean_fair_implied_open": _mean(fair_opens),
        "mean_fair_implied_close": _mean(fair_closes),
    }


def _row(s: dict) -> str:
    return (f"  {s['label']:<26} "
            f"legs={s['n_legs_selected']:>5}  clv_n={s['n_with_clv']:>5}  "
            f"mean={_pct(s['mean_clv_pct'], 3):>12}  "
            f"beat={_pct(s['pct_beat_close'], 1):>8}  "
            f"flat={_pct(s['pct_zero_movement'], 1):>7}  "
            f"t={str(s['t_stat'] or '—'):>7}")


def _cal_row(s: dict) -> str:
    """One market's calibration line: what the model claimed vs what happened.

    model_p, fair_open, hit_rate and fair_close are all PROBABILITIES (0-1) so
    the reliability gap is readable directly in percentage points. hit_rate_pct
    is a percentage in `summarise` — divided back to a fraction here. When the
    model is calibrated, model_p ≈ hit_rate ≈ fair_close. A positive gap means
    the model was overconfident: it claimed more than reality delivered.
    """
    mp, fo, hr, fc = s["mean_model_prob"], s["mean_fair_implied_open"], None, s["mean_fair_implied_close"]
    if s["hit_rate_pct"] is not None:
        hr = s["hit_rate_pct"] / 100.0
    gap = None
    if mp is not None and hr is not None:
        gap = mp - hr
    fmt = lambda x: "NO DATA" if x is None else f"{x:.3f}"
    return (f"  {s['label']:<20} "
            f"n={s['n_graded']:>4}  "
            f"model_p={fmt(mp):>8}  fair_open={fmt(fo):>9}  "
            f"hit={fmt(hr):>8}  fair_close={fmt(fc):>10}  "
            f"gap={fmt(gap):>8}")


def render_report(legs: list, flags: list[str], coverage: dict, cfg,
                   run_id: str) -> str:
    raw = [l for l in legs if not l.derived]
    derived = [l for l in legs if l.derived]

    out: list[str] = []
    A = out.append

    A("=" * 78)
    A("CLV BACKTEST — OLP XDV")
    A("=" * 78)
    A(f"Run ID          : {run_id}")
    A(f"Config          : {cfg.fingerprint()}   (any change here = a different experiment)")
    A(f"Fit season      : {cfg.carry_in_season} (carry-in) -> legs placed in {cfg.test_season}")
    A(f"Selector        : {cfg.selector}   min_MES={cfg.min_mes}  (PRE-DECLARED, not swept)")
    A(f"Refit cadence   : every {cfg.refit_every_days} days   book preference: {', '.join(cfg.book_preference)}")
    A(f"Time decay      : {cfg.half_life_days or 'OFF'}")
    if getattr(cfg, "calibrate", False):
        A(f"Calibration     : ON (out-of-sample, gate >= {cfg.cal_min_legs} legs, "
          f"cap +/-{cfg.cal_max_adjustment:.2f})")
    else:
        A("Calibration     : OFF")
    if getattr(cfg, "blend_market", False):
        A("Market blend    : ON (pull model probs toward the devigged line, "
          "proportional to disagreement)")
    else:
        A("Market blend    : OFF")
    A("")

    A("COVERAGE — what was scanned and what never reached a leg")
    A(f"  {'league':<26} {'fixtures':>9} {'warmup':>8} {'no_model':>9}")
    for lg, cov in coverage.items():
        A(f"  {lg:<26} {cov['n_fixtures_in_scope']:>9} "
          f"{cov['n_excluded_warmup']:>8} {cov['n_no_model']:>9}")
    A("")

    if flags:
        A("DATA FLAGS (surfaced first, per HR35 — a gap is reported, never filled)")
        for f in flags:
            A(f"  ! {f}")
        A("")

    A("RAW-PRICE CLV  (1X2 + Over/Under 2.5 — actual quoted prices)")
    A(_row(summarise(raw, "ALL LEAGUES")))
    A("")
    for lg in sorted({l.league for l in raw}):
        A(_row(summarise([l for l in raw if l.league == lg], lg)))
    A("")
    for mkt in sorted({l.market for l in raw}):
        A(_row(summarise([l for l in raw if l.market == mkt], f"market: {mkt}")))
    A("")

    A("MODEL CALIBRATION — what the model CLAIMED vs what actually happened")
    A("  (model_p is the model's mean probability on the legs it took; hit is")
    A("   the realized rate. A calibrated model has model_p ~ hit ~ fair_close.")
    A("   A positive gap = overconfidence: the model claimed more than reality.")
    for mkt in sorted({l.market for l in raw}):
        A(_cal_row(summarise([l for l in raw if l.market == mkt], mkt)))
    A("")

    A("UNIFIED POOL — every whitelisted league is one deploy-eligible pool")
    A("  (ID402 A/B/C/D softness tiers removed 2026-08-10 — the A/B-vs-C/D")
    A("  control is dead; the pool is measured as a whole, not split by tier.)")
    A(_row(summarise(raw, "ONE pool (all whitelisted)")))
    A("")

    if derived:
        A("DERIVED O1.5 CLV  (probability space — NOT comparable to raw-price CLV above)")
        A(_row(summarise(derived, "O1.5 (DERIVED)")))
        A("  ! O1.5 is NEVER quoted in this source. These figures are derived from the")
        A("    O2.5 line under a Poisson total-goals assumption and labelled DERIVED per")
        A("    HR30. They are in probability space and contain no margin drift, so they")
        A("    must not be averaged with the raw-price numbers above.")
        A("")

    ov = summarise(raw, "_")
    A("MARGIN DRIFT CONTROL")
    A(f"  mean overround at OPEN : {ov['mean_overround_open']}")
    A(f"  mean overround at CLOSE: {ov['mean_overround_close']}")
    if ov["mean_overround_open"] is not None and ov["mean_overround_close"] is not None:
        drift = ov["mean_overround_close"] - ov["mean_overround_open"]
        A(f"  drift: {drift:+.5f}")
        if drift < -0.001:
            A("  ! Margin SHRINKS toward the close. Part of the CLV above is that")
            A("    shrinkage, not model skill. Compare against the placebo run before")
            A("    reading any of it as edge.")
    A("")

    A("SECONDARY — hit rate and ROI (deliberately demoted)")
    A(f"  hit rate: {_pct(ov['hit_rate_pct'], 2)}   ROI: {_pct(ov['roi_pct'], 2)}   "
      f"(n graded={ov['n_graded']})")
    n = ov["n_graded"] or 0
    if n:
        roi_se = 120.0 / math.sqrt(n)   # per-leg PnL sd ~1.2 units at these prices
        A(f"  ROI standard error at n={n} is roughly +/-{roi_se:.1f}%. Detecting a true 3%")
        A(f"  edge at conventional confidence needs on the order of 6,000-13,000 legs.")
        A("  This sample CANNOT distinguish a 3% edge from zero. CLV is the instrument;")
        A("  ROI here is a smoke test that the model isn't broken, not evidence.")
    A("")

    A("HOW TO READ THIS")
    A("  * t is NOT a p-value. Legs are not independent: one match yields several legs,")
    A(f"    and every match inside a {cfg.refit_every_days}-day block shares one model fit. The effective")
    A("    sample is closer to n_distinct_matches than to n_legs, so the true standard")
    A("    error is WIDER than se_clv suggests.")
    A("  * 'flat' is the share of legs where the line did not move at all. A high flat")
    A("    share means 'beat' and 'lost' are both diluted and the headline means less.")
    A("")

    A("CAVEATS — every one of these is a limit of the DATA, not of the run")
    A("  1. UPPER BOUND. 'Opening' price is a single undated archive snapshot. A real")
    A("     entry lands somewhere between open and close and captures only a fraction of")
    A("     the movement. This is the ONE bias here that FLATTERS the result.")
    A("  2. The archived book is not SportyBet or Bet365 Nigeria. This measures whether")
    A("     the model finds lines that move — not whether the Architect could get that price.")
    A("  3. Danish Superliga and Ekstraklasa carry CLOSING PRICES ONLY in this source, so")
    A("     entry-vs-close is undefined. Two of five deploy-eligible leagues, including")
    A("     one of two Tier-A leagues, are unmeasurable here.")
    A("  4. O1.5 is never quoted. ID390's central question is NOT directly answerable")
    A("     with this data.")
    A("  5. BTTS and Over 3.5 have no prices at any point in either schema. Permanently")
    A("     unmeasurable from this source, despite BTTS appearing on the live board.")
    A(f"  6. Model staleness up to {cfg.refit_every_days - 1} days. This biases AGAINST the model — it always")
    A("     has less information than a same-day refit — so a positive result is a lower bound.")
    if not cfg.half_life_days:
        A("  7. No time weighting: a match from the carry-in season counts as much as last week's.")
    A("")

    A("HONEST EDGE LINE: this is an excellent informed process but NOT a demonstrated")
    A("profitable edge. A backtest measures; only logged forward CLV proves.")
    A("Capital authority: THE ARCHITECT. Nothing here is live until the Architect deploys it.")
    A("=" * 78)
    return "\n".join(out)
