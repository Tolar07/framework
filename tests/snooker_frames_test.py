"""Snooker frame-score ladder (framework#340): exact distribution, solver, no look-ahead, PENDING on no data."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import snooker_frames_study as sf  # noqa: E402


def test_distribution_sums_to_one_and_solver_inverts():
    assert abs(sum(sf.score_probs(0.57, 6).values()) - 1) < 1e-9
    for t in (4, 10, 18):
        assert abs(sf.win_prob(sf.solve_f(0.7, t), t) - 0.7) < 1e-6
    assert abs(sf.win_prob(0.5, 7) - 0.5) < 1e-9


def test_longer_match_favours_the_stronger_player_more():
    assert sf.solve_f(0.7, 18) < sf.solve_f(0.7, 4)


def test_pending_without_data():
    assert "PENDING" in sf.render([], datetime(2026, 11, 10, tzinfo=UTC))


def test_rows_skip_missing_frames():
    r = [{"kickoff_utc": "2025-01-01-00-0000", "home": "A Aa", "away": "B Bb", "home_frames": None, "away_frames": 4}]
    assert sf.rows_for_study(r) == []
