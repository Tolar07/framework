from backtest import tennis_format_study as s


def _games():
    out = []
    for y in (2019, 2020):
        for i in range(2100 if y == 2019 else 40):
            m = 0.3 + 0.4 * ((i * 37) % 100) / 100
            out.append({"year": y, "bo": 3 if y == 2019 else 5, "mkt": m, "y": float((i * 13) % 100 < m * 100),
                        "pa": 1 / m, "pb": 1 / (1 - m)})
    return out


def test_candidate_identity_at_even_and_bo3():
    assert abs(s.candidate(0.5, 1.1, 5) - 0.5) < 1e-6
    assert s.candidate(0.7, 1.0, 3) == s.tb.sig(s.tb.logit(0.7))


def test_slope_one_keeps_bo5_price():
    assert abs(s.candidate(0.7, 1.0, 5) - 0.7) < 1e-5


def test_walk_forward_uses_only_earlier_years_and_pending():
    rows = s.walk_forward(_games(), [2019, 2020])
    assert [r["year"] for r in rows] == [2020]              # 2019 has no earlier training year
    assert "PENDING" in s.run(_games())                      # 40 best-of-5 matches < MIN_BO5
