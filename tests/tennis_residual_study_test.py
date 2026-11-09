"""Tennis residual study: fit shrinks to the market when there is no signal, walk-forward uses earlier years only. No network."""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_residual_study as rs  # noqa: E402
from backtest import tennis_backtest as tb  # noqa: E402


def _games(n=4000, seed=3):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        mkt = rnd.uniform(0.2, 0.8)
        year = 2019 + (i * 7) // n
        out.append({"year": year, "day": f"{year}-06-01", "tour": "ATP", "surface": "Hard",
                    "a": f"A{i % 40}", "b": f"B{i % 37}", "y": 1.0 if rnd.random() < mkt else 0.0,
                    "mkt": mkt, "pa": 1 / mkt, "pb": 1 / (1 - mkt), "qa": 1 / mkt, "qb": 1 / (1 - mkt),
                    "ra": float(rnd.randint(1, 200)), "rb": float(rnd.randint(1, 200))})
    return out


def test_solve_and_fit_recover_signal():
    assert rs.solve([[2.0, 0.0], [0.0, 4.0]], [2.0, 4.0]) == [1.0, 1.0]
    assert rs.solve([[0.0, 0.0], [0.0, 0.0]], [1.0, 1.0]) is None
    rnd = random.Random(1)
    rows = []
    for _ in range(3000):
        x = rnd.gauss(0, 1)
        rows.append(([x], 0.0, 1.0 if rnd.random() < tb.sig(0.8 * x) else 0.0))
    assert 0.5 < rs.fit(rows)[0] < 1.0


def test_pure_noise_stays_near_market_and_is_not_a_win():
    g = _games()
    feats = [[rnd, rnd2] for rnd, rnd2 in zip([0.0] * len(g), [0.0] * len(g))]
    rows, coefs = rs.walk_forward(g, feats)
    assert rows and all(abs(c) < 1e-9 for b in coefs.values() for c in b)
    assert all(abs(r["q"] - r["g"]["mkt"]) < 1e-9 for r in rows)
    sc = rs.score(rows)
    assert abs(sc["ll"] - sc["mkt_ll"]) < 1e-9


def test_walk_forward_never_uses_the_test_year_or_later():
    g = _games()
    feats = [[1.0, 0.0]] * len(g)
    rows, coefs = rs.walk_forward(g, feats)
    assert min(coefs) == rs.FIRST_TEST and all(r["g"]["year"] >= rs.FIRST_TEST for r in rows)
    # leaking the answer into one test year must not change that year's own coefficient
    g2 = [dict(x, y=1.0 - x["y"]) if x["year"] == 2024 else x for x in g]
    _, coefs2 = rs.walk_forward(g2, feats)
    assert coefs[2024] == coefs2[2024] and coefs[2023] == coefs2[2023]


def test_missing_rank_reads_pending_not_invented():
    g = _games(60)
    g[0]["ra"] = None
    assert rs.features(g)[0] is None
    assert rs.run(g[:20]).count("PENDING") == 1


def test_calibration_buckets_cover_both_sides():
    g = _games(500)
    assert sum(b[2] for b in rs.calibration(g)) == 2 * len(g)


def test_run_report_is_record_only():
    text = rs.run(_games())
    assert "Record only" in text and "Tries counted" in text
