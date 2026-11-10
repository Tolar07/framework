"""Tennis workload study: features use only earlier matches; no-history rows are skipped. No network."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_workload_study as ws  # noqa: E402


def _g(day, a, b, bo=3):
    return {"day": day, "tour": "ATP", "a": a, "b": b, "bo": bo, "y": 1.0, "mkt": 0.5, "year": int(day[:4])}


def test_first_match_is_pending_and_features_look_back_only():
    gs = [_g("2024-01-01", "A", "B"), _g("2024-01-03", "A", "C"), _g("2024-01-05", "A", "B", bo=5)]
    f = ws.features(gs)
    assert f[0] is None and f[1] is None            # no history for both sides yet
    assert f[2] is not None
    # A: last played 2 days ago, 2 matches in 14d; B: last 4 days ago, 1 match
    assert math.isclose(f[2][0], math.log(2 / 4))
    assert f[2][1] == 1.0 and f[2][2] == 1.0


def test_future_results_do_not_change_earlier_features():
    gs = [_g("2024-01-01", "A", "B"), _g("2024-01-04", "A", "B")]
    before = ws.features(gs)
    after = ws.features(gs + [_g("2024-01-06", "A", "B")])
    assert before == after[:2]


def test_noise_is_not_a_win_and_run_writes_text():
    rnd = random.Random(5)
    gs = []
    for i in range(6000):
        mkt = rnd.uniform(0.2, 0.8)
        year = 2019 + (i * 7) // 6000
        gs.append({"year": year, "day": f"{year}-{1 + i % 12:02d}-{1 + i % 28:02d}", "tour": "ATP",
                   "a": f"P{i % 30}", "b": f"Q{i % 29}", "bo": 3, "y": 1.0 if rnd.random() < mkt else 0.0,
                   "mkt": mkt})
    gs.sort(key=lambda g: g["day"])
    text = ws.run(gs)
    assert "Tennis workload study" in text and "Record only" in text
    assert "a signal beyond the price" not in text


def test_empty_is_pending():
    assert "PENDING" in ws.run([_g("2024-01-01", "A", "B")])
