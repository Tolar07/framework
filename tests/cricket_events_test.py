"""engine/cricket_events.py, data/cricket_overs.py, backtest/cricket_events_study.py (framework #589). Offline."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import cricket_events_study as study  # noqa: E402
from data import cricket_overs as co  # noqa: E402
from engine import cricket_events as ce  # noqa: E402


def _match(overs=20, per_over=(6, 6, 6, 6, 6, 6), wk_at=(), teams=("A", "B"), venue="V", bat="A", n_overs=None):
    n_overs = overs if n_overs is None else n_overs
    ov = []
    for o in range(n_overs):
        dl = []
        for b in range(6):
            d = {"runs": {"total": 1}}
            if (o, b) in wk_at:
                d["wickets"] = [{"player_out": "x"}]
            dl.append(d)
        ov.append({"over": o, "deliveries": dl})
    return {"info": {"venue": venue, "teams": list(teams), "dates": ["2024-06-01"], "overs": overs},
            "innings": [{"team": bat, "overs": ov}]}


def test_parse_blocks_add_up():
    r = co.parse_match(_match(), "T20", 20, (6, 15))
    assert r["blocks"] == [36, 54, 30] and sum(r["blocks"]) == 120 and r["bat"] == "A" and r["bowl"] == "B" and r["wk"] == 0
    r = co.parse_match(_match(overs=50), "ODI", 50, (10, 40))
    assert r["blocks"] == [60, 180, 60]


def test_pending_not_guessed():
    assert co.parse_match(_match(n_overs=12), "T20", 20, (6, 15)) is None            # shortened first innings
    assert co.parse_match(_match(overs=20), "T20", 50, (10, 40)) is None             # wrong format length
    assert co.parse_match(_match(venue=None), "T20", 20, (6, 15)) is None
    assert co.parse_match({"info": {}}, "T20", 20, (6, 15)) is None
    all_out = _match(n_overs=15, wk_at={(o, 0) for o in range(10)})                  # all out inside 15 overs counts
    assert co.parse_match(all_out, "T20", 20, (6, 15))["wk"] == 10


def test_blocks_agree_with_the_innings():
    for fmt in ("T20", "ODI"):
        assert abs(sum(ce.SHARES[fmt]) - 1) < 2e-3
        r = ce.predict(fmt, 160.0 if fmt == "T20" else 270.0, 7.0)
        assert abs(sum(b["runs"] for b in r["blocks"]) - r["runs"]) < 0.02
        assert r["shadow"] is True
        t = list(r["total_over"].values())
        assert t == sorted(t, reverse=True)
        w = list(r["wickets"]["over"].values())
        assert w == sorted(w, reverse=True)


def test_from_total_keeps_the_board():
    r = ce.from_total("T20", 172.5)
    assert r["runs"] == 172.5 and r["wickets"] is None


def test_pending_never_invented():
    assert ce.predict("T20", None) is None and ce.predict("T20", 0) is None and ce.predict("Test", 300) is None
    assert ce.from_total("ODI", None) is None
    assert ce.fit_shares([]) is None and ce.Ratings([]).rates("A", "B", "V") is None
    assert ce.predict("T20", 150, 0)["wickets"] is None


def _rows():
    rows = []
    teams = ["A", "B", "C", "D"]
    for day in range(300):
        for i, b in enumerate(teams):
            o = teams[(i + 1 + day % 3) % 4]
            if o == b:
                continue
            rows.append({"id": str(len(rows)), "date": (date(2023, 1, 1) + timedelta(days=day)).isoformat(), "fmt": "T20",
                         "venue": "V" + str(day % 2), "bat": b, "bowl": o,
                         "blocks": [30 + (day + i) % 9, 50 + (day * 3 + i) % 15, 40 + (day + 2 * i) % 11], "wk": (day + i) % 9})
    return rows


def test_study_walk_forward_runs_and_purges():
    rows = _rows()
    out = study.run(rows, "T20", 2023, 10.0, 10.0, {"total runs": 40.0, "over-block runs": 20.0}, 20.0, collect=True)
    assert out["acc"], "no events scored"
    for p in ("total", "block", "wk"):
        m, b, se, n = study.summarise(out["acc"], p)
        assert n > 0 and m > 0 and b > 0 and se >= 0
    first_day = min(r["date"] for r in rows)
    early = [r for r in rows if r["date"] <= first_day]
    assert study.run(early, "T20", 2023, 10.0, 10.0, {"total runs": 40.0, "over-block runs": 20.0}, 20.0)["acc"] == {}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "OK")
