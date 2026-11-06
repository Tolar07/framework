"""Rugby backtest: parser, Elo replay, no-peeking split, report. No network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_backtest as rb  # noqa: E402


def _ev(day, h, a, hs, as_, done=True):
    return {"date": day + "T15:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": str(hs), "team": {"displayName": h}},
                {"homeAway": "away", "score": str(as_), "team": {"displayName": a}}]}]}


def _events():
    teams = ["A", "B", "C", "D"]
    evs = []
    for i in range(1400):
        y = 2014 + i // 120
        d = f"{y}-{1 + (i % 120) // 10:02d}-{1 + i % 10:02d}"
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        evs.append(_ev(d, h, a, 30 if h == "A" else 10, 12 if a == "A" else 15))
    return evs


def _fetch_one(lg, y):
    return _events() if lg == "267979" else []


def test_parse_skips_unfinished_and_bad():
    evs = [_ev("2020-01-01", "A", "B", 10, 3), _ev("2020-01-02", "A", "B", 0, 0, done=False), {"x": 1}]
    g = rb.parse(evs, "URC")
    assert len(g) == 1 and g[0]["home"] == "A" and g[0]["hs"] == 10.0


def test_load_dedupes_and_orders():
    g = rb.load(_fetch_one)
    days = [x["day"] for x in g]
    assert days == sorted(days)
    assert len({(x["day"], x["home"], x["away"]) for x in g}) == len(g)


def test_replay_no_lookahead_and_min_games():
    g = rb.load(_fetch_one)
    p1 = rb.replay(g, 24.0, 0.0)
    assert p1[0] is None and any(p is not None for p in p1)
    g2 = [dict(x) for x in g]
    g2[-1]["y"] = 1.0 - g2[-1]["y"]          # changing the LAST result must not move any earlier chance
    assert rb.replay(g2, 24.0, 0.0)[:-1] == p1[:-1]


def test_run_reports_heldout_and_pending_safe():
    text = rb.run(rb.load(_fetch_one))
    assert "Rugby walk-forward backtest" in text and "Settings tried: **9**" in text
    assert "Record only" in text
