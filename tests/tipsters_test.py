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
assert tp.map_leg(ev("60021", "Yes", 9.0))["market"] == "other"
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

print("ALL TIPSTER TESTS PASSED")
