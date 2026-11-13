"""engine/nfl_events.py, data/nfl_quarters.py, backtest/nfl_events_study.py (framework #588). Offline."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import nfl_events_study as study  # noqa: E402
from data import nfl_quarters as nq  # noqa: E402
from engine import nfl_events as ne  # noqa: E402


def _event(lh=(7, 3, 0, 10), la=(0, 14, 3, 0), done=True, score=None):
    fh, fa = (sum(lh), sum(la)) if score is None else score
    mk = lambda ha, ls, f, n: {"homeAway": ha, "score": str(f), "team": {"displayName": n}, "linescores": [{"value": v} for v in ls]}  # noqa: E731
    return {"id": "1", "date": "2025-09-07T17:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [mk("home", lh, fh, "H"), mk("away", la, fa, "A")]}]}


def test_parse_game():
    r = nq.parse_game(_event())
    assert r["r"][1] == [3, 14] and r["home"] == "H" and r["ot"] is False
    assert nq.parse_game(_event(lh=(7, 3, 0, 10, 6), la=(0, 14, 3, 0, 0)))["ot"] is True


def test_pending_not_guessed():
    assert nq.parse_game(_event(done=False)) is None
    assert nq.parse_game(_event(score=(99, 17))) is None             # quarters that do not add up are dropped
    assert nq.parse_game(_event(lh=(7, 3, 0), la=(0, 14, 3))) is None  # fewer than four quarters
    e = _event()
    e["competitions"][0]["competitors"][0]["linescores"][2] = {}
    assert nq.parse_game(e) is None


def test_shares_and_agreement():
    assert abs(sum(ne.SHARE_HOME) - 1) < 2e-3 and abs(sum(ne.SHARE_AWAY) - 1) < 2e-3
    r = ne.predict(24.0, 21.0)
    assert abs(sum(q["home_points"] for q in r["quarters"]) - 24.0) < 1e-2          # quarters add up to the game
    assert abs(sum(h["home_points"] + h["away_points"] for h in r["halves"]) - 45.0) < 1e-2
    assert r["shadow"] is True
    t = r["team_over"]["home"]
    assert t["17.5"] > t["20.5"] > t["23.5"] > t["26.5"]
    h = r["halves"][0]["over"]
    assert h["20.5"] > h["23.5"] > h["26.5"]


def test_from_total_keeps_the_board():
    r = ne.from_total(46.5, -3.5)
    assert abs(r["home_points"] + r["away_points"] - 46.5) < 1e-3
    assert abs((r["home_points"] - r["away_points"]) - 3.5) < 1e-3                   # keeps the spread
    assert abs(ne.from_total(46.5, 0)["home_points"] - ne.from_total(46.5, 0)["away_points"]) < 1e-3


def test_pending_never_invented():
    assert ne.predict(None, 20.0) is None and ne.predict(20.0, 0) is None
    assert ne.from_total(None, -3) is None and ne.from_total(44, None) is None and ne.from_total(10, -30) is None
    assert ne.fit_shares([]) is None and ne.Ratings([]).rates("A", "B") is None


def _games():
    rows = []
    teams = ["A", "B", "C", "D"]
    for day in range(220):
        for i, h in enumerate(teams):
            a = teams[(i + 1 + day % 3) % 4]
            if a == h:
                continue
            r = [[((day + i + n) % 3) * 3, ((day + n) % 4) * 2] for n in range(4)]
            rows.append({"id": len(rows), "date": (date(2023, 9, 1) + timedelta(days=day)).isoformat(), "home": h, "away": a, "r": r})
    return rows


def test_study_walk_forward_runs_and_purges():
    rows = _games()
    out = study.run(rows, 2023, 17.0, study.DEFAULT, collect=True)
    assert out["acc"], "no events scored"
    for p in ("q", "h", "team"):
        m, b, se, n = study.summarise(out["acc"], p)
        assert n > 0 and m > 0 and b > 0 and se >= 0
    first_day = min(r["date"] for r in rows)
    assert study.run([r for r in rows if r["date"] <= first_day], 2023, 17.0, study.DEFAULT)["acc"] == {}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
