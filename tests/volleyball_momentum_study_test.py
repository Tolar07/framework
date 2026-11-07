"""Volleyball set-momentum shadow: m=0 equals independent sets; probabilities consistent; thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import volleyball_momentum_study as ms  # noqa: E402
from backtest import volleyball_sets_study as ss  # noqa: E402
from tests.volleyball_backtest_test import _games  # noqa: E402


def test_zero_momentum_matches_independent_sets_and_sums_to_one():
    a, b = ms.score_probs(0.6, 0.0), ss.score_probs(0.6)
    assert all(abs(a[k] - b[k]) < 1e-12 for k in ss.SCORES)
    for m in (0.0, 0.1, 0.2):
        assert abs(sum(ms.score_probs(0.55, m).values()) - 1) < 1e-9


def test_momentum_raises_straight_sets_and_solve_roundtrips():
    lo, hi = ms.score_probs(0.6, 0.0), ms.score_probs(0.6, 0.15)
    assert hi["3-0"] + hi["0-3"] > lo["3-0"] + lo["0-3"]
    for p in (0.2, 0.5, 0.8):
        assert abs(ms.match_win(ms.solve_q(p, 0.1), 0.1) - p) < 1e-6


def test_run_and_pending():
    text = ms.run(_games())
    assert "settings tried" in text and "Record only" in text
    assert "PENDING: too little tuning data" in ms.run(_games(200))
