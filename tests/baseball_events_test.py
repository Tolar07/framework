"""engine/baseball_events.py, data/mlb_innings.py, backtest/baseball_events_study.py (framework #587). Offline."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import baseball_events_study as study  # noqa: E402
from data import mlb_innings as mi  # noqa: E402
from engine import baseball_events as be  # noqa: E402


def _game(runs_home=(1, 0, 0, 2, 0, 0, 0, 0, None), runs_away=(0, 0, 3, 0, 0, 0, 0, 1, 0), state="Final", n=9):
    inn = []
    for i in range(n):
        h = runs_home[i] if i < len(runs_home) else 0
        a = runs_away[i] if i < len(runs_away) else 0
        inn.append({"num": i + 1, "home": {"runs": h} if h is not None else {}, "away": {"runs": a}})
    return {"gamePk": 5, "gameType": "R", "officialDate": "2025-05-01", "status": {"abstractGameState": state},
            "teams": {"home": {"team": {"name": "H"}}, "away": {"team": {"name": "A"}}}, "linescore": {"innings": inn}}


def test_parse_game():
    r = mi.parse_game(_game())
    assert r["r"][3] == [2, 0] and r["r"][8] == [0, 0]          # unplayed bottom 9th is a true zero
    assert r["home"] == "H" and r["date"] == "2025-05-01"


def test_parse_pending_not_guessed():
    assert mi.parse_game(_game(state="Live")) is None
    assert mi.parse_game(_game(n=7)) is None                    # shortened game
    g = _game()
    g["linescore"]["innings"][2]["home"] = {}                    # missing count mid-game
    assert mi.parse_game(g) is None
    g = _game()
    g["gameType"] = "S"
    assert mi.parse_game(g) is None


def test_shares_and_agreement():
    assert abs(sum(be.SHARE_HOME) - 1) < 2e-3 and abs(sum(be.SHARE_AWAY) - 1) < 2e-3
    r = be.predict(4.6, 4.2)
    assert abs(sum(i["home_runs"] for i in r["innings"]) - r["home_runs"]) < 1e-3     # innings add up to the game
    assert r["first5"]["home_runs"] < r["home_runs"] and r["shadow"] is True
    f = r["first5"]["over"]
    assert f["3.5"] > f["4.5"] > f["5.5"]
    t = r["team_over"]["home"]
    assert t["2.5"] > t["3.5"] > t["4.5"]
    assert r["innings"][0]["scoreless"] > 0.3                                         # clumped: not the Poisson 0.34 or lower


def test_from_total_keeps_the_board():
    r = be.from_total(8.8, 0.60)
    assert abs(r["home_runs"] + r["away_runs"] - 8.8) < 1e-3 and r["home_runs"] > r["away_runs"]
    even = be.from_total(8.8, 0.5)
    assert abs(even["home_runs"] - even["away_runs"]) < 1e-3


def test_pending_never_invented():
    assert be.predict(None, 4.0) is None and be.predict(4.0, 0) is None
    assert be.from_total(None, 0.5) is None and be.from_total(8.0, None) is None and be.from_total(8.0, 1.0) is None
    assert be.fit_shares([]) is None and be.Ratings([]).rates("A", "B") is None


def _games():
    rows = []
    teams = ["A", "B", "C", "D"]
    for day in range(160):
        for i, h in enumerate(teams):
            a = teams[(i + 1 + day % 3) % 4]
            if a == h:
                continue
            r = [[(day + i + n) % 2, (day + n) % 3 == 0] for n in range(9)]
            rows.append({"id": len(rows), "date": (date(2023, 4, 1) + timedelta(days=day)).isoformat(), "home": h, "away": a, "r": r})
    return rows


def test_ratings_and_shares():
    rows = _games()
    sh = be.fit_shares(rows)
    assert abs(sum(sh[0]) - 1) < 1e-9 and abs(sum(sh[1]) - 1) < 1e-9
    mh, ma = be.Ratings(rows).rates("A", "B", 30)
    assert mh > 0 and ma > 0
    a, _ = be.Ratings(rows).rates("A", "B", 1e9)               # huge shrink -> league average
    c, _ = be.Ratings(rows).rates("C", "B", 1e9)
    assert abs(a - c) < 1e-6


def test_study_walk_forward_runs_and_purges():
    rows = _games()
    out = study.run(rows, 2023, 30.0, 8.0, collect=True)
    assert out["acc"], "no events scored"
    m, b, se, n = study.summarise(out["acc"], "f5")
    assert n > 0 and m > 0 and b > 0 and se >= 0
    first_day = min(r["date"] for r in rows)
    assert study.run([r for r in rows if r["date"] <= first_day], 2023, 30.0, 8.0)["acc"] == {}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
