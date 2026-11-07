from datetime import UTC, datetime

from backtest import darts_holdout_study as m


def _g(i, year, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"{year}-01-01-{i:03d}", "tournament": f"{year} PDC World Championship"}


def _games(n_per_year=60):
    out = []
    for y in (2022, 2023, 2024, 2025):
        for i in range(n_per_year):
            out.append(_g(i, y, "ABCD"[i % 4], "EFGH"[(i * 3) % 4], 3, i % 3))
    return out


def test_mult_falls_back_to_one_without_a_score():
    assert m.mult_of(_g(1, 2024, "A", "B", 3, 1), "plain") == 1.0
    assert m.mult_of(_g(1, 2024, "A", "B", 3, 0), "margin_k") > 2.0
    g = _g(1, 2024, "A", "B", 3, 1)
    g["home_sets"] = None
    assert m.mult_of(g, "margin_k") == 1.0


def test_split_is_by_year_and_choice_uses_dev_only():
    r = m.walk_forward(_games(), "plain", 24.0, 1.0)
    assert r["dev_n"] > 0 and r["sealed_n"] > 0
    ev = m.evaluate(_games())
    assert len(ev["rows"]) == len(m.TRIES) == 24
    assert ev["chosen"]["dev"] == min(x["dev"] for x in ev["rows"])


def test_pending_when_too_few_and_empty_is_no_data():
    assert "PENDING" in m.evaluate(_games(5))["verdict"]
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    assert "Verdict:" in m.render(_games(), datetime(2026, 11, 7, tzinfo=UTC))
