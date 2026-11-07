from datetime import UTC, datetime

from backtest import darts_night_study as s


def _g(day, i, h, a, w):
    d = f"2025-01-{day:02d}"
    return {"date": d, "kickoff_utc": f"{d}-{i:03d}", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_zero_shift_is_identity_and_fatigue_moves_against_the_busier_player():
    assert abs(s.shifted(0.6, 2.0, 0.0, 0.0) - 0.6) < 1e-9
    assert s.shifted(0.6, 2.0, 0.0, -0.1) < 0.6 < s.shifted(0.6, -2.0, 0.0, -0.1)


def test_night_load_counts_earlier_matches_same_night_only():
    rows = s.scored([_g(1, 0, "A A", "B B", 1), _g(1, 1, "A A", "C C", 1), _g(2, 0, "A A", "C C", 1)], min_games=0)
    assert rows[0][1] == 0.0
    assert rows[1][1] == 1.0          # A has thrown once tonight, C none
    assert rows[2][1] == 0.0          # new night


def test_slot_shift_is_clipped_and_small_sample_reads_pending():
    assert s.slot_shift([(0.5, 0.0, 1.0)] * 50) == 0.5
    out = s.render([_g(1, 0, "A A", "B B", 1), _g(1, 1, "A A", "B B", 0)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
