from datetime import UTC, datetime

from backtest import darts_score_study as s


def test_score_distribution_sums_to_one_and_favours_stronger():
    d = s.set_scores(0.1, 3)
    assert abs(sum(d.values()) - 1) < 1e-9
    assert sum(v for (a, b), v in d.items() if a == 3) > 0.5
    flat = s.set_scores(0.0, 3)
    assert abs(sum(v for (a, b), v in flat.items() if a == 3) - 0.5) < 1e-9


def _games(n):
    return [{"home": "Strong S", "away": f"Weak {i % 5}", "home_sets": 3, "away_sets": i % 3, "winner": 1,
             "kickoff_utc": f"2024-01-00-{i:03d}"} for i in range(n)]


def test_walk_forward_scores_and_skips_odd_format():
    g = _games(60) + [{"home": "Strong S", "away": "Weak 0", "home_sets": 2, "away_sets": 0, "winner": 1,
                       "kickoff_utc": "2024-01-00-999"}]
    r = s.walk_forward(g)
    assert r["scored"] > 0 and r["skipped"] >= 1
    assert r["model"] is not None and r["flat"] is not None


def test_pending_and_no_data():
    assert s.verdict({"scored": 5, "model": 0.5, "flat": 0.6}).startswith("PENDING")
    assert "NO DATA - PENDING" in s.render([], datetime(2026, 11, 7, tzinfo=UTC))
