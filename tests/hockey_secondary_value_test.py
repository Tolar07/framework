"""Offline test of backtest/hockey_secondary_value.py (framework #569, step 2). No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import hockey_secondary_value as hv  # noqa: E402


def side(price, model, won, last):
    return {"first": {"price": price, "model": model}, "last": {"price": last}, "won": won}


game = {"result": {"reg": [3, 2], "final": [3, 2]}, "sides": {
    "H:18|total=5.5|Over 5.5": side(2.10, 0.55, 1, 1.95),
    "H:18|total=5.5|Under 5.5": side(1.75, 0.45, 0, 1.90),
    "H:18|total=6.5|Over 6.5": side(3.50, 0.30, 0, 3.4),       # outside the band
    "H:29||Yes": side(1.80, None, 1, 1.8),                      # model does not price it
}}
b = hv.bets(game)
assert len(b) == 2 and all(1.6 <= x["price"] <= 2.6 for x in b)
over = next(x for x in b if x["price"] == 2.10)
assert over["family"] == "Total goals, 60 min" and over["won"] == 1 and over["clv"] > 0, over
assert hv.bets({**game, "result": None}) == [], "no result: not graded (PENDING)"
text = hv.build([("2026-11-09", {"games": {"g": game}})])
assert "Games graded: 1" in text and "Total goals, 60 min" in text and "COLLECTING (1 of 200)" in text, text
assert "NO DATA — PENDING" in hv.build([])
print("hockey secondary value: OK")
