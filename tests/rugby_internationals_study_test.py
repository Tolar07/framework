"""Rugby internationals study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_internationals_study as ris  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 2) % 4]
        hs = 30.0 if (h == "A" or i % 3 == 0) else 10.0
        yr = 2014 + i // 120
        out.append({"year": yr, "day": f"{yr}-01-01", "home": h, "away": a, "hs": hs, "as": 20.0,
                    "y": 1.0 if hs > 20 else 0.0, "league": "Test Match"})
    return out


def _ev(day, h, a, hs, as_, done=True):
    return {"date": day + "T15:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": str(hs), "team": {"displayName": h}},
                {"homeAway": "away", "score": str(as_), "team": {"displayName": a}}]}]}


def test_load_dedupes_and_skips_failures():
    def fetch(lg, y):
        if y == 2015:
            raise OSError("down")
        return [_ev(f"{y}-03-01", "X", "Y", 20, 10), _ev(f"{y}-03-01", "Y", "X", 20, 10, done=False)]
    g = ris.load(fetch)
    assert g and all(x["y"] in (0.0, 0.5, 1.0) for x in g)
    assert len({(x["day"], x["home"], x["away"]) for x in g}) == len(g)
    assert not any(x["year"] == 2015 for x in g)


def test_run_and_pending():
    text = ris.run(_games())
    assert "Settings tried" in text and "2020" in text and "Record only" in text
    assert "PENDING" in ris.run(_games(300))
