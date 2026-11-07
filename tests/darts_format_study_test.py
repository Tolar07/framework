from backtest import darts_format_study as d


def test_equal_players_even_match():
    for legs in (3, 6, 10):
        assert abs(d.leg_match_win(0.0, legs) - 0.5) < 1e-9
    assert abs(d.set_match(0.0, 3, 3) - 0.5) < 1e-9


def test_score_dist_sums_to_one_and_monotone():
    for legs in (3, 6):
        assert abs(sum(d.leg_match(0.03, legs).values()) - 1.0) < 1e-9
    assert d.leg_match_win(0.02, 6) < d.leg_match_win(0.05, 6) < d.leg_match_win(0.1, 6)
    assert d.leg_match_win(0.05, 6) < d.leg_match_win(0.05, 10)


def test_solver_roundtrip_and_pending():
    for m in (0.1, 0.5, 0.73, 0.9):
        p = d.price_legs(m, 6)
        assert abs(d.leg_match_win(p["edge"], 6) - m) < 1e-6
    assert d.price_legs(0.0, 6) is None and d.price_legs(1.0, 6) is None
    assert d.price_sets(1.5, 3, 3) is None


def test_report_runs():
    assert "Darts format shadow" in d.run()
