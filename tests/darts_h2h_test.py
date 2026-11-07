from datetime import UTC, datetime

from backtest import darts_h2h_study as s


def _g(i, h, a, w):
    d = f"2025-01-{i:02d}"
    return {"date": d, "kickoff_utc": d + "T19:00:00Z", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_nudge_zero_weight_is_identity_and_moves_with_record():
    assert abs(s.nudge(0.6, 0.5, 0.0) - 0.6) < 1e-9
    assert s.nudge(0.6, 0.5, 1.0) > 0.6 > s.nudge(0.6, -0.5, 1.0)


def test_head_to_head_uses_earlier_meetings_only_and_flips_with_sides():
    rows = s.scored([_g(1, "A A", "B B", 1), _g(2, "B B", "A A", 2), _g(3, "B B", "A A", 1)], min_games=0)
    assert rows[0][1] == 0.0                    # no earlier meeting
    assert rows[1][1] < 0
    assert rows[2][1] < 0                       # A is 2-0 up, home is B


def test_small_sample_reads_pending_and_is_record_only():
    out = s.render([_g(1, "A A", "B B", 1), _g(2, "A A", "B B", 0)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
