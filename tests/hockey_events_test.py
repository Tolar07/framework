"""engine/hockey_events.py, data/nhl_periods.py, backtest/hockey_events_study.py (framework #586). Offline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import hockey_events_study as study  # noqa: E402
from data import nhl_periods as np_  # noqa: E402
from engine import hockey_events as he  # noqa: E402
from engine import hockey_periods as hp  # noqa: E402


def _pbp():
    def play(n, typ, owner, ptype="REG"):
        return {"periodDescriptor": {"number": n, "periodType": ptype}, "typeDescKey": typ,
                "details": {"eventOwnerTeamId": owner}}
    plays = [play(1, "shot-on-goal", 1), play(1, "goal", 2), play(2, "faceoff", 1), play(2, "shot-on-goal", 2),
             play(3, "goal", 1), play(3, "missed-shot", 2), play(4, "goal", 1, "OT")]
    return {"id": 7, "gameState": "OFF", "startTimeUTC": "2025-01-02T00:00:00Z",
            "homeTeam": {"id": 1, "abbrev": "AAA"}, "awayTeam": {"id": 2, "abbrev": "BBB"}, "plays": plays}


def test_parse_pbp_counts_regulation_only():
    r = np_.parse_pbp(_pbp())
    assert r["g"] == [[0, 1], [0, 0], [1, 0]] and r["s"] == [[1, 1], [0, 1], [1, 0]]   # goal counts as a shot; OT excluded
    assert r["home"] == "AAA" and r["date"] == "2025-01-02"


def test_parse_pbp_pending_not_guessed():
    p = _pbp()
    p["gameState"] = "LIVE"
    assert np_.parse_pbp(p) is None
    p = _pbp()
    p["plays"] = [x for x in p["plays"] if x["periodDescriptor"]["number"] != 2]
    assert np_.parse_pbp(p) is None


def test_agrees_with_the_board():
    r = he.from_board(1.62, 4.6, 5.0)
    ph, pd, pa = hp.devig(1.62, 4.6, 5.0)
    lh, la = hp.solve_rates(ph, pa, pd)
    assert abs(r["home_goals"] - lh) < 1e-3 and abs(r["away_goals"] - la) < 1e-3
    h, d, a = hp.three_way(lh, la)
    assert max(abs(h - ph), abs(d - pd), abs(a - pa)) < 1e-3
    assert abs(sum(p["home_goals"] for p in r["periods"]) - r["home_goals"]) < 2e-4          # periods add up to the game
    assert abs(sum(p["away_goals"] for p in r["periods"]) - r["away_goals"]) < 2e-4


def test_shape():
    r = he.predict(3.2, 2.8, 30, 28)
    p1 = r["periods"][0]
    assert p1["over"]["0.5"] > p1["over"]["1.5"] > p1["over"]["2.5"]
    assert abs(p1["scoreless"] - (1 - p1["over"]["0.5"])) < 1e-3
    assert r["team_over"]["home"]["1.5"] > r["team_over"]["home"]["3.5"]
    assert r["periods"][0]["home_shots"] < r["periods"][1]["home_shots"] + 1
    assert r["shadow"] is True


def test_pending_never_invented():
    assert he.predict(None, 2.0) is None and he.predict(2.0, 0) is None
    assert he.from_board(None, 4.0, 3.0) is None and he.from_board(1.0, 4.0, 3.0) is None
    assert he.team_rates([], "A", "B") is None and he.fit_shares([]) is None


def _games():
    rows = []
    teams = ["A", "B", "C", "D"]
    day = 0
    for rep in range(120):
        for i, h in enumerate(teams):
            a = teams[(i + 1 + rep % 3) % 4]
            if a == h:
                continue
            gh = 1 + (h == "A") + (rep % 3 == 0)
            g = [[gh % 2 + (n == 0), (n == 1) + (a == "D")] for n in range(3)]
            s = [[9 + n, 8 + n] for n in range(3)]
            rows.append({"id": len(rows), "date": (__import__("datetime").date(2023, 10, 1)
                         + __import__("datetime").timedelta(days=day)).isoformat(), "home": h, "away": a, "g": g, "s": s})
        day += 1
    return rows


def test_team_rates_and_shares():
    rows = _games()
    sh = he.fit_shares(rows)
    assert abs(sum(sh[0]) - 1) < 1e-9 and abs(sum(sh[1]) - 1) < 1e-9
    lh, la = he.team_rates(rows, "A", "B", 20)
    assert lh > 0 and la > 0
    lh2, _ = he.team_rates(rows, "A", "B", 1e9)               # huge shrink -> league average
    lh3, _ = he.team_rates(rows, "C", "B", 1e9)
    assert abs(lh2 - lh3) < 1e-6


def test_study_walk_forward_runs_and_purges():
    rows = _games()
    out = study.run(rows, 2023, 20.0, 60.0, collect=True)
    assert out["acc"], "no events scored"
    m, b, se, n = study.summarise(out["acc"], "goals")
    assert n > 0 and m > 0 and b > 0 and se >= 0
    # a game is never predicted from its own day or the day before: first scored day has >=2 prior days of history
    first_day = min(r["date"] for r in rows)
    assert study.run([r for r in rows if r["date"] <= first_day], 2023, 20.0, 60.0)["acc"] == {}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
