"""Rugby Elo-variants study: no network, thin data is PENDING."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import rugby_inputs_study as ri  # noqa: E402


def _games(n=1500):
    teams = ["A", "B", "C", "D"]
    out = []
    for i in range(n):
        h, a = teams[i % 4], teams[(i + 1 + i // 4 % 3) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        hs = 30.0 if (h == "A" or i % 3 == 0) else 10.0
        out.append({"year": 2014 + i // 120, "home": h, "away": a, "hs": hs, "as": 20.0,
                    "y": 1.0 if hs > 20 else 0.0, "league": "URC" if i % 2 else "Top 14"})
    return out


def test_mov_changes_ratings():
    g = _games()
    hb = {"URC": 70.0, "Top 14": 70.0}
    assert ri.replay(g, hb, False) != ri.replay(g, hb, True)


def test_run_counts_tries():
    text = ri.run(_games())
    assert "Settings tried" in text and "MOV Elo" in text and "2020" in text


def test_thin_data_pending():
    assert "PENDING" in ri.run(_games(300))
