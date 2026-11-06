"""Rugby totals study: no peeking, thin data is PENDING. No network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_totals_study as rt  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs, as_ = (40.0 if h == "A" else 15.0), 12.0
        out.append({"year": 2014 + i // 120, "home": h, "away": a, "hs": hs, "as": as_})
    return out


def test_replay_uses_only_past_games():
    g = _games()
    p = rt.replay(g, 8, 1.0)
    assert p[0] is None and p[10] is None            # nothing known yet
    g2 = [dict(x) for x in g]
    g2[-1]["hs"] = 999.0                             # changing the last result moves no earlier prediction
    assert rt.replay(g2, 8, 1.0)[:-1] == p[:-1]


def test_run_reports_and_counts_tries():
    text = rt.run(_games())
    assert "Settings tried: **9**" in text and "2020" in text


def test_thin_data_is_pending():
    assert "PENDING" in rt.run(_games(60))
