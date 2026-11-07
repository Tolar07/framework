from datetime import UTC, datetime

from backtest import darts_format_underdog_study as m


def _g(i, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"2024-01-{i:03d}"}


def _games(n=200):
    return [_g(i, "A" if i % 2 else "B", "C" if i % 3 else "D", 3 + i % 3, i % 3) for i in range(1, n)]


def test_buckets():
    assert [m.bucket_of(n) for n in (2, 3, 4, 5, 6, 13)] == [0, 0, 1, 2, 3, 3]


def test_counts_and_rates_are_sane():
    rows = m.walk_forward(_games())
    assert sum(r["n"] for r in rows) > 0
    for r in rows:
        assert r["won"] <= r["n"] and r["implied"] <= r["n"] * 0.5


def test_pending_paths():
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    assert m.verdict(5, 0.3, 0.3).startswith("PENDING")
    assert "MORE" in m.verdict(50, 0.30, 0.40)
    assert "LESS" in m.verdict(50, 0.40, 0.30)
    assert "about as often" in m.verdict(50, 0.30, 0.31)
    text = m.render(_games(), datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(m.BUCKETS) + 1
