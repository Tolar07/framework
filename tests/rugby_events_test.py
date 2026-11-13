"""engine/rugby_events.py, data/rugby_events.py and backtest/rugby_events_study.py (framework #593). Offline."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import rugby_events_study as study  # noqa: E402
from data import rugby_events as data  # noqa: E402
from engine import rugby_events as re_  # noqa: E402


def _row(h1=(10.0, 6.0), h2=(13.0, 8.0), tries=(2.0, 1.0), conv=(2.0, 1.0), pens=(3.0, 2.0), drops=(0.0, 1.0)):
    pts = [5 * tries[i] + 2 * conv[i] + 3 * pens[i] + 3 * drops[i] for i in (0, 1)]
    return {"day": "2020-01-01", "home": "A", "away": "B", "h1": list(h1), "h2": list(h2), "pts": pts,
            "tries": list(tries), "conv": list(conv), "pens": list(pens), "drops": list(drops)}


def test_event_rates_rebuild_the_points():
    rows = [_row(), _row(tries=(3.0, 2.0), conv=(2.0, 2.0), pens=(1.0, 0.0), drops=(0.0, 0.0)), _row(tries=(0.0, 1.0), pens=(4.0, 3.0))]
    f = re_.fit(rows)
    rebuilt = sum(re_.POINTS[k] * f["rate"][k] for k in re_.POINTS)
    assert abs(rebuilt - 1.0) < 1e-9          # 5*tries + 2*conv + 3*pens + 3*drops = 1 point per point
    r = re_.predict(25.0, 20.0, f)
    assert r["shadow"] is True
    assert abs(r["first_half"]["home"] + r["second_half"]["home"] - 25.0) < 1e-2
    assert abs(r["tries"]["home"] * 5 + 2 * 25.0 * f["rate"]["conv"] + 3 * 25.0 * f["rate"]["pens"] + 3 * 25.0 * f["rate"]["drops"] - 25.0) < 0.05
    v = list(r["tries"]["total_over"].values())
    assert v == sorted(v, reverse=True)


def test_from_total_keeps_the_board_total_and_spread():
    f = re_.fit([_row(), _row(tries=(3.0, 1.0))])
    r = re_.from_total(46.0, -6.0, f)
    assert abs(r["home_points"] + r["away_points"] - 46.0) < 1e-2
    assert abs(r["home_points"] - r["away_points"] - 6.0) < 1e-2


def test_missing_inputs_read_pending_never_invented():
    f = re_.fit([_row()])
    assert re_.predict(None, 20.0, f) is None and re_.predict(20.0, 20.0, None) is None and re_.fit([]) is None
    assert re_.from_total(None, -3.0, f) is None and re_.from_total(40.0, None, f) is None
    only_halves = re_.fit([{"h1": [10.0, 6.0], "h2": [10.0, 6.0], "pts": [20.0, 12.0], "tries": None}])
    r = re_.predict(25.0, 20.0, only_halves)
    assert r["tries"] is None and r["penalty_goals"] is None and r["first_half"]["over"]


def _event(hs, as_, h1, a1, h2, a2, tries=(2, 1), pens=(1, 2), conv=(2, 1), drops=(0, 0), done=True):
    def comp(side, score, p1, p2, t, p, c, d):
        st = [("tries", t), ("penaltyGoals", p), ("conversionGoals", c), ("dropGoalsConverted", d), ("penaltyTries", 0)]
        return {"homeAway": side, "score": str(score), "team": {"displayName": side.upper()},
                "linescores": [{"period": 1, "value": p1}, {"period": 2, "value": p2}],
                "statistics": [{"name": n, "displayValue": str(v)} for n, v in st]}
    return {"date": "2014-03-01T15:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [comp("home", hs, h1, h2, tries[0], pens[0], conv[0], drops[0]),
                                              comp("away", as_, a1, a2, tries[1], pens[1], conv[1], drops[1])]}]}


def test_parse_keeps_only_real_halves_and_counts_that_rebuild_the_score():
    ok = data.parse_game(_event(13, 11, 6, 3, 7, 8), "X")              # 2 tries, 2 conv, 1 pen = 17? not 13 -> counts untrusted
    assert ok is not None and ok["tries"] is None and ok["h1"] == [6.0, 3.0]
    good = data.parse_game(_event(17, 15, 10, 6, 7, 9), "X")           # home 10+4+3 = 17, away 5+2+6 = 13? -> not equal 15
    assert good is not None and good["tries"] is None
    exact = data.parse_game(_event(17, 13, 10, 6, 7, 7), "X")
    assert exact["tries"] == [2.0, 1.0] and exact["pens"] == [1.0, 2.0]
    assert data.parse_game(_event(17, 13, 0, 0, 17, 13), "X") is None   # whole score in period 2: no real half split
    assert data.parse_game(_event(17, 13, 10, 6, 6, 7), "X") is None    # halves do not add up (extra time)
    assert data.parse_game(_event(17, 13, 10, 6, 7, 7, done=False), "X") is None


def test_study_reads_pending_with_thin_data_and_runs_with_enough():
    assert "PENDING" in study.render([], datetime(2026, 1, 1))
    games = []
    from datetime import date, timedelta
    names = ["A", "B", "C", "D", "E", "F"]
    for i in range(420):
        d = date(2014, 1, 1) + timedelta(days=i)
        g = _row(h1=(10.0 + i % 3, 6.0), h2=(10.0, 8.0 + i % 2))
        g.update({"day": d.isoformat(), "home": names[i % 6], "away": names[(i * 5 + 1) % 6 if (i * 5 + 1) % 6 != i % 6 else (i + 1) % 6]})
        g["r"] = [g["h1"], g["h2"]]
        games.append(g)
    r = study.run(games, 300, 340, 8.0, 10.0)
    assert r["acc"] and any(k.startswith("tries") for k in r["acc"])


if __name__ == "__main__":
    test_event_rates_rebuild_the_points()
    test_from_total_keeps_the_board_total_and_spread()
    test_missing_inputs_read_pending_never_invented()
    test_parse_keeps_only_real_halves_and_counts_that_rebuild_the_score()
    test_study_reads_pending_with_thin_data_and_runs_with_enough()
    print("OK")
