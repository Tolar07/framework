"""Offline test of backtest/rugby_secondary_value.py (framework #569, step 4). No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import rugby_secondary_value as rv  # noqa: E402


def side(first, last):
    return {"first": {"price": first}, "last": {"price": last}}


game = {"home": "A", "away": "B", "ko": "k", "result": {"final": [30, 20]}, "sides": {
    "rugby:11||Home": side(1.70, 1.70), "rugby:11||Away": side(2.10, 2.10),
    "rugby:16|hcp=-9.5|Home (-9.5)": side(1.90, 1.85), "rugby:16|hcp=-9.5|Away (+9.5)": side(1.90, 1.95),
    "rugby:16|hcp=-12.5|Home (-12.5)": side(2.30, 2.30), "rugby:16|hcp=-12.5|Away (+12.5)": side(1.60, 1.60),
    "rugby:18|total=47.5|Over 47.5": side(1.85, 1.85), "rugby:18|total=47.5|Under 47.5": side(1.95, 1.95),
    "rugby:18|total=70.5|Over 70.5": side(4.00, 4.00),                        # outside the band
    "rugby:14|hcp=0:5|Home (0:5)": side(2.00, 2.00),                         # not priced by this model
}}
assert rv.final_ok({"final": [30, 20]}) == (30, 20) and rv.final_ok(None) is None and rv.final_ok({"final": [1]}) is None
assert rv.bets(game, [50] * 5) == [], "short history: PENDING, not invented"
hist = [50] * 30
b = rv.bets(game, hist)
assert {x["family"] for x in b} == {"Points handicap", "Total points"}, b
hc = {x["price"]: x for x in b if x["family"] == "Points handicap"}
assert hc[1.90]["won"] in (0, 1) and len([x for x in b if x["family"] == "Points handicap"]) == 4
assert hc[2.30]["won"] == 0 and hc[1.60]["won"] == 1                      # 30-20: home -12.5 fails, away +12.5 covers
assert abs(hc[2.30]["p"] + hc[1.60]["p"] - 1) < 1e-9, "the two handicap sides cover everything"
tot = {x["price"]: x for x in b if x["family"] == "Total points"}
assert tot[1.85]["won"] == 1 and tot[1.95]["won"] == 0                    # 50 points: over 47.5
assert abs(tot[1.85]["p"] + tot[1.95]["p"] - 1) < 1e-9 and all(x["clv"] is not None for x in b)
assert rv.bets({**game, "result": None}, hist) == [], "no result: not graded (PENDING)"
assert rv.bets({"result": {"final": [2, 1]}, "sides": {}}, hist) == []
docs = [(f"2026-10-{d:02d}", {"games": {"x": {**game, "ko": f"k{d}"}}}) for d in range(1, 32)]
text = rv.build(docs + [("2026-11-05", {"games": {"y": {**game, "ko": "late"}}})])
assert "Points handicap" in text and "Total points" in text, text
assert "NO DATA — PENDING" in rv.build([]) and "NO DATA — PENDING" in rv.build(docs[:5])
print("rugby secondary value: OK")
