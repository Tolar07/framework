"""Offline test of backtest/tennis_secondary_value.py (framework #569, step 3). No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backtest")]

import tennis_secondary_value as tv  # noqa: E402


def side(price, last):
    return {"first": {"price": price}, "last": {"price": last}}


def game(periods, winner=1, comp="ATP Challenger X, Men Singles", home="A B"):
    return {"comp": comp, "home": home, "away": "C D", "ko": "k", "result": {"periods": periods, "winner": winner},
            "sides": {
                "tennis:186||Home": side(1.80, 1.80), "tennis:186||Away": side(2.00, 2.00),
                "tennis:202|setnr=1|Home": side(2.20, 2.10), "tennis:202|setnr=1|Away": side(1.65, 1.70),
                "tennis:202|setnr=3|Home": side(2.00, 2.00),                    # set 3: PENDING
                "tennis:188|hcp=-1.5|Home (-1.5)": side(3.00, 3.0),             # outside the band
                "tennis:188|hcp=1.5|Home (+1.5)": side(1.60, 1.60),
                "tennis:189|total=21.5|Over 21.5": side(1.90, 1.80),
                "tennis:189|total=21.5|Under 21.5": side(1.90, 2.00)}}


g = game([[6, 4], [6, 3]])
b = tv.bets(g)
fams = {x["family"] for x in b}
assert fams == {"Set 1 winner", "Set handicap +-1.5", "Total games"}, fams
assert all(1.6 <= x["price"] <= 2.6 and 0 < x["p"] < 1 for x in b)
s1 = [x for x in b if x["family"] == "Set 1 winner"]
assert len(s1) == 2 and sum(x["won"] for x in s1) == 1 and abs(sum(x["p"] for x in s1) - 1) < 1e-9
hc = next(x for x in b if x["family"] == "Set handicap +-1.5")
assert hc["won"] == 1                                                 # home +1.5 with a 2-0 win
over = next(x for x in b if x["price"] == 1.90 and x["won"] == 0)     # 19 games: over 21.5 lost, under won
assert over["clv"] is not None and abs(over["clv"] - (1.9 * (1 / 1.8) / (1 / 1.8 + 1 / 2.0) - 1)) < 1e-9
assert tv.bets({**g, "result": None}) == [], "no result: PENDING"
assert tv.bets(game([[6, 4], [3, 2]])) == [], "retirement mid-set: left out"
assert tv.bets(game([[6, 4]])) == [], "one set only: left out"
assert tv.bets(game([[6, 4], [6, 3]], home="A B / E F")) == [], "doubles: not modelled"
text = tv.build([("2026-11-11", {"games": {"g": g, "dup": g}})])
assert "Matches graded: 1" in text and "Total games" in text and "COLLECTING (" in text, text
assert "NO DATA — PENDING" in tv.build([])
print("tennis secondary value: OK")
