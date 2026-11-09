import random

from engine import format_prob as fp


def test_race_matches_known_values():
    assert abs(fp.race(0.5, 6) - 0.5) < 1e-12
    assert abs(fp.race(0.6, 2) - 0.648) < 1e-12          # best of 3
    assert abs(fp.best_of_win(0.6, 5) - 0.68256) < 1e-9
    assert fp.race(0.55, 10) > fp.race(0.55, 6) > fp.race(0.55, 1)


def test_win_by_two_table_tennis_value():
    assert abs(fp.win_by_two(0.5, 11) - 0.5) < 1e-12
    assert abs(fp.win_by_two(0.54, 11) - 0.651) < 0.002   # matches backtest/TABLE_TENNIS_FORMAT_STUDY.md


def test_volleyball_dist_sums_and_monotone():
    for bo in (3, 5):
        assert abs(sum(fp.volleyball_dist(0.53, bo).values()) - 1.0) < 1e-9
    assert abs(fp.volleyball_match(0.5) - 0.5) < 1e-9
    assert fp.volleyball_match(0.52) < fp.volleyball_match(0.55)


def test_tennis_equal_and_longer_format_helps_favourite():
    assert abs(fp.tennis_match(0.0, 3) - 0.5) < 1e-9
    assert fp.tennis_match(0.02, 5) > fp.tennis_match(0.02, 3) > 0.5
    assert fp.tennis_match(-0.02, 5) < fp.tennis_match(-0.02, 3) < 0.5
    assert abs(fp.tennis_match(0.03, 3) + fp.tennis_match(-0.03, 3) - 1.0) < 1e-9


def test_tennis_set_matches_simulation():
    rng = random.Random(7)
    sa, sb = 0.66, 0.62

    def game(p):
        a = b = 0
        while not (max(a, b) >= 4 and abs(a - b) >= 2):
            if rng.random() < p:
                a += 1
            else:
                b += 1
        return a > b

    def tb(a_first):
        a = b = n = 0
        while not (max(a, b) >= 7 and abs(a - b) >= 2):
            a_serves = (((n + 1) // 2) % 2 == 0) == a_first
            if rng.random() < (sa if a_serves else 1 - sb):
                a += 1
            else:
                b += 1
            n += 1
        return a > b

    def tset():
        a_first = rng.random() < 0.5
        a = b = 0
        while True:
            if a == 6 and b == 6:
                return tb(a_first)
            if (a >= 6 and a - b >= 2) or a == 7:
                return True
            if (b >= 6 and b - a >= 2) or b == 7:
                return False
            a_serves = ((a + b) % 2 == 0) == a_first
            w = game(sa) if a_serves else not game(sb)
            a, b = (a + 1, b) if w else (a, b + 1)

    n = 20000
    sim = sum(tset() for _ in range(n)) / n
    assert abs(sim - fp.tennis_set(sa, sb)) < 0.012


def test_solvers_roundtrip_and_pending():
    d = fp.tennis_edge(0.7, 3)
    assert abs(fp.tennis_match(d, 3) - 0.7) < 1e-6
    assert fp.tennis_edge(0.0, 3) is None and fp.tennis_edge(1.0, 5) is None
    c = fp.convert_tennis(0.7, 3, 5)
    assert 0.7 < c < 0.9
    assert abs(fp.convert_tennis(c, 5, 3) - 0.7) < 1e-5
    assert fp.convert_units(0.6, 6, 10) > 0.6
    assert fp.convert_units(1.5, 6, 10) is None
