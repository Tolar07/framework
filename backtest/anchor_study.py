"""
ANCHOR + CALIBRATION STUDY (improvement #4, Architect 2026-10-02).

Q1. How much should the pick's probability lean on the MARKET vs the MODEL?
    p = market + w * (model - market) for w in WEIGHTS (w=0.5 is today's
    50/50 consensus; w=0 pure market; w=1 pure model).
Q2. Are the stated probabilities honest? Calibration error (ECE) of the
    chosen picks, before and after an isotonic calibration map fitted on the
    PREVIOUS season and applied to the next (out-of-sample).

Walk-forward, production model fit (last + current season, 240-day
half-life), opening prices, band 1.20-2.00, one pick per match: the in-band
market (1X2, Double Chance, O/U 2.5) with the highest blended probability.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.clv_backtest import BacktestConfig, get_model, refit_cut_dates
from data.football_data_source import load_league
from engine.dixon_coles import predict

GROUPS = [
    ("2324", "2425", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League"]),
    ("2425", "2526", ["Premier League", "Championship", "La Liga", "Serie A", "Bundesliga",
                      "Ligue 1", "Eredivisie", "Primeira Liga", "Scottish Premiership",
                      "Belgian Pro League", "League One", "League Two"]),
]
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
BAND = (1.20, 2.00)
RECORDS = Path(__file__).with_name("anchor_records.json")


def _devig(ps):
    inv = [1 / p for p in ps]
    s = sum(inv)
    return [i / s for i in inv]


def collect() -> list[dict]:
    cfg = BacktestConfig(leagues=(), carry_in_season="", test_season="",
                         refit_every_days=14, max_history_matches=800, half_life_days=240.0)
    recs = []
    for carry_s, test_s, leagues in GROUPS:
        for lg in leagues:
            try:
                carry, _ = load_league(lg, carry_s)
                test, _ = load_league(lg, test_s)
            except Exception:
                continue
            hist = sorted(carry + test, key=lambda r: r.date)
            test = sorted(test, key=lambda r: r.date)
            warm = None
            for cut in refit_cut_dates([r.date for r in test], 14):
                end = (date.fromisoformat(cut) + timedelta(days=14)).isoformat()
                block = [r for r in test if cut <= r.date < end]
                model, _ = get_model(lg, cut, hist, cfg, warm) if block else (None, None)
                if model is None:
                    continue
                warm = getattr(model, "warm_seed", None) or warm
                for r in block:
                    o = r.odds
                    if not o or not all((o.home.open, o.draw.open, o.away.open,
                                         o.over25.open, o.under25.open)):
                        continue
                    p = predict(model, r.home_team, r.away_team)
                    if p is None:
                        continue
                    mh, md, ma = _devig([o.home.open, o.draw.open, o.away.open])
                    mo, mu = _devig([o.over25.open, o.under25.open])
                    H, D, A = o.home.open, o.draw.open, o.away.open
                    t = r.fthg + r.ftag
                    # (market, model_p, market_p, price, won)
                    rows = [
                        ("HOME", p.p_home, mh, H, r.fthg > r.ftag),
                        ("DRAW", p.p_draw, md, D, r.fthg == r.ftag),
                        ("AWAY", p.p_away, ma, A, r.ftag > r.fthg),
                        ("OVER25", p.p_over_25, mo, o.over25.open, t > 2),
                        ("UNDER25", 1 - p.p_over_25, mu, o.under25.open, t <= 2),
                        ("DC_1X", p.p_home + p.p_draw, mh + md, 1 / (1 / H + 1 / D), r.fthg >= r.ftag),
                        ("DC_X2", p.p_draw + p.p_away, md + ma, 1 / (1 / D + 1 / A), r.ftag >= r.fthg),
                        ("DC_12", p.p_home + p.p_away, mh + ma, 1 / (1 / H + 1 / A), r.fthg != r.ftag),
                    ]
                    recs.append({"season": test_s, "league": lg, "date": r.date,
                                 "rows": [x for x in rows if BAND[0] <= x[3] <= BAND[1]]})
            print(f"done {lg} {test_s}", flush=True)
    RECORDS.write_text(json.dumps(recs), encoding="utf-8")
    return recs


def pick(rec, w):
    if not rec["rows"]:
        return None
    best = max(rec["rows"], key=lambda x: x[2] + w * (x[1] - x[2]))
    return best[2] + w * (best[1] - best[2]), best


def isotonic(points):
    """Pool-adjacent-violators: [(p, y)] -> list of (p_upper, rate) steps."""
    pts = sorted(points)
    blocks = [[p, y, 1] for p, y in pts]          # [max_p, sum_y, n]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][1] / blocks[i][2] > blocks[i + 1][1] / blocks[i + 1][2]:
            a, b = blocks[i], blocks.pop(i + 1)
            a[0], a[1], a[2] = b[0], a[1] + b[1], a[2] + b[2]
            i = max(i - 1, 0)
        else:
            i += 1
    return [(b[0], b[1] / b[2]) for b in blocks]


def apply_iso(steps, p):
    for up, rate in steps:
        if p <= up:
            return rate
    return steps[-1][1]


def ece(pairs, bins=10):
    """Expected calibration error over (stated p, won) pairs, in points."""
    if not pairs:
        return float("nan")
    tot, n = 0.0, len(pairs)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if lo <= p < hi or (b == bins - 1 and p == 1)]
        if sel:
            tot += len(sel) / n * abs(sum(p for p, _ in sel) / len(sel) - sum(y for _, y in sel) / len(sel))
    return 100 * tot


def analyse(recs) -> str:
    L = ["ANCHOR + CALIBRATION STUDY — one pick per match, band 1.20-2.00, opening prices", ""]
    seasons = sorted({r["season"] for r in recs})
    L.append(f"{'w (model weight)':18} " + " ".join(f"{s:>34}" for s in seasons))
    for w in WEIGHTS:
        cells = []
        for s in seasons:
            res = [pick(r, w) for r in recs if r["season"] == s]
            res = [x for x in res if x]
            n = len(res)
            hit = sum(b[4] for _, b in res) / n
            roi = sum((b[3] - 1) if b[4] else -1 for _, b in res) / n
            e = ece([(p, b[4]) for p, b in res])
            cells.append(f"n={n:5d} hit={100*hit:4.1f}% roi={100*roi:+5.2f}% ECE={e:4.1f}")
        L.append(f"w={w:<16} " + " ".join(f"{c:>34}" for c in cells))
    L += ["", "Calibration (isotonic map fitted on the earlier season, applied to the next):"]
    for w in (0.5, 0.25):
        train = [x for x in (pick(r, w) for r in recs if r["season"] == seasons[0]) if x]
        test = [x for x in (pick(r, w) for r in recs if r["season"] == seasons[1]) if x]
        steps = isotonic([(p, int(b[4])) for p, b in train])
        before = ece([(p, b[4]) for p, b in test])
        after = ece([(apply_iso(steps, p), b[4]) for p, b in test])
        avg_stated = sum(p for p, _ in test) / len(test)
        avg_real = sum(b[4] for _, b in test) / len(test)
        L.append(f"  w={w}: stated avg {100*avg_stated:.1f}% vs real {100*avg_real:.1f}% · "
                 f"ECE {before:.1f} -> {after:.1f} pts after calibration")
    return "\n".join(L)


if __name__ == "__main__":
    recs = json.loads(RECORDS.read_text()) if RECORDS.exists() and "--reuse" in sys.argv else collect()
    out = analyse(recs)
    print(out)
    Path(__file__).with_name("ANCHOR_STUDY.md").write_text("```\n" + out + "\n```\n", encoding="utf-8")
