"""Snooker layoff study (framework#340): buckets, no look-ahead, PENDING on thin data."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import snooker_rust_study as sr  # noqa: E402

NOW = datetime(2026, 11, 11, tzinfo=UTC)


def test_buckets():
    assert sr.bucket(None) == "first match seen" and sr.bucket(30) == "layoff<=30d"
    assert sr.bucket(31) == "layoff 31-90d" and sr.bucket(91) == "layoff>90d"


def test_layoff_uses_longer_gap_and_needs_history():
    assert sr.layoff({"a": "2025-01-01"}, "a", "b", "2025-02-01") is None
    assert sr.layoff({"a": "2025-01-01", "b": "2025-01-25"}, "a", "b", "2025-02-01") == 31


def test_first_match_not_counted_with_lookahead():
    rows = [{"kickoff_utc": f"2019-01-{d:02d}-00-0000", "home": "A Aa", "away": "B Bb", "home_frames": 4,
             "away_frames": 1, "winner": 1} for d in range(1, 6)]
    data = sr.collect(rows)
    assert sum(len(v["tune"]) + len(v["held"]) for v in data.values()) <= 5


def test_fit_and_pending():
    assert sr.fit([(0.6, 1.0)] * 5) is None
    assert sr.fit([(0.7, 1.0)] * 150) == max(sr.GRID)
    assert "PENDING" in sr.render([], NOW)
    assert "PENDING" in sr.render([{"kickoff_utc": "2025-01-01-00-0000", "home": "A Aa", "away": "B Bb",
                                    "home_frames": 4, "away_frames": 1, "winner": 1}], NOW)
