from datetime import UTC, datetime

from backtest import darts_dated_calibration_study as s


def _g(d, h, a, w):
    return {"date": d, "kickoff_utc": d + "T19:00:00Z", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_sides_come_in_pairs_and_use_earlier_games_only():
    games = [_g("2025-01-01", "A A", "B B", 1), _g("2025-01-02", "A A", "B B", 1)]
    rows = s.sides(games, min_games=0)
    assert len(rows) == 4
    assert rows[0][0] == 0.5 and rows[0][1] == 1 and rows[1][1] == 0   # first game: no history
    assert rows[2][0] > 0.5                                            # after a win A is favoured
    assert abs(rows[2][0] + rows[3][0] - 1) < 1e-9


def test_small_bands_read_pending():
    out = s.render([_g("2025-01-01", "A A", "B B", 1)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
