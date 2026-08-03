"""
CALIBRATION DIAGNOSTIC — is the model's 70% actually a 70%?

WHY THIS EXISTS
  Three independent signals said the engine overstates its confidence:
    * backtest mean CLV negative in both leagues tested
    * backtest hit rate 31.5% on selections rated far higher
    * a live board where 5 of 5 fixtures showed positive EV, which cannot
      happen against an efficient market with a calibrated model
  None of those localise the problem. This does: it bins every walk-forward
  prediction by the probability the model assigned, and compares that to how
  often the thing actually happened.

  A well-calibrated model's 60-70% bucket contains events that occur about
  65% of the time. If it instead occurs 45% of the time, the model is
  overconfident by 20 points in that band and every MES computed there is
  inflated by roughly the same amount.

METHOD
  Reuses the SAME walk-forward machinery and the SAME cached models as the CLV
  backtest, so predictions here are exactly the ones the backtest scored — no
  look-ahead, no refit, no separate code path that could disagree.

HR35
  Reports the measurement. It does not fit a correction, does not tune a
  parameter, and does not touch the engine. Choosing a remedy is a modelling
  decision for the Architect (Section 12: calibration rules are not
  auto-ratifiable).
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import load_league
from engine.dixon_coles import predict
from backtest.clv_backtest import BacktestConfig, refit_cut_dates, get_model

# Wider at the tails, where thin data would otherwise make a bucket meaningless.
BINS = [(0.0, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 0.50),
        (0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01)]


def collect(league: str, cfg: BacktestConfig) -> list[tuple[str, float, bool]]:
    """(market, predicted_probability, did_it_happen) for every walk-forward
    prediction — ALL fixtures, not just the ones a selection rule liked.
    Filtering to selected legs would measure the selector, not the model."""
    carry, _ = load_league(league, cfg.carry_in_season)
    test, _ = load_league(league, cfg.test_season)
    history = sorted(carry + test, key=lambda r: r.date)
    test_sorted = sorted(test, key=lambda r: r.date)

    rows: list[tuple[str, float, bool]] = []
    warm = None
    for cut in refit_cut_dates([r.date for r in test_sorted], cfg.refit_every_days):
        end = (date.fromisoformat(cut) + timedelta(days=cfg.refit_every_days)).isoformat()
        block = [r for r in test_sorted if cut <= r.date < end]
        if not block:
            continue
        model, _ = get_model(league, cut, history, cfg, warm)
        if model is None:
            continue
        if getattr(model, "warm_seed", None):
            warm = model.warm_seed
        for m in block:
            p = predict(model, m.home_team, m.away_team)
            if p is None:
                continue
            total = m.fthg + m.ftag
            rows += [
                ("Home win", p.p_home, m.fthg > m.ftag),
                ("Draw", p.p_draw, m.fthg == m.ftag),
                ("Away win", p.p_away, m.ftag > m.fthg),
                ("Over 2.5", p.p_over_25, total > 2),
                ("Over 1.5", p.p_over_15, total > 1),
                ("BTTS yes", p.p_btts_yes, m.fthg > 0 and m.ftag > 0),
            ]
    return rows


def report(rows: list[tuple[str, float, bool]], title: str) -> str:
    out = [f"\n{'=' * 74}", f"CALIBRATION — {title}", "=" * 74]
    markets = sorted({r[0] for r in rows})

    for mkt in markets:
        sub = [(p, hit) for m, p, hit in rows if m == mkt]
        if not sub:
            continue
        out.append(f"\n{mkt}   (n={len(sub)})")
        out.append(f"  {'model says':<14}{'n':>6}{'actual':>9}{'gap':>9}   reading")
        for lo, hi in BINS:
            bucket = [(p, h) for p, h in sub if lo <= p < hi]
            if len(bucket) < 8:
                continue
            pred = sum(p for p, _ in bucket) / len(bucket)
            act = sum(1 for _, h in bucket if h) / len(bucket)
            gap = (pred - act) * 100
            if abs(gap) < 5:
                verdict = "well calibrated"
            elif gap > 0:
                verdict = f"OVERCONFIDENT by {gap:.0f}pp"
            else:
                verdict = f"underconfident by {-gap:.0f}pp"
            out.append(f"  {lo*100:>3.0f}-{hi*100:<3.0f}%      {len(bucket):>6}"
                       f"{act*100:>8.1f}%{gap:>+8.1f}pp   {verdict}")

        pred_all = sum(p for p, _ in sub) / len(sub)
        act_all = sum(1 for _, h in sub if h) / len(sub)
        out.append(f"  OVERALL: model mean {pred_all*100:.1f}% vs actual "
                   f"{act_all*100:.1f}%  ({(pred_all-act_all)*100:+.1f}pp)")

    # Brier score: mean squared error of the probabilities. Lower is better;
    # 0.25 is what you get by always saying 50%.
    brier = sum((p - (1 if h else 0)) ** 2 for _, p, h in rows) / len(rows)
    out.append(f"\nBrier score (all markets): {brier:.4f}   "
               f"[0.25 = always guessing 50%; lower is better]")
    return "\n".join(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", nargs="+",
                     default=["Scottish Premiership", "Eredivisie"])
    ap.add_argument("--test-season", default="2425")
    ap.add_argument("--carry-in", default="2324")
    a = ap.parse_args()

    all_rows = []
    for lg in a.leagues:
        cfg = BacktestConfig(leagues=(lg,), carry_in_season=a.carry_in,
                              test_season=a.test_season)
        rows = collect(lg, cfg)
        all_rows += rows
        print(report(rows, lg))
    if len(a.leagues) > 1:
        print(report(all_rows, "ALL LEAGUES COMBINED"))
