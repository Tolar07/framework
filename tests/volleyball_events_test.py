"""engine/volleyball_events.py, data/volleyball_sets.py and backtest/volleyball_events_study.py (framework #591). Offline."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import volleyball_events_study as study  # noqa: E402
from data import volleyball_sets as vs  # noqa: E402
from engine import volleyball_events as ve  # noqa: E402

HIST = {3: sorted([150 + i % 12 for i in range(60)]), 4: sorted([200 + i % 15 for i in range(60)]),
        5: sorted([235 + i % 15 for i in range(60)])}


def test_ladder_agrees_with_the_board():
    for m in (0.0, 0.1, 0.2):
        for p in (0.1, 0.35, 0.5, 0.72, 0.9):
            r = ve.predict(p, m, HIST)
            assert abs(r["match_win"] - p) < 2e-3
            assert abs(sum(r["score"].values()) - 1) < 1e-3
            assert r["shadow"] is True
            assert abs(r["sets_over"]["3.5"] - sum(r["score"][k] for k in ("3-1", "1-3", "3-2", "2-3"))) < 2e-3
            assert r["handicap_cover"]["home -1.5"] <= r["match_win"] + 2e-3
            pts = list(r["points_over"].values())
            assert pts == sorted(pts, reverse=True) and all(0 < v < 1 for v in pts)


def test_pending_never_invented():
    assert ve.predict(None, 0.1, HIST) is None and ve.predict(0.0, 0.1, HIST) is None and ve.predict(1.0, 0.1, HIST) is None
    assert ve.predict(0.6, 0.1, None)["points_over"] is None          # no history: sets numbers only
    assert ve.predict(0.6, 0.1, {3: [150] * 5, 4: [], 5: []})["points_over"] is None


def _event(hs_sets, as_sets, hs, as_, done=True):
    def comp(side, lines, score):
        return {"homeAway": side, "score": str(score), "team": {"displayName": side + "T"},
                "linescores": [{"value": float(v)} for v in lines]}
    return {"date": "2024-10-01T18:00Z", "status": {"type": {"completed": done}},
            "competitions": [{"competitors": [comp("home", hs_sets, hs), comp("away", as_sets, as_)]}]}


def test_parse_keeps_only_consistent_finished_matches():
    ok = vs.parse_event(_event([25, 20, 25, 25], [20, 25, 23, 18], 3, 1))
    assert ok and ok["sets"] == [[25, 20], [20, 25], [25, 23], [25, 18]]
    assert vs.parse_event(_event([25, 20, 25, 25], [20, 25, 23, 18], 3, 1, done=False)) is None
    assert vs.parse_event(_event([25, 20, 25], [20, 25, 23], 3, 1)) is None      # set count != sets won
    assert vs.parse_event(_event([25, 20, 25, 25], [20, 25, 23, 18], 2, 2)) is None  # not best-of-5 shaped
    assert vs.parse_event(_event([25, 25, 25], [20, 20, 20], 2, 1)) is None        # winners disagree with sets won
    assert vs.parse_event({}) is None


def _rows():
    names = list("ABCDEFGH")
    rows = []
    for day in range(500):
        d = date(2019, 1, 1) + timedelta(days=day)
        i, j = day % 8, (day * 3 + 1) % 8
        if i == j:
            continue
        n = 3 + day % 3
        hs = 3 if day % 5 else 0 if n == 3 else 3
        hs, as_ = (3, n - 3) if (day % 5) else (n - 3, 3)
        sets = [[25, 20 + k % 4] for k in range(hs)] + [[18 + k % 5, 25] for k in range(as_)]
        if n == 5:
            sets[-1] = [15, 12] if hs == 3 else [12, 15]
        rows.append({"day": d.isoformat(), "home": names[i], "away": names[j], "hs": hs, "as": as_, "sets": sets})
    return rows


def test_study_walk_forward_runs_and_purges():
    rows = _rows()
    res = study.run(rows, momenta=(0.0, 0.1), min_hist=40)
    assert res[0.1], "no match scored"
    m, b, sem, n = study.summarise(res[0.1], "sc_m", "sc_b")
    assert n > 0 and m > 0 and b > 0 and sem >= 0
    assert study.run(rows[:30], momenta=(0.1,), min_hist=40)[0.1] == []
    assert study.run([], momenta=(0.1,))[0.1] == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
