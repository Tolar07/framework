from datetime import UTC, datetime

from backtest import darts_margin_elo_study as m


def _g(i, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"2024-01-01-{i:03d}", "tournament": "2024 PDC World Championship"}


def test_target_modes_and_missing_score_fallback():
    assert m.target(_g(1, "A", "B", 3, 1), "plain") == (1.0, 1.0)
    assert m.target(_g(1, "A", "B", 3, 1), "share") == (0.75, 1.0)
    y, mult = m.target(_g(1, "A", "B", 3, 0), "margin_k")
    assert y == 1.0 and mult > 2.0
    g = _g(1, "A", "B", 3, 1)
    g["home_sets"] = None
    assert m.target(g, "share") == (1.0, 1.0)


def test_walk_forward_scores_before_learning_and_plain_matches_history_study():
    from backtest import darts_history_study as h
    games = [_g(i, "A" if i % 2 else "B", "C" if i % 3 else "D", 3, i % 3) for i in range(1, 40)]
    r = m.walk_forward(games, "plain", 24.0, 1)
    assert r["brier"] == h.walk_forward(games, 24.0, 1)["brier"]


def test_empty_is_pending_and_render_counts_every_try():
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    games = [_g(i, "A" if i % 2 else "B", "C", 3, 1) for i in range(1, 20)]
    text = m.render(games, datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(m.TRIES) + 1 and "PENDING" in text
