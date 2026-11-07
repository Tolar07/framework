from datetime import UTC, datetime

from backtest import darts_totals_study as s


def _g(i, h, a, hs, as_):
    return {"date": "2025-01-01", "kickoff_utc": f"2025-01-01-{i:03d}", "home": h, "away": a,
            "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 0}


def test_empty_is_pending():
    assert "PENDING" in s.render([], datetime(2026, 1, 1, tzinfo=UTC))


def test_rows_use_earlier_matches_only_and_total_legs():
    rows = s.rows_of([_g(0, "A A", "B B", 6, 3), _g(1, "A A", "B B", 6, 5)], min_games=0)
    assert rows[0] == (0.5, 9) and rows[1][0] > 0.5 and rows[1][1] == 11


def test_over_chances_are_probabilities_and_fall_with_line():
    ov = s.over_chances(0.6, 0.6)
    assert all(0 <= v <= 1 for v in ov.values()) and ov[7.5] > ov[8.5] > ov[9.5] > ov[10.5]


def test_small_sample_reads_pending():
    out = s.render([_g(0, "A A", "B B", 6, 3)], datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
