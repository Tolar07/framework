from datetime import UTC, datetime

from backtest import darts_year_decay_study as m


def _g(i, y, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"{y}-01-{i:03d}"}


def test_zero_shrink_matches_history_study():
    from backtest import darts_history_study as h
    games = [_g(i, 2023 + i // 20, "A" if i % 2 else "B", "C" if i % 3 else "D", 3, i % 3) for i in range(1, 60)]
    assert m.walk_forward(games, 0.0, 1)["brier"] == h.walk_forward(games, 24.0, 1)["brier"]


def test_shrink_only_acts_at_year_change():
    one_year = [_g(i, 2024, "A" if i % 2 else "B", "C", 3, i % 3) for i in range(1, 30)]
    assert m.walk_forward(one_year, 0.5, 1) == {**m.walk_forward(one_year, 0.0, 1), "shrink": 0.5}
    two = one_year + [_g(i, 2025, "A", "B", 3, 0) for i in range(1, 10)]
    assert m.walk_forward(two, 0.5, 1)["brier"] != m.walk_forward(two, 0.0, 1)["brier"]


def test_empty_is_pending_and_render_counts_every_try():
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    games = [_g(i, 2023 + i // 10, "A" if i % 2 else "B", "C", 3, 1) for i in range(1, 30)]
    text = m.render(games, datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(m.SHRINKS) * len(m.MIN_GAMES_TRIES) + 1 and "PENDING" in text
