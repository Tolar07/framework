from datetime import UTC, datetime

from backtest import darts_coldstart_study as m


def _g(i, h, a, hs, as_):
    return {"home": h, "away": a, "home_sets": hs, "away_sets": as_, "winner": 1 if hs > as_ else 2,
            "kickoff_utc": f"2024-01-{i:03d}"}


def _games(n=80):
    return [_g(i, "A" if i % 2 else "B", "C" if i % 3 else "D", 3, i % 3) for i in range(1, n)]


def test_buckets():
    assert [m.bucket_of(n) for n in (0, 1, 2, 3, 5, 6, 99)] == [0, 1, 1, 2, 2, 3, 3]


def test_every_match_lands_in_one_bucket():
    g = _games()
    assert sum(r["scored"] for r in m.walk_forward(g)) == len(g)
    assert m.walk_forward(g)[0]["scored"] >= 1


def test_empty_pending_and_small_bucket_pending():
    assert "NO DATA - PENDING" in m.render([], datetime(2026, 11, 7, tzinfo=UTC))
    assert m.verdict(5, 0.2).startswith("PENDING")
    assert m.verdict(50, 0.2) == "beats a coin flip"
    text = m.render(_games(), datetime(2026, 11, 7, tzinfo=UTC))
    assert text.count("\n| ") >= len(m.BUCKETS) + 1
