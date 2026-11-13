"""engine/darts_events.py and backtest/darts_events_study.py (framework #592). Offline."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import darts_events_study as study  # noqa: E402
from engine import darts_events as de  # noqa: E402


def test_ladder_agrees_with_the_board():
    for p in (0.1, 0.35, 0.5, 0.72, 0.9):
        r = de.predict(p, 6)
        assert abs(r["match_win"] - p) < 1e-3
        assert abs(sum(r["score"].values()) - 1) < 0.02
        assert r["shadow"] is True
        v = list(r["total_legs_over"].values())
        assert v == sorted(v, reverse=True) and len(v) == 5


def test_180s_and_checkouts_pending_never_invented():
    r = de.predict(0.6, 6)
    assert r["total_180s"] is None and r["most_180s"] is None and r["checkouts"] is None
    assert de.predict(None, 6) is None and de.predict(0.6, None) is None and de.predict(1.0, 6) is None


def test_study_runs_and_reads_pending_without_data(tmp_path):
    names = ["A", "B", "C", "D", "E", "F"]
    rows = []
    for day in range(400):
        d = date(2023, 1, 1) + timedelta(days=day)
        i, j = day % 6, (day * 5 + 1) % 6
        if i != j:
            w = (day // 2) % 3 != 0
            rows.append({"date": d.isoformat(), "kickoff_utc": d.isoformat() + "-%04d" % day, "home": names[i],
                         "away": names[j], "home_frames": 6 if w else day % 6, "away_frames": day % 6 if w else 6})
    res = study.ss.run(rows, shrinks=(1.0,), min_format=20)
    assert res[1.0]["rows"]
    assert "NO DATA - PENDING" in study.render([], datetime(2026, 1, 1))


if __name__ == "__main__":
    import tempfile
    test_ladder_agrees_with_the_board()
    test_180s_and_checkouts_pending_never_invented()
    test_study_runs_and_reads_pending_without_data(Path(tempfile.gettempdir()))
    print("OK")
