"""Both sides study: every side is a yes/no record; learning is gated like engine/learning.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backtest"))

import both_sides_study as bs  # noqa: E402

row = {"sport": "football", "first": {"p": {"1x2": [2.0, 3.4, 4.0], "btts": [1.8, 1.95], "dc": [1.25, 1.33, 1.8]}},
       "result": {"h": 1, "a": 0}}
recs = bs.records(row)
keys = {r["key"]: r for r in recs}
Y, N = "SB:29||Yes", "SB:29||No"
DC = ("SB:10||Home or Draw", "SB:10||Home or Away", "SB:10||Draw or Away")
assert {Y, N, "SB:1||Home", "SB:1||Draw", "SB:1||Away", *DC} <= set(keys)
assert keys[N]["won"] == 1 and keys[Y]["won"] == 0, "both sides of BTTS are records"
assert abs(keys[Y]["fair"] + keys[N]["fair"] - 1) < 1e-9
assert abs(sum(keys[k]["fair"] for k in DC) - 2) < 1e-9, "double chance covers each result twice"
assert bs.band(1.25) == "1.20-1.40" and bs.band(3.5) == "3.00+"

# too few records: nothing learned; many records far off: a capped shift
few = [{"seg": "s", "won": 1, "fair": 0.5}] * 10
assert bs.learn(few) == {}
many = [{"seg": "s", "won": 1, "fair": 0.5}] * 200
assert 0 < bs.learn(many)["s"] <= bs.MAX_SHIFT
print("both_sides_study_test: OK")

# every market SportyBet prices is kept and becomes yes/no records (2026-10-12)
from engine import universe as uv  # noqa: E402

ev = {"markets": [
    {"id": "1", "status": 0, "outcomes": [{"desc": "Home", "odds": "2.0"}, {"desc": "Draw", "odds": "3.4"},
                                          {"desc": "Away", "odds": "4.0"}]},
    {"id": "16", "status": 0, "specifier": "hcp=1.5",
     "outcomes": [{"desc": "Home (+1.5)", "odds": "1.15"}, {"desc": "Away (-1.5)", "odds": "5.0"}]},
    {"id": "26", "status": 0, "outcomes": [{"desc": "Odd", "odds": "1.9"}, {"desc": "Even", "odds": "1.9"}]},
    {"id": "33", "status": 2, "outcomes": [{"desc": "Yes", "odds": "3.0"}, {"desc": "No", "odds": "1.3"}]}]}
px = uv.prices("football", ev)
assert set(px["ladder"]) == {"SB:1||Home", "SB:1||Draw", "SB:1||Away", "SB:16|hcp=1.5|Home (+1.5)",
                             "SB:16|hcp=1.5|Away (-1.5)", "SB:26||Odd", "SB:26||Even"}, "closed lines are not kept"
row = {"sport": "football", "first": {"p": px}, "result": {"h": 1, "a": 0}}
got = {r["key"]: r["won"] for r in uv.all_records(row)}
assert got["SB:16|hcp=1.5|Home (+1.5)"] == 1 and got["SB:16|hcp=1.5|Away (-1.5)"] == 0, "underdog handicaps are learned"
assert got["SB:26||Odd"] == 1 and got["SB:26||Even"] == 0
# an old row (no ladder) is renamed into the same keys
old = {"sport": "football", "first": {"p": {"btts": [1.8, 1.95], "ou2.5": [2.0, 1.8]}}, "result": {"h": 2, "a": 1}}
got = {r["key"]: r["won"] for r in uv.all_records(old)}
assert got == {"SB:29||Yes": 1, "SB:29||No": 0, "SB:18|total=2.5|Over 2.5": 1, "SB:18|total=2.5|Under 2.5": 0}
# basketball: every total and handicap line, both sides; an exact landing is a push, left out
bev = {"markets": [{"id": "225", "status": 0, "specifier": "total=200.5",
                    "outcomes": [{"desc": "Over 200.5", "odds": "1.9"}, {"desc": "Under 200.5", "odds": "1.9"}]},
                   {"id": "223", "status": 0, "specifier": "hcp=-5",
                    "outcomes": [{"desc": "Home (-5)", "odds": "1.9"}, {"desc": "Away (+5)", "odds": "1.9"}]}]}
bpx = uv.prices("basketball", bev)
got = {r["key"]: r["won"] for r in uv.all_records({"sport": "basketball", "first": {"p": bpx},
                                                   "result": {"h": 105, "a": 100}})}
assert got == {"total|200.5|over": 1, "total|200.5|under": 0}, got   # home won by exactly 5: handicap pushes
print("all markets: OK")
