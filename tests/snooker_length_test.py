"""Snooker match-length study (framework#340): buckets, stretch maths, no look-ahead, PENDING on thin data."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import snooker_length_study as sl  # noqa: E402

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def test_buckets():
    assert sl.bucket(4) == "first-to-4" and sl.bucket(6) == "first-to-5-6" and sl.bucket(10) == "first-to-9+"


def test_stretch_identity_and_direction():
    assert abs(sl.stretch(0.7, 1.0) - 0.7) < 1e-9
    assert sl.stretch(0.7, 1.3) > 0.7 > sl.stretch(0.7, 0.8)
    assert abs(sl.stretch(0.5, 1.5) - 0.5) < 1e-9


def test_fit_needs_enough_and_picks_best():
    assert sl.fit([(0.6, 1.0)] * 5) is None
    # favourites always win: sharper is better, so the largest factor wins
    assert sl.fit([(0.7, 1.0)] * 150) == max(sl.GRID)


def test_pending_without_data_and_thin_buckets():
    assert "PENDING" in sl.render([], NOW)
    rows = [{"kickoff_utc": "2025-01-01-00-0000", "home": "A Aa", "away": "B Bb", "home_frames": 4,
             "away_frames": 1, "winner": 1}]
    assert "PENDING" in sl.render(rows, NOW)
