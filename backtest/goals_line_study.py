"""GOALS LINE STUDY (2026-10-13): does the model's Over/Under 3.5 and 4.5 land?

STATE item 31: the board's match Under 3.5 / 4.5 picks said 79.5% and landed
68.6%, and engine/calibration.py corrects only the 1.5 and 2.5 lines. Same
walk-forward as backtest/btts_study.py (model fitted only on matches before
each 14-day block, 14 leagues, two seasons): the raw model's Over 3.5 / 4.5
chance against what landed, by band; then a Platt fit (the method that
corrected 1.5/2.5) checked out of sample — leave one league out, Brier score
before and after. A study: nothing changes the engine until the Architect
says so. Results: backtest/GOALS_LINE_STUDY.md.

    python backtest/goals_line_study.py
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from collections import defaultdict  # noqa: E402
from datetime import date, timedelta  # noqa: E402

import numpy as np  # noqa: E402

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates  # noqa: E402
from backtest.selection_study import GROUPS  # noqa: E402
from data.football_data_source import load_league  # noqa: E402
from engine.dixon_coles import predict  # noqa: E402

OUT = ROOT / "backtest" / "GOALS_LINE_STUDY.md"
CACHE = ROOT / "backtest" / "results" / "goals_line_rows.json"


def collect() -> list[tuple]:
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="", refit_every_days=14)
    rows = []   # (league, season, p_o35, o35, p_o45, o45)
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception as e:  # noqa: BLE001
                print("skip", lg, test_s, e)
                continue
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            warm = None
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                if not block:
                    continue
                model, _ = get_model(lg, cut, hist, cfg, warm)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for m in block:
                    p = predict(model, m.home_team, m.away_team)
                    if p is None or p.matrix is None:
                        continue
                    t = m.fthg + m.ftag
                    tot = np.add.outer(np.arange(p.matrix.shape[0]), np.arange(p.matrix.shape[1]))
                    rows.append((lg, test_s, float(p.p_over_35), t >= 4, float(p.matrix[tot >= 5].sum()), t >= 5))
            print("done", lg, test_s, flush=True)
    return rows


def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def platt(xs: list[float], ys: list[bool]) -> tuple[float, float]:
    """Fit sigmoid(a + b * logit(p)) by Newton's method on the log loss."""
    a, b = 0.0, 1.0
    X = np.array([logit(x) for x in xs])
    Y = np.array(ys, dtype=float)
    for _ in range(50):
        z = a + b * X
        p = 1 / (1 + np.exp(-z))
        g = np.array([np.sum(p - Y), np.sum((p - Y) * X)])
        w = p * (1 - p)
        H = np.array([[np.sum(w), np.sum(w * X)], [np.sum(w * X), np.sum(w * X * X)]]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-9:
            break
    return float(a), float(b)


def cal(p: float, ab: tuple[float, float]) -> float:
    return 1 / (1 + math.exp(-(ab[0] + ab[1] * logit(p))))


def brier(ps, ys) -> float:
    return float(np.mean([(p - y) ** 2 for p, y in zip(ps, ys, strict=True)]))


def section(rows: list[tuple], i_p: int, i_y: int, name: str) -> list[str]:
    ps, ys = [r[i_p] for r in rows], [r[i_y] for r in rows]
    L = [f"## {name} — {len(rows)} matches", "",
         f"Model said Over {100 * np.mean(ps):.1f}% on average; landed {100 * np.mean(ys):.1f}%. "
         f"So Under {100 * (1 - np.mean(ps)):.1f}% said, {100 * (1 - np.mean(ys)):.1f}% landed.", "",
         "| Model's UNDER chance | matches | Under landed |", "|---|---:|---:|"]
    bands = defaultdict(list)
    for p, y in zip(ps, ys, strict=True):
        u = 1 - p
        b = min(int(u * 10), 9) / 10
        bands[b].append(not y)
    for b in sorted(bands):
        if len(bands[b]) >= 20:
            L.append(f"| {b:.0%}–{b + 0.1:.0%} | {len(bands[b])} | {100 * np.mean(bands[b]):.1f}% |")
    ab = platt(ps, ys)
    leagues = sorted({r[0] for r in rows})
    before, after, better = [], [], 0
    for lg in leagues:
        tr = [r for r in rows if r[0] != lg]
        te = [r for r in rows if r[0] == lg]
        f = platt([r[i_p] for r in tr], [r[i_y] for r in tr])
        b0 = brier([r[i_p] for r in te], [r[i_y] for r in te])
        b1 = brier([cal(r[i_p], f) for r in te], [r[i_y] for r in te])
        before.append(b0 * len(te))
        after.append(b1 * len(te))
        better += b1 < b0
    n = len(rows)
    L += ["", f"Platt fit on all {n}: a = {ab[0]:.4f}, b = {ab[1]:.4f}. Leave one league out: Brier "
          f"{sum(before) / n:.4f} → {sum(after) / n:.4f}, better in {better} of {len(leagues)} leagues.", "",
          "| Raw model Under | calibrated Under |", "|---:|---:|"]
    for u in (0.60, 0.70, 0.75, 0.80, 0.85, 0.90):
        L.append(f"| {u:.0%} | {1 - cal(1 - u, ab):.1%} |")
    return L + [""]


def main() -> None:
    if CACHE.exists():
        rows = [tuple(r) for r in json.loads(CACHE.read_text())]
    else:
        rows = collect()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(rows))
    L = ["# GOALS LINE STUDY — the model's Over/Under 3.5 and 4.5 against results", "",
         "Walk-forward (`backtest/goals_line_study.py`, method of `backtest/btts_study.py`): the model fitted "
         "only on matches before each 14-day block. STATE item 31 asked whether the board's match Unders run on "
         "an uncalibrated model. A study — nothing in the engine changes until the Architect says so.", ""]
    L += section(rows, 2, 3, "Over/Under 3.5")
    L += section(rows, 4, 5, "Over/Under 4.5")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
