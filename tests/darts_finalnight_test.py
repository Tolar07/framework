from datetime import UTC, datetime

from backtest import darts_finalnight_study as s


def _g(day, i, h, a, w, t="T1"):
    d = f"2025-01-{day:02d}"
    return {"date": d, "kickoff_utc": f"{d}-{i:03d}", "home": h, "away": a, "winner": w, "tournament": t}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_factor_one_is_identity_and_only_final_nights_move():
    assert abs(s.shifted(0.7, True, 1.0) - 0.7) < 1e-9
    assert abs(s.shifted(0.7, False, 0.5) - 0.7) < 1e-9
    assert s.shifted(0.7, True, 0.5) < 0.7 < s.shifted(0.7, True, 1.5)


def test_last_night_is_per_tournament():
    games = [_g(1, 0, "A A", "B B", 1), _g(5, 0, "A A", "B B", 1), _g(2, 0, "A A", "B B", 1, "T2")]
    assert s.last_nights(games) == {("T1", "2025-01-05"), ("T2", "2025-01-02")}


def test_scored_flags_final_night_and_small_sample_reads_pending():
    games = [_g(1, 0, "A A", "B B", 1), _g(5, 0, "A A", "B B", 0)]
    assert [r[1] for r in s.scored(games, min_games=0)] == [False, True]
    out = s.render(games, datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
