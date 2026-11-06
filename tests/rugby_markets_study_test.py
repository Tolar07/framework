"""Rugby market catalogue check: no network."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_markets_study as rm  # noqa: E402
from engine import multisport as ms  # noqa: E402


def test_every_asked_market_is_catalogued():
    assert set(ms.SPORTS["rugby"]["markets"].split(",")) <= set(rm.CATALOGUE)


def test_no_market_has_contradicting_sides():
    for mid, (_n, specs) in rm.CATALOGUE.items():
        assert rm.check(mid, specs)["bad"] == 0, mid


def test_report_says_so():
    t = rm.run()
    assert "| 406 |" in t and "Contradictions" in t and "Record only" in t
