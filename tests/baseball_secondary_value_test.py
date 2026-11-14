"""Offline test of backtest/baseball_secondary_value.py (framework #569, step 4). No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import baseball_secondary_value as bb  # noqa: E402


def side(first, last):
    return {"first": {"price": first}, "last": {"price": last}}


game = {"home": "A", "away": "B", "ko": "k", "result": {"final": [5, 1]}, "sides": {
    "baseball:251||Home": side(1.70, 1.70), "baseball:251||Away": side(2.10, 2.10),
    "baseball:256|hcp=-1.5|Home (-1.5)": side(2.35, 2.30), "baseball:256|hcp=-1.5|Away (+1.5)": side(1.60, 1.62),
    "baseball:258|total=8.5|Over 8.5": side(1.74, 1.74), "baseball:258|total=8.5|Under 8.5": side(1.97, 1.97),
    "baseball:258|total=12.5|Over 12.5": side(4.00, 4.00),                    # outside the band
}}
assert bb.final_ok({"final": [5, 1]}) == (5, 1) and bb.final_ok({"final": [3, 3]}) is None and bb.final_ok(None) is None
assert bb.bets(game, [9] * 5) == [], "short history: PENDING, not invented"
hist = [9] * 30
b = bb.bets(game, hist)
assert {x["family"] for x in b} == {"Run line", "Total runs"}, b
rl = {x["price"]: x for x in b if x["family"] == "Run line"}
assert rl[2.35]["won"] == 1 and rl[1.60]["won"] == 0                          # 5-1: home -1.5 covers, away +1.5 does not
assert abs(rl[2.35]["p"] + rl[1.60]["p"] - 1) < 1e-6, "the two run-line sides cover everything"
tot = {x["price"]: x for x in b if x["family"] == "Total runs"}
assert tot[1.74]["won"] == 0 and tot[1.97]["won"] == 1                        # 6 runs: under 8.5
assert abs(tot[1.74]["p"] + tot[1.97]["p"] - 1) < 1e-9 and all(x["clv"] is not None for x in b)
assert bb.bets({**game, "result": None}, hist) == [], "no result: not graded (PENDING)"
assert bb.bets({"result": {"final": [2, 1]}, "sides": {}}, hist) == []
docs = [(f"2026-10-{d:02d}", {"games": {"x": {**game, "ko": f"k{d}"}}}) for d in range(1, 32)]
text = bb.build(docs + [("2026-11-05", {"games": {"y": {**game, "ko": "late"}}})])
assert "Run line" in text and "Total runs" in text, text
assert "NO DATA — PENDING" in bb.build([]) and "NO DATA — PENDING" in bb.build(docs[:5])
print("baseball secondary value: OK")
