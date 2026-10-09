"""
Offline test of the tipster-slip learner (engine/tipsters.py): SportyBet
share-code legs mapped to the vocabulary, settlement (incl. pushes and
quarter handicaps), leg classes, and grading that never needs a result for
a slip that has already lost a leg. No real slip or handle is used.
"""
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import fotmob as fm
from engine import tipsters as tp


def ev(mid, desc, odds, spec=None, sport="sr:sport:1"):
    return {"eventId": "sr:match:1", "homeTeamName": "Home FC", "awayTeamName": "Away FC",
            "estimateStartTime": int(datetime(2026, 10, 9, 18, tzinfo=UTC).timestamp() * 1000),
            "sport": {"id": sport, "category": {"name": "X", "tournament": {"name": "Y"}}},
            "markets": [{"id": mid, "specifier": spec, "desc": "m", "status": 0,
                         "outcomes": [{"id": "1", "desc": desc, "odds": str(odds), "isActive": 1}]}]}


assert tp.map_leg(ev("10", "Home or Draw", 1.3))["market"] == "dc"
leg = tp.map_leg(ev("18", "Over 2.5", 1.8, "total=2.5"))
assert (leg["market"], leg["selection"], leg["line"], leg["kickoff"]) == ("ou", "over", 2.5, "2026-10-09T18:00Z")
assert tp.map_leg(ev("16", "Away (+0.75)", 1.9, "hcp=-0.75"))["line"] == 0.75
assert tp.map_leg(ev("227", "Over 85.5", 1.8, "total=85.5", "sr:sport:2"))["team"] == "home"
assert tp.map_leg(ev("900302", "Over 1.5", 1.4, "total=1.5"))["market"] == "other"     # 1st-half corners
print("share-code legs mapped: OK")

assert tp.settle({"market": "1x2", "selection": "draw"}, 1, 1) == "win"
assert tp.settle({"market": "dnb", "selection": "home"}, 0, 0) == "push"
assert tp.settle({"market": "ah", "selection": "away", "line": 0.25}, 1, 1) == "half_win"
assert tp.settle({"market": "ah", "selection": "home", "line": -0.75}, 1, 0) == "half_win"
assert tp.settle({"market": "team_total", "selection": "under", "line": 1.5, "team": "away"}, 3, 1) == "win"
assert tp.settle({"market": "other"}, 1, 0) is None
assert abs(tp.leg_factor("half_win", 1.9) - 1.45) < 1e-9 and tp.leg_factor("half_lose", 1.9) == 0.5
print("settlement incl. pushes and quarter lines: OK")

assert [tp.leg_class({"market": m, "price": p}) for m, p in
        (("dc", 1.30), ("ou", 1.80), ("1x2", 3.5), ("other", 1.2))] == ["aligned", "middle", "risky", "risky"]
print("leg classes: OK")


class Idx:
    def __init__(self, res):
        self.res = res

    def find(self, home, away, ko):
        return self.res.get(home)


d = Path(tempfile.mkdtemp())
slip = {"poster": "@x", "post_url": "u1", "posted_at": "2026-10-09T10:00:00Z", "book": "bet365",
        "legs": [{"sport": "football", "home": "A", "away": "B", "kickoff": "2026-10-09T15:00Z",
                  "market": "dc", "selection": "1x", "price": 1.3},
                 {"sport": "football", "home": "C", "away": "D", "kickoff": "2026-10-09T15:00Z",
                  "market": "other", "price": 6.0, "text": "exotic"},
                 {"sport": "football", "home": "E", "away": "F", "kickoff": "2026-10-09T15:00Z",
                  "market": "1x2", "selection": "home", "price": 1.5}]}
(d / "slips_2026-10-09.jsonl").write_text(json.dumps(slip) + "\n", encoding="utf-8")
fin = {"finished_regular": True, "finished_other": False}
idx = {"football": Idx({"A": {**fin, "fthg": 2, "ftag": 0}, "E": {**fin, "fthg": 0, "ftag": 1}})}
assert tp.grade_due(d, idx, datetime(2026, 10, 9, 16, tzinfo=UTC)) == [], "not 3 h after kick-off yet"
assert tp.grade_due(d, idx, datetime(2026, 10, 9, 19, tzinfo=UTC)) == ["None: lost"]
g = tp.load_graded(d)[0]
assert g["status"] == "lost" and g["payout"] == 0.0 and g["unknown"] == ["exotic"], "a lost leg settles the slip"
assert tp.grade_due(d, idx, datetime(2026, 10, 9, 20, tzinfo=UTC)) == [], "graded once"
print("grading (a slip that lost a leg needs no other result): OK")

posted = datetime(2026, 10, 9, 8, tzinfo=UTC)
assert tp._kickoff({"kickoff": "Newmarket 1:15"}, posted) == posted, "a race card is not a date"
assert tp._kickoff({"kickoff": None}, posted) == posted and tp._kickoff({}, posted) == posted
print("unparsable kick-off falls back to the post time: OK")

# SportyBet specials seen on slips (2026-10-09): mapped, re-mapped from old decodes, settled
def sb_leg(mid, mdesc, odesc, spec=""):
    return tp.map_leg({"sport": {"id": "sr:sport:1"}, "homeTeamName": "A", "awayTeamName": "B",
                       "markets": [{"id": mid, "desc": mdesc, "specifier": spec,
                                    "outcomes": [{"desc": odesc, "odds": "1.30"}]}]})


up2 = sb_leg(60100, "1X2 - 2UP", "Home")
assert (up2["market"], up2["selection"]) == ("2up", "home") and tp.leg_class(up2) == "special"
old = {**up2, "market": "other", "selection": None}
assert tp.remap(old)["market"] == "2up", "a leg decoded before 2UP was known is mapped again"
assert tp.remap({"market": "other", "text": "Corners: Over 1.5", "sb": {"market": "900302"}})["market"] == "other"
oo = sb_leg(854, "Home Team or Over 2.5", "Yes", "total=2.5")
assert (oo["market"], oo["team"], oo["line"]) == ("or_over", "home", 2.5)
assert tp.settle(oo, 1, 0) == "win" and tp.settle(oo, 1, 2) == "win" and tp.settle(oo, 0, 1) == "lose"
we = sb_leg(51, "Away Team to Win Either Half", "Yes")
assert tp.settle(we, 1, 1, [1, 0]) == "win", "lost the 1st half 1-0, won the 2nd 1-0"
assert tp.settle(we, 1, 1, [0, 0]) == "lose" and tp.settle(we, 1, 1) is None, "no half-time score: can't settle"
r3 = sb_leg(60021, "Home Team To Score 3 or More Goals in a Row", "No")
assert tp.settle(r3, 2, 0) == "win", "home scored only twice: the 'No' is safe on the score alone"
assert tp.settle(r3, 3, 1) is None
assert tp.settle(r3, 3, 1, None, [[5, "h"], [20, "a"], [40, "h"], [60, "h"]]) == "win"
assert tp.settle(r3, 3, 1, None, [[5, "h"], [20, "h"], [40, "h"], [60, "a"]]) == "lose"
assert tp.settle(up2, 2, 2) is None and tp.settle(up2, 2, 2, None, [[1, "h"], [2, "h"], [3, "a"], [4, "a"]]) == "win"
d1 = sb_leg(60110, "Double Chance - 1UP", "Home or Draw")
assert tp.settle(d1, 0, 1) == "lose" and tp.settle(d1, 1, 2, None, [[3, "h"], [50, "a"], [60, "a"]]) == "win"
assert tp.settle({"market": "dc_1up", "selection": "12"}, 1, 1) == "win", "a scored draw had a 1-goal lead"
assert tp.settle({"market": "ou", "selection": "over", "line": 2.0}, 1, 1) == "push", "Asian Over 2 on exactly 2"
print("SportyBet specials (2UP/1UP, or Over, either half, 3 in a row): OK")

# grading asks the goal-time source only when the score can't settle a leg, and checks it
d = Path(tempfile.mkdtemp())
slip = {"poster": "@x", "post_url": "u2", "posted_at": "2026-10-09T10:00:00Z", "book": "sportybet",
        "legs": [{**up2, "kickoff": "2026-10-09T15:00Z", "price": 1.3}]}
(d / "slips_2026-10-09.jsonl").write_text(json.dumps(slip) + "\n", encoding="utf-8")
idx = {"football": Idx({"A": {**fin, "fthg": 2, "ftag": 2}})}
asked = []


def tl(home, away, ko):
    asked.append(ko)
    return {"goals": [[1, "h"], [2, "h"], [3, "a"], [4, "a"]], "ht": [2, 0]}


assert tp.grade_due(d, idx, datetime(2026, 10, 9, 19, tzinfo=UTC), tl) == ["None: won"] and asked == ["2026-10-09T15:00Z"]
print("grading with goal times (2UP paid at 2-0 in a 2-2 game): OK")

assert fm.timeline({"content": {"matchFacts": {"events": {"events": [
    {"type": "Goal", "time": 16, "newScore": [1, 0]}, {"type": "Half", "halfStrShort": "HT", "homeScore": 1, "awayScore": 0},
    {"type": "Goal", "time": 90, "overloadTime": 4, "isHome": True, "ownGoal": True, "newScore": [1, 1]},
    {"type": "Goal", "time": 105, "newScore": [2, 1]}]}}}}) == {"goals": [[16, "h"], [90, "a"]], "ht": [1, 0]}, \
    "own goal read from the running score; stoppage time in, extra time out"
assert fm.timeline({"content": {"matchFacts": {"events": {"events": [{"type": "Goal", "time": 3, "newScore": [2, 0]}]}}}}) is None
print("FotMob goal timeline: OK")

print("ALL TIPSTER TESTS PASSED")
