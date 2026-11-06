"""Rugby calibration study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_calibration_study as rc  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        y = 1.0 if (h == "A" or i % 3 == 0) else 0.0
        out.append({"year": 2014 + i // 120, "home": h, "away": a, "y": y, "league": "URC"})
    return out


def test_shrink_ends():
    assert rc.shrink(0.9, 0.6, 1.0) == 0.9 and rc.shrink(0.9, 0.6, 0.0) == 0.6


def test_run_counts_tries_and_reports():
    text = rc.run(_games())
    assert "Shrink weights tried: **5**" in text and "2020" in text and "Stated home-win chance" in text


def test_reliability_counts_match():
    g = _games()
    from backtest import rugby_backtest as rb
    p = rb.replay(g, 32.0, 70.0)
    rows = rc.reliability(g, p, (2014, 2030))
    n = sum(1 for x, q in zip(g, p) if q is not None)
    assert sum(r["n"] for r in rows) == n


def test_thin_data_pending():
    text = rc.run(_games(300))
    assert "PENDING" in text
