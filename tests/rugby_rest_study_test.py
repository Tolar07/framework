"""Rugby rest-days study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_rest_study as rr  # noqa: E402


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


def test_rest_gap_uses_only_the_past():
    g = [{"day": "2024-01-01", "home": "A", "away": "B"}, {"day": "2024-01-04", "home": "A", "away": "C"},
         {"day": "2024-01-11", "home": "B", "away": "A"}]
    assert rr.rest_gap(g) == [0, 3 - 7, 10 - 7]


def test_rest_term_changes_chances():
    g = _games()
    hb = {"URC": 70.0, "Top 14": 70.0}
    gaps = rr.rest_gap(g)
    assert rr.replay(g, hb, 0.0, gaps) != rr.replay(g, hb, 8.0, gaps)


def test_run_and_pending():
    assert "Settings tried" in rr.run(_games()) and "2020" in rr.run(_games())
    assert "PENDING" in rr.run(_games(300))
