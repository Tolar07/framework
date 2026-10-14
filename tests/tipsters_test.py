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

dn = Path(tempfile.mkdtemp())            # 12 Oct: kickoff and post time written with no zone
naive = {**slip, "post_url": "u-naive", "posted_at": "2026-10-09T10:00:00",
         "legs": [{**leg, "kickoff": "2026-10-09T15:00"} for leg in slip["legs"]]}
(dn / "slips_2026-10-09.jsonl").write_text(json.dumps(naive) + "\n", encoding="utf-8")
assert tp.grade_due(dn, idx, datetime(2026, 10, 9, 16, tzinfo=UTC)) == [], "a zone-less kickoff is UTC"
assert tp.grade_due(dn, idx, datetime(2026, 10, 9, 19, tzinfo=UTC)) == ["None: lost"], "and grades without crashing"
print("zone-less kickoff read as UTC: OK")

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

# ── closing-line value (backtest/tipster_study.py) ───────────────────────────
from backtest import tipster_study as ts  # noqa: E402

uni = [{"sport": "football", "id": "sr:match:7", "ko": "2026-10-10T15:00Z", "home": "Home FC", "away": "Away FC",
        "first": {"at": "2026-10-09T09:00Z", "p": {"1x2": [2.0, 3.4, 3.8], "ou2.5": [1.9, 1.9]}},
        "last": {"at": "2026-10-10T13:00Z", "p": {"1x2": [1.8, 3.6, 4.4], "ou2.5": [2.0, 1.8],
                                                  "dc": [1.25, 1.3, 2.0]}}}]
idx = ts.UniverseIndex(uni)
home = {"sport": "football", "market": "1x2", "selection": "home", "price": 2.0, "sb": {"event": "sr:match:7"}}
r = ts.leg_clv(home, "2026-10-09T10:00Z", idx)
assert abs(r["clv"] - (2.0 / 1.8 - 1)) < 1e-9 and r["move"] > 0 and r["ev_close"] > 0 and round(r["lead_h"]) == 29
assert ts.leg_clv(home, "2026-10-10T14:00Z", idx) is None, "entry read after the last look: no close"
by_name = {"sport": "football", "market": "ou", "selection": "over", "line": 2.5, "price": 1.9,
           "home": "Home FC", "away": "Away FC", "kickoff": "2026-10-10T15:00Z"}
assert ts.leg_clv(by_name, "2026-10-09T10:00Z", idx)["clv"] < 0, "found by name; over drifted 1.9 -> 2.0"
dc = ts.leg_quote({"sport": "football", "market": "dc", "selection": "1x"}, uni[0]["last"]["p"])
assert dc[0] == 1.25 and 0.7 < dc[1] < 0.8
assert ts.leg_quote({"sport": "football", "market": "ah", "selection": "home", "line": -1}, uni[0]["last"]["p"]) is None
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp)
    leg = {**home, "home": "Home FC", "away": "Away FC", "kickoff": "2026-10-10T15:00Z", "result": "win"}
    (f / "graded_2026-10-09.jsonl").write_text(json.dumps({
        "post_url": "https://x.com/a/status/1", "poster": "@a", "official": False, "book": "sportybet",
        "posted_at": "2026-10-09T09:30:00Z", "status": "won", "payout": 2.0, "implied": 0.5,
        "legs": [leg], "unknown": []}) + "\n")
    (f / "decoded_2026-10-09.jsonl").write_text(json.dumps({
        "post_url": "https://x.com/a/status/1", "decoded_at": "2026-10-09T10:00Z", "legs": [leg]}) + "\n")
    text = ts.write(f, f / "TIPSTER_STUDY.md", universe_rows=uni)
    assert "1 of 1 legs measured against the close" in text and "| @a | 1 | +11.1%" in text, text[-900:]
    assert json.loads((f / "aggregates.json").read_text())["clv"]["legs_measured"] == 1
    assert "NO DATA — PENDING" in ts.write(f, f / "T.md", universe_rows=[])
up = {"sport": "football", "market": "1up", "selection": "home", "price": 1.6, "sb": {"event": "sr:match:7"}}
uni_up = [{**uni[0], "last": {**uni[0]["last"], "p": {**uni[0]["last"]["p"], "1up": [1.5, 3.4, 2.6]}}}]
r_up = ts.leg_clv(up, "2026-10-09T10:00Z", ts.UniverseIndex(uni_up))
assert abs(r_up["clv"] - (1.6 / 1.5 - 1)) < 1e-9 and r_up["ev_close"] is None and r_up["move"] is None, \
    "1UP rows don't add up to one: CLV only, no margin-free EV"
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp)
    nop = {"sport": "football", "market": "team_total", "selection": "over", "line": 1.5, "team": "home",
           "price": None, "home": "Home FC", "away": "Away FC", "kickoff": "2026-10-10T15:00Z", "result": "win"}
    (f / "graded_2026-10-10.jsonl").write_text(json.dumps({
        "post_url": "https://x.com/b/status/2", "poster": "@b", "official": False, "book": "bet365",
        "posted_at": "2026-10-10T09:00:00Z", "status": "won", "payout": 1.5, "implied": 1.0,
        "legs": [nop, {**home, "home": "Home FC", "away": "Away FC", "kickoff": "2026-10-10T15:00Z",
                       "result": "win"}], "unknown": []}) + "\n")
    assert "Legs by class" in ts.write(f, f / "T.md", universe_rows=uni_up), "a leg with no price must not crash the study"
print("closing-line value of tipster legs: OK")

# ── the collector writes loose JSON; the grader must not assume clean types ──
# 2026-10-14: the scheduled grader crashed on EVERY run from 13 Oct with
#   implied *= 1 / leg["price"] ... TypeError: unsupported operand type(s)
#   for /: 'int' and 'str'
# because a bet365 leg's price was the string "1.85" (the collector session
# writes those legs straight into the slip JSON). Collection carried on, so
# graded_*.jsonl silently stopped at 12 Oct while slips kept arriving.
assert tp._num("1.85") == 1.85 and tp._num(1.85) == 1.85, "a price given as text is still a price"
assert tp._num("2,10") == 2.10, "a decimal comma is a decimal point"
assert tp._num(" 1.50 ") == 1.5 and tp._num("+1.75") == 1.75, "padding and a leading + are not values"
assert tp._num("-1.5") == -1.5, "a handicap line can be negative"
for junk in ("", "abc", "evs", None, True, [], {}):
    assert tp._num(junk) is None, f"{junk!r} is not a number and must read None, never a guess (HR35)"

with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp)
    str_leg = {"sport": "football", "home": "Norwich", "away": "Southampton",
               "kickoff": "2026-10-13T18:45Z", "market": "ou", "selection": "over",
               "line": "2.5", "price": "1.85", "text": "Over 2.5"}
    (f / "slips_2026-10-13.jsonl").write_text(json.dumps({
        "poster": "@a", "post_url": "https://x.com/a/status/9", "book": "bet365",
        "posted_at": "2026-10-13T10:00:00Z", "stated_odds": "3.52", "legs": [str_leg]}) + "\n"
        # a half-written line: the collector appends from a browser session, and
        # one torn line used to take every slip in the file down with it
        + '{"poster": "@b", "post_url": "https://x.com/b/status/8", "legs": [{"pri\n',
        encoding="utf-8")
    _slips = tp.load_slips(f)
    assert len(_slips) == 1, "the torn line is skipped, the good slip still loads"
    _leg = _slips[0]["legs"][0]
    assert _leg["price"] == 1.85 and _leg["line"] == 2.5 and _slips[0]["stated_odds"] == 3.52, \
        "every number is coerced where the row is READ, not at each of the eight uses"
    _implied = 1.0
    for _lg in _slips[0]["legs"]:                      # the exact line that crashed
        _implied *= 1 / _lg["price"] if _lg.get("price") else 1.0
    assert abs(_implied - 1 / 1.85) < 1e-9
    assert tp.settle(_leg, 2, 1) == "win" and tp.leg_class(_leg) == "middle", \
        "a coerced line settles and classes like a native number"
print("loose types from the collector: OK")

print("ALL TIPSTER TESTS PASSED")
