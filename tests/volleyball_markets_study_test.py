"""Volleyball set-market shadow: markets are consistent with the score model; thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import volleyball_markets_study as mk  # noqa: E402
from tests.volleyball_backtest_test import _games  # noqa: E402


def test_markets_consistent():
    for p in (0.2, 0.5, 0.8):
        mp = mk.market_probs(p, 0.1)
        assert mp["Over 4.5 sets (five sets)"] <= mp["Over 3.5 sets"] <= 1
        assert mp["Home -1.5 sets"] > mp["Away -1.5 sets"] if p > 0.5 else mp["Home -1.5 sets"] < mp["Away -1.5 sets"]


def test_run_and_pending():
    text = mk.run(_games())
    assert "settings tried" in text and "Record only" in text and "Over 3.5 sets" in text
    assert "PENDING: too little tuning data" in mk.run(_games(200))
