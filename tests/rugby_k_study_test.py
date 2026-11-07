"""Rugby K-factor study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_k_study as rk  # noqa: E402
from backtest import rugby_inputs_study as ri  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs = 30.0 if (h == "A" or i % 3 == 0) else 10.0
        yr = 2014 + i // 120
        out.append({"year": yr, "day": f"{yr}-01-01", "home": h, "away": a, "hs": hs, "as": 20.0,
                    "y": 1.0 if hs > 20 else 0.0, "league": "URC" if i % 2 else "Top 14"})
    return out


def test_k_changes_chances():
    g = _games()
    hb = {"URC": 70.0, "Top 14": 70.0}
    assert ri.replay(g, hb, False, 8.0) != ri.replay(g, hb, False, 56.0)


def test_run_and_pending():
    text = rk.run(_games())
    assert "Settings tried" in text and "2020" in text and "Tuning-years Brier by K" in text
    assert "PENDING" in rk.run(_games(300))
