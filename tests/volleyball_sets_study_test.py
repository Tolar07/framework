"""Volleyball set-score shadow: maths is consistent, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import volleyball_sets_study as ss  # noqa: E402
from tests.volleyball_backtest_test import _games  # noqa: E402


def test_score_probs_sum_to_one_and_solve_roundtrips():
    for q in (0.1, 0.5, 0.8):
        assert abs(sum(ss.score_probs(q).values()) - 1) < 1e-12
    for m in (0.05, 0.5, 0.9):
        assert abs(ss.match_win(ss.solve_q(m)) - m) < 1e-9
    assert abs(ss.solve_q(0.5) - 0.5) < 1e-9


def test_run_and_pending():
    text = ss.run(_games())
    assert "1 setting tried" in text and "Record only" in text and "log loss" in text.lower()
    assert "PENDING: too little tuning data" in ss.run(_games(200))
