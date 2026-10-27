"""
No PENDING left that a second source can settle (Architect 2026-10-26: "Make sure
I don't get pending. Make sure everything is properly verified"). On 25 Oct five
singles stayed PENDING on Flashscore alone: three games missing from its feed,
'VfL 1899 Osnabruck' against Flashscore's 'VfL Osnabruck', and Barcelona v Real
Madrid. grade_all now asks FotMob for what Flashscore lacks: by the pick's own
FotMob id, else the same strict two-name match, and only for a 90-minute 'FT'.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import flashscore_results as fs
from engine import picks_ledger as pl


def single(home, away, market, fotmob_id=None):
    return {"fixture": f"{home} v {away}", "home": home, "away": away, "market": market,
            "kickoff": "2026-10-25T12:30:00Z", "fotmob_id": fotmob_id, "result": None}


FOTMOB = [
    {"id": 5811784, "home": "Genk", "away": "Standard Liège", "kickoff_utc": "2026-10-25T12:30:00.000Z",
     "finished": True, "reason": "FT", "awarded": False, "score": [2, 1]},
    {"id": 1, "home": "Sporting CP", "away": "Académico Viseu", "kickoff_utc": "2026-10-25T20:30:00.000Z",
     "finished": True, "reason": "FT", "awarded": False, "score": [1, 2]},
    {"id": 2, "home": "Cup Home", "away": "Cup Away", "kickoff_utc": "2026-10-25T18:00:00.000Z",
     "finished": True, "reason": "Pen", "awarded": False, "score": [1, 1]},
    {"id": 3, "home": "Late Home", "away": "Late Away", "kickoff_utc": "2026-10-25T22:00:00.000Z",
     "finished": False, "reason": "", "awarded": False, "score": [0, 0]},
]
asked = []


def fotmob_day(day):
    asked.append(day)
    return FOTMOB if day == "2026-10-25" else []


with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    doc = {"date": "2026-10-25", "singles": [
        single("Genk", "Standard", "SB:10||Home or Away", fotmob_id=5811784),   # by id
        single("Sp Lisbon", "Academico de Viseu FC", "SB:18|total=4.5|Under 4.5"),  # by name
        single("Cup Home", "Cup Away", "SB:10||Home or Away"),                  # penalties
        single("Late Home", "Late Away", "SB:10||Home or Away"),                # not finished
        single("Nobody", "Anywhere", "SB:10||Home or Away"),                    # in neither feed
    ], "accas": []}
    path = pl.LEDGER_DIR / "picks_2026-10-25.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    flags = pl.grade_all([], today="2026-10-26", fotmob_day=fotmob_day)
    res = {s["fixture"]: (s["result"], s.get("ft")) for s in
           json.loads(path.read_text(encoding="utf-8"))["singles"]}
    assert res["Genk v Standard"] == ("won", "2-1"), res
    assert res["Sp Lisbon v Academico de Viseu FC"] == ("won", "1-2"), res     # 3 goals: Under 4.5
    assert res["Cup Home v Cup Away"][0] == "no-90min-result", res            # never guessed
    assert res["Late Home v Late Away"][0] is None, res
    assert res["Nobody v Anywhere"][0] is None, res
    assert any("taken from FotMob" in f for f in flags), flags
    assert "2026-10-27" not in asked, "never asks FotMob about a future day"

    # without the second source (tests, offline) grading behaves exactly as before
    path.write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all([], today="2026-10-26")
    assert all(s["result"] is None for s in json.loads(path.read_text(encoding="utf-8"))["singles"])

# the two names that kept 25 Oct singles off Flashscore
assert fs._sim("VfL 1899 Osnabruck", "VfL Osnabruck") >= fs.MATCH_MIN
assert fs._sim("Sp Lisbon", "Sporting CP") >= fs.MATCH_MIN
assert fs._sim("Sp Lisbon", "Sporting Gijon") < fs.MATCH_MIN
print("fotmob_grading_test: OK")
