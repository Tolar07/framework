"""
FORM CALIBRATION BACKTEST — does weighting recent form sharpen the model?

QUESTION
  engine/dixon_coles.fit() can weight recent matches more heavily
  (half_life_days, the standard Dixon-Coles time-decay). It is OFF by default.
  This asks, out-of-sample, whether turning it on makes the model's probabilities
  SHARPER — not whether a pick won, but whether the stated probabilities matched
  reality better. That is the necessary condition for any edge: if the numbers
  don't calibrate better, no CLV or ROI can come from the change.

METHOD (walk-forward, no look-ahead)
  Stream a league's completed matches in date order. For each matchday D, fit the
  model STRICTLY on matches before D (within a lookback window) at a given
  half-life, predict every match on D, and score the prediction against the
  actual result. Nothing on or after D is ever seen by the model that predicts it.

  Scored per half-life setting:
    - Brier score (multiclass 1X2): mean sum (p_i - y_i)^2. Lower = sharper.
    - Log-loss: mean -log(p_actual). Lower = sharper. Punishes confident misses.
    - Accuracy: argmax hit rate (secondary — a blunt measure).

  half_life = None is the baseline (equal weighting, today's default). A setting
  only earns "ship it" if it beats the baseline on Brier AND log-loss.

RESULT (2026-09-30, Eredivisie + Ekstraklasa, 2 seasons each — see
backtest/FORM_CALIBRATION_FINDINGS.md): time-decay did NOT help. Brier/log-loss
were flat-to-worse at every half-life, monotonically worse as the decay
shortened, on both leagues. Recommendation: keep time-decay OFF. This harness is
kept so the result is reproducible and re-checkable on more leagues/seasons.

HR35: a match with missing goals is skipped and not scored, never estimated.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import load_league
from engine.dixon_coles import fit, predict

DEFAULT_GRID = [None, 365, 180, 90]     # half_life_days; None = equal weighting


def _load_stream(league: str, seasons: list[str]) -> list:
    out: list = []
    for s in seasons:
        try:
            res, _ = load_league(league, s)
            out += [r for r in res if r.fthg is not None and r.ftag is not None]
        except Exception:
            continue
    out.sort(key=lambda r: r.date)
    return out


def _outcome(r) -> int:
    return 0 if r.fthg > r.ftag else (1 if r.fthg == r.ftag else 2)


def backtest_league(league: str, seasons: list[str], grid: list,
                    window_days: int = 550, warmup: int = 80,
                    min_train: int = 60) -> dict | None:
    """Walk-forward calibration per half-life. Returns {hl: metrics} or None."""
    res = _load_stream(league, seasons)
    if len(res) < warmup + 40:
        return None
    dates = sorted({r.date for r in res})
    sc = {hl: {"brier": 0.0, "logloss": 0.0, "hit": 0, "n": 0} for hl in grid}

    for d in dates:
        prior = [r for r in res if r.date < d]
        if len(prior) < warmup:
            continue
        train = [r for r in prior
                 if (date.fromisoformat(d) - date.fromisoformat(r.date)).days <= window_days]
        if len(train) < min_train:
            continue
        today = [r for r in res if r.date == d]
        for hl in grid:
            try:
                model = fit(train, half_life_days=hl, ref_date=d)
            except Exception:
                continue
            for r in today:
                p = predict(model, r.home_team, r.away_team)
                if p is None:
                    continue
                probs = [p.p_home, p.p_draw, p.p_away]
                total = sum(probs)
                if total <= 0:
                    continue
                probs = [x / total for x in probs]
                y = _outcome(r)
                sc[hl]["brier"] += sum((probs[i] - (1 if i == y else 0)) ** 2 for i in range(3))
                sc[hl]["logloss"] += -math.log(max(probs[y], 1e-9))
                sc[hl]["hit"] += 1 if max(range(3), key=lambda i: probs[i]) == y else 0
                sc[hl]["n"] += 1
    return sc


def _report(league: str, sc: dict, grid: list) -> None:
    print(f"\n==== {league} ====")
    if not sc or not sc[grid[0]]["n"]:
        print("  insufficient data")
        return
    base_n = sc[None]["n"] or 1 if None in sc else 1
    base_brier = (sc[None]["brier"] / base_n) if None in sc else None
    for hl in grid:
        s = sc[hl]
        n = s["n"] or 1
        brier, logloss, acc = s["brier"] / n, s["logloss"] / n, 100 * s["hit"] / n
        tag = "(baseline)" if hl is None else ""
        delta = "" if (hl is None or base_brier is None) else f"  dBrier {brier - base_brier:+.4f}"
        print(f"  half_life={str(hl):>5}  n={s['n']:4d}  Brier {brier:.4f}  "
              f"LogLoss {logloss:.4f}  Acc {acc:4.1f}% {tag}{delta}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Form (time-decay) calibration backtest")
    ap.add_argument("--leagues", nargs="+", default=["Eredivisie", "Ekstraklasa"])
    ap.add_argument("--seasons", nargs="+", default=["2425", "2526"])
    ap.add_argument("--grid", nargs="+", type=lambda v: None if v.lower() == "none" else int(v),
                    default=DEFAULT_GRID, help="half_life_days values; use 'none' for baseline")
    ap.add_argument("--window-days", type=int, default=550)
    ap.add_argument("--warmup", type=int, default=80)
    a = ap.parse_args()
    t0 = time.time()
    for lg in a.leagues:
        _report(lg, backtest_league(lg, a.seasons, a.grid, a.window_days, a.warmup) or {}, a.grid)
    print(f"\n[done in {time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
