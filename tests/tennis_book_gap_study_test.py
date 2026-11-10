"""Tennis book-gap study: gap and tour flag come from the row, missing average price is PENDING, noise is not a win. No network."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import tennis_book_gap_study as bs  # noqa: E402
from backtest import tennis_backtest as tb  # noqa: E402


def _g(qa=1.5, qb=2.6, tour="WTA", mkt=0.62):
    return {"qa": qa, "qb": qb, "tour": tour, "mkt": mkt, "year": 2024, "y": 1.0}


def test_gap_and_tour_flag():
    f = bs.features([_g()])[0]
    z = tb.logit(0.62)
    assert math.isclose(f[0], tb.logit(tb.devig(1.5, 2.6)) - z) and math.isclose(f[1], z)
    assert bs.features([_g(tour="ATP")])[0][1] == 0.0


def test_missing_average_is_pending():
    assert bs.features([_g(qa=None)]) == [None]
    assert "PENDING" in bs.run([_g(qa=None)])


def test_noise_is_not_a_win():
    rnd = random.Random(5)
    gs = []
    for i in range(6000):
        mkt = rnd.uniform(0.2, 0.8)
        year = 2019 + (i * 7) // 6000
        qa = 1 / min(max(mkt + rnd.uniform(-.03, .03), .05), .95)
        gs.append({"year": year, "day": f"{year}-06-01", "tour": rnd.choice(["ATP", "WTA"]), "qa": qa,
                   "qb": 1 / (1 - 1 / qa) if qa > 1 else 2.0, "mkt": mkt, "y": 1.0 if rnd.random() < mkt else 0.0})
    text = bs.run(gs)
    assert "Tennis book-gap study" in text and "Record only" in text
    assert "a signal beyond the price" not in text
