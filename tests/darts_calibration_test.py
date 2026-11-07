from datetime import UTC, datetime

from backtest import darts_calibration_study as m


def _g(i, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"2024-01-{i:03d}"}


def _games(n=60):
    return [_g(i, "A" if i % 2 else "B", "C" if i % 3 else "D", 3, i % 3) for i in range(1, n)]


def test_temp_one_matches_history_study():
    from backtest import darts_history_study as h
    g = _games()
    assert m.walk_forward(g, 1.0, 1)["brier"] == h.walk_forward(g, 24.0, 1)["brier"]


def test_temp_changes_score_but_not_hit_rate_direction():
    g = _games()
    assert m.walk_forward(g, 2.0, 1)["brier"] != m.walk_forward(g, 1.0, 1)["brier"]
    assert m.walk_forward(g, 2.0, 1)["hit"] == m.walk_forward(g, 1.0, 1)["hit"]


def test_empty_is_pending_and_render_counts_every_try():
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    text = m.render(_games(), datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(m.TEMPS) * len(m.MIN_GAMES_TRIES) + 1 and "PENDING" in text
