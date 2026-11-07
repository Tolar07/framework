from datetime import UTC, datetime

from backtest import darts_rest_study as s


def _g(d, i, h, a, w):
    return {"date": d, "kickoff_utc": f"{d}-{i:03d}", "home": h, "away": a, "winner": w}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_rest_uses_earlier_matches_only_and_caps():
    games = [_g("2025-01-01", 0, "A A", "B B", 1), _g("2025-01-08", 0, "A A", "C C", 1),
             _g("2025-03-01", 0, "A A", "B B", 0)]
    rows = s.scored(games, 14, min_games=0)
    assert rows[0][1] == 0.0                      # both first matches count as the cap
    assert rows[1][1] == (7 - 14) / 7             # A rested 7 days, C is new (cap 14)
    assert rows[2][1] == 0.0                      # both capped


def test_small_sample_reads_pending():
    out = s.render([_g("2025-01-01", 0, "A A", "B B", 1), _g("2025-01-08", 0, "A A", "B B", 0)],
                   datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
