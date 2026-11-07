from datetime import UTC, datetime

from backtest import darts_close_study as s


def _g(i, h, a, w, hs, as_):
    return {"date": "2025-01-01", "kickoff_utc": f"2025-01-01-{i:03d}", "home": h, "away": a, "winner": w,
            "home_sets": hs, "away_sets": as_}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_carry_sign_and_threshold():
    g = _g(0, "A A", "B B", 1, 6, 5)
    assert s._carry(g, 1, 1) == 1 and s._carry(g, 2, 1) == -1
    assert s._carry(_g(0, "A A", "B B", 1, 6, 2), 1, 2) == 0   # comfortable
    assert s._carry(_g(0, "A A", "B B", 0, 5, 5), 1, 2) == 0   # draw


def test_uses_earlier_matches_only():
    games = [_g(0, "A A", "B B", 1, 6, 5), _g(1, "A A", "C C", 1, 6, 0), _g(2, "A A", "B B", 0, 3, 6)]
    rows = s.scored(games, 1, min_games=0)
    assert rows[0][1] == 0.0    # nothing earlier
    assert rows[1][1] == 1.0    # A's narrow win carried, C is new
    assert rows[2][1] == 1.0    # A last won 6-0 (0); B last lost 5-6 narrow (-1): 0 - (-1)


def test_small_sample_reads_pending():
    out = s.render([_g(0, "A A", "B B", 1, 6, 5), _g(1, "A A", "B B", 0, 3, 6)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
