from datetime import UTC, datetime

from backtest import darts_streak_study as s


def _g(i, h, a, w):
    return {"date": "2025-01-01", "kickoff_utc": f"2025-01-01-{i:03d}", "home": h, "away": a, "winner": w,
            "home_sets": 6, "away_sets": 3}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_step_runs():
    assert s._step(0, 1) == 1 and s._step(1, 1) == 2 and s._step(2, -1) == -1
    assert s._step(-2, -1) == -3 and s._step(3, 0) == 0


def test_uses_earlier_matches_only():
    games = [_g(0, "A A", "B B", 1), _g(1, "A A", "C C", 1), _g(2, "A A", "B B", 2)]
    rows = s.scored(games, 2, min_games=0)
    assert rows[0][1] == 0.0    # nothing earlier
    assert rows[1][1] == 0.0    # A on 1 win only (< 2)
    assert rows[2][1] == 1.0    # A on 2 straight wins; B lost once (0)


def test_small_sample_reads_pending():
    out = s.render([_g(0, "A A", "B B", 1), _g(1, "A A", "B B", 2)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
