"""Rugby rest-days study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_carryover_study as rr  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs = 30.0 if (h == "A" or i % 3 == 0) else 10.0
        yr = 2014 + i // 120
        out.append({"year": yr, "day": f"{yr}-{1 + (i % 120) // 10:02d}-{1 + i % 10:02d}", "home": h, "away": a,
                    "hs": hs, "as": 20.0, "y": 1.0 if hs > 20 else 0.0, "league": "URC" if i % 2 else "Top 14"})
    return out


def test_pull_only_after_a_long_break():
    hb = {"URC": 0.0}
    base = [{"day": "2020-01-01", "league": "URC", "home": "A", "away": "B", "y": 1.0},
            {"day": "2020-01-08", "league": "URC", "home": "A", "away": "C", "y": 1.0},
            {"day": "2020-06-01", "league": "URC", "home": "A", "away": "B", "y": 1.0}]
    # MIN_GAMES is 8, so compare the internal ratings through a low bar
    old = rr.rb.MIN_GAMES
    rr.rb.MIN_GAMES = 0
    try:
        short = [dict(x) for x in base]
        short[2]["day"] = "2020-01-15"
        assert rr.replay(short, hb, 0.0) == rr.replay(short, hb, 0.5)
        assert rr.replay(base, hb, 0.0)[2] != rr.replay(base, hb, 0.5)[2]
    finally:
        rr.rb.MIN_GAMES = old


def test_run_and_pending():
    assert "Settings tried" in rr.run(_games()) and "2020" in rr.run(_games())
    assert "PENDING" in rr.run(_games(300))
