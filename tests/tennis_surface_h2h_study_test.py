"""Tennis surface/H2H study: features use only earlier matches; no-history rows are skipped. No network."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_surface_h2h_study as st  # noqa: E402


def _g(day, a, b, y=1.0, surface="Clay"):
    return {"day": day, "tour": "ATP", "a": a, "b": b, "bo": 3, "y": y, "mkt": 0.5, "year": int(day[:4]),
            "surface": surface}


def test_features_look_back_only_and_first_matches_pending():
    gs = [_g("2024-01-01", "A", "B", 1.0), _g("2024-01-02", "A", "C"), _g("2024-01-03", "B", "A", 0.0, "Hard")]
    f = st.features(gs)
    assert f[0] is None and f[1] is None
    # B (a) vs A (b) on Hard: no hard history for either -> equal rates; A led the only meeting 1-0
    assert math.isclose(f[2][0], 0.0)
    assert math.isclose(f[2][1], (1.5 / 4 - 0.5) * 0.25)
    assert f[2][2] == 0.0                    # both last played on Clay -> both switch


def test_future_results_do_not_change_earlier_features():
    gs = [_g("2024-01-01", "A", "B"), _g("2024-01-04", "A", "B")]
    assert st.features(gs) == st.features(gs + [_g("2024-01-06", "A", "B", 0.0)])[:2]


def test_noise_is_not_a_win_and_run_writes_text():
    rnd = random.Random(5)
    gs = []
    for i in range(6000):
        mkt = rnd.uniform(0.2, 0.8)
        year = 2019 + (i * 7) // 6000
        gs.append({"year": year, "day": f"{year}-{1 + i % 12:02d}-{1 + i % 28:02d}", "tour": "ATP",
                   "a": f"P{i % 30}", "b": f"Q{i % 29}", "bo": 3, "y": 1.0 if rnd.random() < mkt else 0.0,
                   "mkt": mkt, "surface": ("Clay", "Hard", "Grass")[i % 3]})
    gs.sort(key=lambda g: g["day"])
    text = st.run(gs)
    assert "surface-form and head-to-head study" in text and "Record only" in text
    assert "a signal beyond the price" not in text


def test_empty_is_pending():
    assert "PENDING" in st.run([_g("2024-01-01", "A", "B")])
