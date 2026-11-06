"""Rugby draw study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_draw_study as rd  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs = 20.0 if i % 25 == 0 else (30.0 if (h == "A" or i % 3 == 0) else 10.0)
        y = 0.5 if hs == 20.0 else 1.0 if hs > 20 else 0.0
        yr = 2014 + i // 120
        out.append({"year": yr, "day": f"{yr}-01-01", "home": h, "away": a, "hs": hs, "as": 20.0, "y": y,
                    "league": "URC" if i % 2 else "Top 14"})
    return out


def test_three_way_sums_to_one_and_is_capped():
    for e, d in ((0.5, 0.05), (0.9, 0.5), (0.1, 0.03), (0.6, 0.0)):
        p = rd.three_way(e, d)
        assert abs(sum(p) - 1) < 1e-9 and min(p) >= 0


def test_bucket_edges():
    assert [rd.bucket(e) for e in (0.5, 0.65, 0.9)] == [0, 1, 2]


def test_draw_rates_use_only_given_years():
    g = _games()
    probs = [0.5] * len(g)
    flat, rates = rd.draw_rates(g, probs, (2014, 2014))
    assert 0 < flat < 0.2 and len(rates) == 3


def test_run_and_pending():
    t = rd.run(_games())
    assert "Variants tried" in t and "2020" in t
    assert "PENDING" in rd.run(_games(300))
