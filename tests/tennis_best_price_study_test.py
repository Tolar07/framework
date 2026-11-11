"""Tennis best-price study: EV maths, missing prices are PENDING/skipped, no network."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_best_price_study as bp  # noqa: E402


def _g(**kw):
    g = {"year": 2024, "mkt": 0.6, "y": 1.0, "pa": 1.6, "pb": 2.4, "qa": 1.62, "qb": 2.3, "xa": 1.7, "xb": 2.5}
    g.update(kw)
    return g


def test_sides_and_ev():
    rows = bp.sides([_g()])
    assert len(rows) == 2 and rows[0]["won"] and not rows[1]["won"]
    st = bp.stats(rows, "x")
    assert st["n"] == 2
    assert math.isclose(st["ev"], (0.6 * 1.7 - 1 + 0.4 * 2.5 - 1) / 2)
    assert math.isclose(st["roi"], (0.7 - 1.0) / 2)


def test_missing_and_old_rows_skipped():
    assert bp.sides([_g(year=2020)]) == []
    rows = bp.sides([_g(xa=None, xb=None)])
    assert bp.stats(rows, "x")["n"] == 0
    assert "PENDING" in bp.run([_g(xa=None, xb=None)])
    assert "PENDING" in bp.run([])


def test_report_text():
    text = bp.run([_g(), _g(mkt=0.4, y=0.0)])
    assert "Tennis best-price study" in text and "Record only" in text
