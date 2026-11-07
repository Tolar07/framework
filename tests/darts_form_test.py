from datetime import UTC, datetime

from backtest import darts_form_study as s


def _g(i, h, a, w):
    return {"date": "2025-01-01", "kickoff_utc": f"2025-01-01-{i:03d}", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_zero_weight_is_identity_and_form_moves_toward_the_hot_player():
    assert abs(s.shifted(0.6, 2.0, 0.0) - 0.6) < 1e-9
    assert s.shifted(0.6, 1.0, 0.5) > 0.6 > s.shifted(0.6, -1.0, 0.5)


def test_form_uses_earlier_matches_only_and_is_zero_sum():
    rows = s.scored([_g(0, "A A", "B B", 1), _g(1, "A A", "B B", 1), _g(2, "A A", "B B", 1)], 3, min_games=0)
    assert rows[0][1] == 0.0                 # nothing earlier
    assert rows[1][1] > 0.0                  # A won the first, B lost it
    assert rows[2][1] > rows[1][1] * 0.5


def test_small_sample_reads_pending():
    out = s.render([_g(0, "A A", "B B", 1), _g(1, "A A", "B B", 0)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
