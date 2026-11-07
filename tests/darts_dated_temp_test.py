from datetime import UTC, datetime

from backtest import darts_dated_temp_study as s


def _g(i, h, a, w):
    d = f"2025-01-{i:02d}"
    return {"date": d, "kickoff_utc": d + "T19:00:00Z", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_temper_shrinks_toward_half_and_t1_is_identity():
    assert abs(s.temper(0.8, 1.0) - 0.8) < 1e-9
    assert 0.5 < s.temper(0.8, 2.0) < 0.8
    assert abs(s.temper(0.5, 3.0) - 0.5) < 1e-9


def test_scored_uses_earlier_games_only():
    rows = s.scored([_g(1, "A A", "B B", 1), _g(2, "A A", "B B", 1)], min_games=0)
    assert rows[0][0] == 0.5 and rows[1][0] > 0.5


def test_small_sample_reads_pending_and_is_record_only():
    out = s.render([_g(1, "A A", "B B", 1), _g(2, "A A", "B B", 0)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
