"""Tennis level study: flags come from the row itself, missing Series is PENDING, noise is not a win. No network."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_level_study as ls  # noqa: E402
from backtest import tennis_backtest as tb  # noqa: E402


def _g(series="Grand Slam", rnd="Quarterfinals", court="Indoor", mkt=0.7):
    return {"series": series, "round": rnd, "court": court, "mkt": mkt, "year": 2024, "y": 1.0}


def test_flags_scale_the_price_logit():
    z = tb.logit(0.7)
    f = ls.features([_g()])[0]
    assert math.isclose(f[0], z) and f[1] == 0.0 and math.isclose(f[2], z) and math.isclose(f[3], z)
    f2 = ls.features([_g(series="ATP250", rnd="1st Round", court="Outdoor")])[0]
    assert f2 == [0.0, 0.0, 0.0, 0.0]


def test_missing_series_is_pending():
    assert ls.features([_g(series="")]) == [None]
    assert "PENDING" in ls.run([_g(series="")])


def test_noise_is_not_a_win():
    rnd = random.Random(9)
    gs = []
    for i in range(6000):
        mkt = rnd.uniform(0.2, 0.8)
        year = 2019 + (i * 7) // 6000
        gs.append({"year": year, "day": f"{year}-06-01", "series": rnd.choice(["Grand Slam", "Masters 1000", "ATP250"]),
                   "round": rnd.choice(["1st Round", "Final"]), "court": rnd.choice(["Indoor", "Outdoor"]),
                   "mkt": mkt, "y": 1.0 if rnd.random() < mkt else 0.0})
    text = ls.run(gs)
    assert "Tennis tournament-level study" in text and "Record only" in text
    assert "a signal beyond the price" not in text
