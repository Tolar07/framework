from backtest import table_tennis_format_study as t


def test_even_points_even_game_and_match():
    assert abs(t.game_win(0.5) - 0.5) < 1e-9
    assert abs(t.match_win(0.5, 5) - 0.5) < 1e-9
    assert abs(t.match_win(0.5, 7) - 0.5) < 1e-9


def test_game_chance_known_value():
    # 55% of points -> ~ 0.7 game chance (standard 11-point, win-by-2 result)
    assert 0.68 < t.game_win(0.55) < 0.76
    assert t.game_win(0.0) == 0.0 and abs(t.game_win(1.0) - 1.0) < 1e-12


def test_score_dist_sums_to_one():
    for bo in (3, 5, 7):
        assert abs(sum(t.score_dist(0.63, bo).values()) - 1.0) < 1e-9


def test_solver_roundtrip_and_monotone():
    for m in (0.1, 0.5, 0.73, 0.95):
        r = t.solve_point_chance(m, 5)
        assert abs(t.match_win(t.game_win(r), 5) - m) < 1e-6
    assert t.solve_point_chance(0.6, 5) < t.solve_point_chance(0.7, 5)


def test_price_pending_on_bad_input():
    assert t.price(0.0) is None and t.price(1.0) is None


def test_price_totals_consistent():
    p = t.price(0.7, 5)
    s = t.score_dist(p["game"], 5)
    assert abs(p["over"][3.5] - (sum(v for k, v in s.items() if sum(k) > 3.5))) < 1e-12
    assert p["over"][4.5] < p["over"][3.5]
