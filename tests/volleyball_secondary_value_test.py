"""Offline test of backtest/volleyball_secondary_value.py (framework #569, step 4). No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import volleyball_secondary_value as vv  # noqa: E402


def side(first, last):
    return {"first": {"price": first}, "last": {"price": last}}


SETS = [[25, 20], [25, 18], [20, 25], [25, 22]]                   # home wins 3-1, 188 points
game = {"home": "A", "away": "B", "ko": "k", "result": {"periods": SETS, "winner": 1}, "sides": {
    "volleyball:186||Home": side(1.70, 1.70), "volleyball:186||Away": side(2.10, 2.10),
    "volleyball:188|hcp=-1.5|Home (-1.5)": side(1.90, 1.80), "volleyball:188|hcp=-1.5|Away (+1.5)": side(1.90, 2.00),
    "volleyball:188|hcp=-2.5|Home (-2.5)": side(3.50, 3.4),                     # outside the band
    "volleyball:238|total=180.5|Over 180.5": side(1.85, 1.85), "volleyball:238|total=180.5|Under 180.5": side(1.85, 1.85),
}}
assert vv.valid_sets(SETS) and not vv.valid_sets([[25, 20], [25, 24], [25, 10]]) and not vv.valid_sets([[25, 20]] * 2)
b = vv.bets(game, None)
assert {x["family"] for x in b} == {"Set handicap"}, "no history: total points is PENDING, not invented"
home = next(x for x in b if x["price"] == 1.90 and x["won"] == 1)       # home -1.5 landed (3-1)
assert 0 < home["p"] < 1 and home["clv"] is not None
away = next(x for x in b if x["won"] == 0)
assert abs(home["p"] + away["p"] - 1) < 1e-9, "the two handicap sides cover the whole ladder"
hist = {3: list(range(300, 330)), 4: list(range(340, 370)), 5: list(range(380, 410))}
fams = {x["family"] for x in vv.bets(game, hist)}
assert fams == {"Set handicap", "Total points"}, fams
tp = [x for x in vv.bets(game, hist) if x["family"] == "Total points"]
assert all(x["won"] == (1 if i == 0 else 0) for i, x in enumerate(sorted(tp, key=lambda z: -z["won"]))) and sum(x["won"] for x in tp) == 1
assert vv.bets({**game, "result": None}, hist) == [], "no result: not graded (PENDING)"
text = vv.build([("2026-11-09", {"games": {"g": game}})])
assert "Matches graded: 1" in text and "Set handicap" in text and "COLLECTING (" in text, text
assert "Total points" not in text.split("Matches graded")[1], "walk-forward: first day has no history"
assert "NO DATA — PENDING" in vv.build([])
print("volleyball secondary value: OK")
