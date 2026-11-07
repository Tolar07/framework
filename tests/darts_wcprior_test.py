from datetime import UTC, datetime

from backtest import darts_wcprior_study as s


def _g(t, d, i, h, a, w):
    return {"tournament": t, "date": d, "kickoff_utc": f"{d}-{i:03d}", "home": h, "away": a, "winner": w}


def test_worlds_of_same_year_come_before_pl_but_later_years_after():
    pl = [_g("2024 Premier League Darts", "2024-02-01", 0, "A A", "B B", 1)]
    wc = [_g("2025 PDC World Championship", "2025-01-02", 0, "A A", "B B", 1),
          _g("2024 PDC World Championship", "2024-01-02", 0, "A A", "B B", 1)]
    assert [(e[0], e[1]) for e in s.events(pl, wc)] == [(2024, 0), (2024, 1), (2025, 0)]


def test_weight_zero_is_pl_only_and_weight_one_learns_the_worlds():
    wc = [_g("2023 PDC World Championship", "2023-01-02", i, "A A", "B B", 1) for i in range(5)]
    pl = [_g("2024 Premier League Darts", "2024-02-01", i, "A A", "B B", 1) for i in range(3)]
    rows = s.scored(pl, wc, weights=[0.0, 1.0], min_games=0)
    assert abs(rows[0]["p"][0.0] - 0.5) < 1e-9 and rows[0]["p"][1.0] > 0.5


def test_small_sample_reads_pending():
    pl = [_g("2024 Premier League Darts", "2024-02-01", 0, "A A", "B B", 1)]
    out = s.render(pl, list(pl), datetime(2026, 1, 1, tzinfo=UTC))
    assert "PENDING" in out and "Record only" in out
    assert "NO DATA" in s.render([], [], datetime(2026, 1, 1, tzinfo=UTC))
