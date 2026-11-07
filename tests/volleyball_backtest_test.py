"""Volleyball study: no network, thin data is PENDING, non-final scores dropped."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import volleyball_backtest as vb  # noqa: E402


def _ev(day, h, a, hs, as_, done=True):
    return {"date": day + "T19:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": str(hs), "team": {"displayName": h}},
                {"homeAway": "away", "score": str(as_), "team": {"displayName": a}}]}]}


def test_load_filters_and_survives_failures():
    def fetch(d):
        if d == "20170901":
            raise OSError("down")
        return [_ev("2018-09-02", "X", "Y", 3, 1), _ev("2018-09-02", "Y", "X", 1, 3),   # same pair, same day
                _ev("2018-09-03", "X", "Y", 2, 1), _ev("2018-09-04", "X", "Y", 0, 0, done=False)]
    g = vb.load(fetch, ["20170901", "20180902"])
    assert len(g) == 1 and g[0]["y"] == 1.0 and g[0]["year"] == 2018


def _games(n=2500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 2) % 4]
        hs, as_ = (3, 1) if (h == "A" or i % 3 == 0) else (0, 3)
        yr = 2016 + i // 250
        out.append({"year": yr, "day": f"{yr}-10-01", "home": h, "away": a, "hs": float(hs), "as": float(as_),
                    "y": float(hs > as_), "league": "NCAA women"})
    return out


def test_run_and_pending():
    text = vb.run(_games())
    assert "Settings tried" in text and "Table tennis" in text and "PENDING" in text and "Record only" in text
    assert "PENDING: too little tuning data" in vb.run(_games(200))
