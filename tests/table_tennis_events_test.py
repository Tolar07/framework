"""engine/table_tennis_events.py, data/table_tennis_games.py, backtest/table_tennis_events_study.py (framework #594). Offline."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import table_tennis_events_study as study  # noqa: E402
from backtest import volleyball_events_study as vstudy  # noqa: E402
from data import table_tennis_games as tt  # noqa: E402
from engine import table_tennis_events as te  # noqa: E402

HIST = {3: sorted([33 + i % 8 for i in range(60)]), 4: sorted([44 + i % 10 for i in range(60)]),
        5: sorted([55 + i % 10 for i in range(60)])}
HEAD = "X,Date,Time,Player1,Player2,Sets_P1,Sets_P2,P1_G1,P2_G1,P1_G2,P2_G2,P1_G3,P2_G3,P1_G4,P2_G4,P1_G5,P2_G5,HomeWinner\n"


def test_ladder_agrees_with_the_board():
    for p in (0.1, 0.35, 0.5, 0.72, 0.9):
        r = te.predict(p, 0.1, HIST)
        assert abs(r["match_win"] - p) < 2e-3 and abs(sum(r["score"].values()) - 1) < 1e-3 and r["shadow"] is True
        assert abs(r["games_over"]["3.5"] - sum(r["score"][k] for k in ("3-1", "1-3", "3-2", "2-3"))) < 2e-3
        assert "sets_over" not in r
        pts = list(r["points_over"].values())
        assert pts == sorted(pts, reverse=True) and all(0 < v < 1 for v in pts)


def test_pending_never_invented():
    assert te.predict(None, 0.1, HIST) is None and te.predict(0.0, 0.1, HIST) is None and te.predict(1.0, 0.1, HIST) is None
    assert te.predict(0.6, 0.1, None)["points_over"] is None
    assert te.predict(0.6, 0.1, {3: [40] * 5, 4: [], 5: []})["points_over"] is None


def test_parse_keeps_only_consistent_matches():
    ok = HEAD + "1,6/10/2022,1:05:00,A A.,B B.,3,1,11,8,11,6,6,11,11,8,NA,NA,1\n"
    got = tt.parse(ok)
    assert got[0]["sets"] == [[11, 8], [11, 6], [6, 11], [11, 8]] and got[0]["day"] == "2022-06-10"
    na = HEAD + "2,6/10/2022,1:05:00,A A.,B B.,3,1,11,8,NA,NA,6,11,11,8,NA,NA,1\n"      # NA inside a played game
    wrong = HEAD + "3,6/10/2022,1:05:00,A A.,B B.,3,1,11,8,11,6,11,6,11,8,NA,NA,1\n"   # winners disagree with 3-1
    bo3 = HEAD + "4,6/10/2022,1:05:00,A A.,B B.,2,0,11,8,11,6,NA,NA,NA,NA,NA,NA,1\n"   # not best-of-5
    extra = HEAD + "5,6/10/2022,1:05:00,A A.,B B.,3,0,11,8,11,6,11,6,11,8,NA,NA,1\n"   # a 4th game after 3-0
    for bad in (na, wrong, bo3, extra):
        assert tt.parse(bad) == []
    assert tt.load(get=lambda: ok)[0]["home"] == "A A."


def _rows():
    names = list("ABCDEFGHIJ")
    rows = []
    for day in range(40):
        d = date(2022, 6, 1) + timedelta(days=day)
        for k in range(30):
            i, j = (day + k) % 10, (day * 3 + k * 7 + 1) % 10
            if i == j:
                continue
            n = 3 + (day + k) % 3
            hs, as_ = (3, n - 3) if (day + k) % 5 else (n - 3, 3)
            sets = [[11, 5 + k % 5] for _ in range(hs)] + [[4 + k % 6, 11] for _ in range(as_)]
            rows.append({"day": d.isoformat(), "home": names[i], "away": names[j], "hs": hs, "as": as_, "sets": sets})
    return rows


def test_study_walk_forward_runs_and_reports():
    rows = _rows()
    now = datetime(2026, 11, 13, tzinfo=UTC)
    res = vstudy.run(rows, momenta=(0.0, 0.1), min_hist=100)
    assert res[0.1]
    assert vstudy.run(rows[:20], momenta=(0.1,), min_hist=100)[0.1] == []
    text = study.render(rows, now, min_hist=100, min_rows=100)
    assert "Exact game score" in text and "Held-out matches" in text
    assert "NO DATA - PENDING" in study.render(rows[:10], now)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
