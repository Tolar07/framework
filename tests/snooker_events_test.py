"""engine/snooker_events.py and backtest/snooker_events_study.py (framework #590). Offline."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import snooker_events_study as study  # noqa: E402
from engine import snooker_events as se  # noqa: E402


def test_ladder_agrees_with_the_board():
    for t in (4, 5, 6, 10, 18):
        for p in (0.1, 0.35, 0.5, 0.72, 0.9):
            r = se.predict(p, t)
            assert abs(r["match_win"] - p) < 1e-3                     # the ladder IS the board's win chance
            assert abs(sum(r["score"].values()) - 1) < 2e-3 * t       # cells add to 1 (rounding)
            assert r["shadow"] is True and r["centuries"] is None
            tot = list(r["total_over"].values())
            assert tot == sorted(tot, reverse=True)                  # longer line, smaller over chance
            assert len(tot) == t - 1


def test_totals_and_handicap_are_sums_of_score_cells():
    r = se.predict(0.7, 5)
    assert abs(r["total_over"]["5.5"] - sum(v for k, v in r["score"].items() if sum(map(int, k.split("-"))) > 5.5)) < 2e-3
    assert r["handicap_cover"]["-1.5"] >= r["match_win"] - 2e-3          # covering -1.5 includes every win
    assert r["handicap_cover"]["2.5"] <= r["handicap_cover"]["1.5"] <= r["handicap_cover"]["-1.5"]


def test_pending_never_invented():
    assert se.predict(None, 5) is None and se.predict(0.6, None) is None
    assert se.predict(0.0, 5) is None and se.predict(1.0, 5) is None and se.predict(0.6, 1) is None


def _rows():
    names = ["A", "B", "C", "D", "E", "F"]
    rows = []
    for day in range(400):
        d = date(2020, 1, 1) + timedelta(days=day)
        i, j = day % 6, (day * 5 + 1) % 6
        if i == j:
            continue
        w = (day // 2) % 3 != 0
        hf, af = (4, day % 4) if w else (day % 4, 4)
        rows.append({"date": d.isoformat(), "kickoff_utc": d.isoformat() + "-00-%04d" % day, "home": names[i], "away": names[j],
                     "home_frames": hf, "away_frames": af, "winner": 1 if w else 2})
    return rows


def test_study_walk_forward_runs_and_purges():
    rows = _rows()
    res = study.run(rows, shrinks=(1.0, 0.8), min_format=20)
    assert res[1.0]["rows"], "no match scored"
    m, b, se_, n = study.summarise(res[1.0]["rows"], "sc_m", "sc_b")
    assert n > 0 and m > 0 and b > 0 and se_ >= 0
    # no match is scored before enough purged history exists
    assert study.run(rows[:30], shrinks=(1.0,), min_format=20)[1.0]["rows"] == []
    assert study.run([], shrinks=(1.0,))[1.0]["rows"] == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
