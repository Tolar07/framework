"""
Offline test of the results loop (data.flashscore_results + engine.picks_ledger):
feed parsing, strict name matching, regular-time-only grading, won/lost/void
settlement, acca outcomes and the scorecard. No network.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import flashscore_results as fs
from engine import picks_ledger as pl
from engine import full_markets as fm

# --- feed parsing: one regular-time finish, one after penalties ------------
FEED = ("SA÷1¬~ZA÷ENGLAND: League Two¬~AA÷x1¬AD÷1791036000¬AB÷3¬AC÷3¬AE÷Bristol Rovers"
        "¬AF÷Crewe¬AG÷2¬AH÷1¬~AA÷x2¬AD÷1791036000¬AB÷3¬AC÷11¬AE÷Grimsby¬AF÷Shrewsbury"
        "¬AG÷1¬AH÷1¬~ZA÷WORLD: Friendly¬~AA÷x3¬AD÷1791036000¬AB÷1¬AC÷1¬AE÷Spain¬AF÷Czechia¬")
ev = fs.parse_feed(FEED)
assert len(ev) == 3 and ev[0]["finished_regular"] and not ev[1]["finished_regular"]
assert ev[1]["finished_other"] and not ev[2]["finished_regular"]
print("feed parsing (regular time only): OK")

# --- strict matching ---------------------------------------------------------
assert fs.find_result(ev, "Bristol Rvs", "Crewe", "2026-10-03")["fthg"] == 2
assert fs.find_result(ev, "Bristol Rvs", "Crewe", "2026-09-20") is None, "wrong date never matches"
assert fs.find_result(ev, "Man City", "Crewe", "2026-10-03") is None
assert fs._sim("Man City", "Manchester Utd") < fs.MATCH_MIN, "Man City must never match Man Utd"
assert fs.find_result(ev, "Czech Republic", "Spain", "2026-10-03") is None, "home/away order matters"
print("strict name/date matching: OK")

# --- ledger grading ---------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    pl.LEDGER_DIR = Path(d)
    doc = {"date": "2026-10-03", "generated_at": "", "singles": [
        {"fixture": "Bristol Rvs v Crewe", "league": "League Two", "home": "Bristol Rvs",
         "away": "Crewe", "kickoff": "2026-10-03", "market": "1X2_HOME", "pick": "x",
         "price": 1.80, "chance": 0.6, "tier": "SAFE", "certainty": "HIGH", "code": "A",
         "result": None, "ft": None},
        {"fixture": "Bristol Rvs v Crewe", "league": "League Two", "home": "Bristol Rvs",
         "away": "Crewe", "kickoff": "2026-10-03", "market": fm.key(16, "hcp=-1", "Home (-1.0)"),
         "pick": "x", "price": 1.9, "chance": 0.5, "tier": "SAFE", "certainty": "MEDIUM",
         "code": "B", "result": None, "ft": None},
        {"fixture": "Grimsby v Shrewsbury", "league": "League Two", "home": "Grimsby",
         "away": "Shrewsbury", "kickoff": "2026-10-03", "market": "1X2_HOME", "pick": "x",
         "price": 1.5, "chance": 0.7, "tier": "BOOK", "certainty": "LOW", "code": "C",
         "result": None, "ft": None}],
        "accas": [{"name": "Acca A", "code": "Z", "odds": 3.0, "chance": 0.4,
                   "legs": ["Bristol Rvs v Crewe", "Grimsby v Shrewsbury"], "result": None}],
        "safe3": [], "megas": []}
    (Path(d) / "picks_2026-10-03.json").write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all(ev, today="2026-10-04")
    out = json.loads((Path(d) / "picks_2026-10-03.json").read_text(encoding="utf-8"))
    s = out["singles"]
    assert s[0]["result"] == "won" and s[0]["ft"] == "2-1"
    assert s[1]["result"] == "void", "Asian -1 on a one-goal win is a push"
    assert s[2]["result"] == "no-90min-result", "penalties: never guessed"
    assert out["accas"][0]["result"] is None, "acca stays pending until every leg settles"
    card = pl.scorecard(7, today="2026-10-04")
    assert "1W-0L-1V" in card and "+0.80u" in card, card
print("ledger grading + scorecard: OK")

# --- after extra time: settled only when every possible 90' score agrees ----
AET = ("SA÷1¬~ZA÷ENGLAND: FA Cup - Qualification¬~AA÷x9¬AD÷1791312300¬AB÷3¬AC÷10¬"
       "AE÷Scarborough¬AF÷Macclesfield¬AG÷1¬AH÷2¬BC÷0¬BD÷1¬")
ev2 = fs.parse_feed(AET)
assert ev2[0]["finished_other"] and (ev2[0]["fh_home"], ev2[0]["fh_away"]) == (1, 1)
# HT 1-1, final 1-2 (aet) -> 90' was 1-1 or 1-2
assert pl._settle_90_bounds("1X2_HOME", ev2[0]) == "lost", "home won neither way"
assert pl._settle_90_bounds("1X2_AWAY", ev2[0]) is None, "1-1 or 1-2: never guessed"
assert pl._settle_90_bounds(fm.key(18, "total=1.5", "Over 1.5"), ev2[0]) == "won"
with tempfile.TemporaryDirectory() as d:
    pl.LEDGER_DIR = Path(d)
    doc = {"date": "2026-10-06", "generated_at": "", "singles": [
        {"fixture": "Scarborough v Macclesfield", "league": "FA Cup", "home": "Scarborough",
         "away": "Macclesfield", "kickoff": "2026-10-06", "market": "1X2_HOME", "pick": "x",
         "price": 2.5, "chance": 0.4, "tier": "SAFE", "certainty": "LOW", "code": "S",
         "result": "no-90min-result", "ft": None}], "accas": [], "safe3": [], "megas": []}
    (Path(d) / "picks_2026-10-06.json").write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all(ev2, today="2026-10-07")
    out = json.loads((Path(d) / "picks_2026-10-06.json").read_text(encoding="utf-8"))
    assert out["singles"][0]["result"] == "lost", "an earlier no-90min-result is re-checked"
print("after extra time: settled from the half-time..final range only when certain: OK")

assert fs._sim("Denizli Idman Yurdu", "Denizli IY Gureller") == 1.0
assert fs._sim("Serik Belediyespor", "Serik Spor") == 1.0
print("Turkish club aliases: OK")

print("\n✅ ALL RESULTS-LOOP TESTS PASSED")
