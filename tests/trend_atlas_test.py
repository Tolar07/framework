"""
data/espn_history.py + engine/trend_atlas.py + backtest/trend_atlas_study.py. Offline: a hand-made ESPN event,
hand-made matches and SportyBet prices; no network.
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backtest"))
from data import espn_history as eh  # noqa: E402
from engine import trend_atlas as ta  # noqa: E402
import trend_atlas_study as tas  # noqa: E402


def team(tid, ha, name, score, corners=5):
    return {"homeAway": ha, "score": str(score), "team": {"id": tid, "displayName": name},
            "statistics": [{"name": "wonCorners", "displayValue": str(corners)}, {"name": "foulsCommitted", "displayValue": "10"},
                           {"name": "totalShots", "displayValue": "12"}, {"name": "shotsOnTarget", "displayValue": "4"}]}


def det(minute, tid, goal=False, y=False, r=False):
    return {"clock": {"displayValue": minute}, "team": {"id": tid}, "scoringPlay": goal, "yellowCard": y, "redCard": r}


EV = {"id": "1", "uid": "s:600~l:770~e:1", "date": "2025-03-15T15:00Z", "season": {"year": 2025, "slug": "regular-season"},
      "status": {"type": {"completed": True, "name": "STATUS_FULL_TIME"}},
      "competitions": [{"altGameNote": "MLS", "competitors": [team("10", "home", "A FC", 2, 6), team("20", "away", "B FC", 1, 3)],
                        "details": [det("12'", "10", goal=True), det("45'+2'", "20", goal=True), det("50'", "20", y=True),
                                    det("88'", "10", goal=True), det("90'+3'", "10", r=True)]}]}
m = eh.parse_event(EV)
assert m["lid"] == "770" and m["league"] == "MLS" and m["ft"] == [2, 1], m
assert m["goals"] == [[12, 0], [45, 1], [88, 0]] and m["ht"] == [1, 1], m        # 45'+2' is first half
assert m["cards"] == [[50, 1, "Y"], [90, 0, "R"]] and m["corners"] == [6, 3]
# goal minutes that don't add up to the score are dropped (HR35), and so is the half-time score built from them
bad = {**EV, "competitions": [{**EV["competitions"][0], "details": [det("12'", "10", goal=True)]}]}
assert eh.parse_event(bad)["goals"] is None and eh.parse_event(bad)["ht"] is None
# extra time / penalties: not a 90-minute result
aet = {**EV, "status": {"type": {"completed": True, "name": "STATUS_FINAL_AET"}}}
assert eh.parse_event(aet) is None

# markets
r = ta.norm(m, "espn")
M = ta.MARKETS
assert M["goals over 2.5"](r) == 1.0 and M["goals over 3.5"](r) == 0.0 and M["BTTS yes"](r) == 1.0
assert M["1st half draw"](r) == 1.0 and M["1st half goals over 1.5"](r) == 1.0 and M["2nd half goals over 0.5"](r) == 1.0
assert M["early goal (0-15 min)"](r) == 1.0 and M["goal 76 min on"](r) == 1.0
assert M["corners over 8.5"](r) == 1.0 and M["cards over 2.5"](r) == 0.0 and M["yellow cards over 2.5"](r) == 0.0
nocorn = ta.norm({**m, "corners": None, "cards": None, "goals": None, "ht": None}, "espn")
assert M["corners over 8.5"](nocorn) is None and M["cards over 2.5"](nocorn) is None and M["goal 76 min on"](nocorn) is None

# run(): reads each date once, one line per match id
with tempfile.TemporaryDirectory() as d:
    out = eh.run(date(2025, 3, 15), date(2025, 3, 16), Path(d), get=lambda u: {"events": [EV]})
    assert "2 dates read, 1 new matches" in out, out
    out = eh.run(date(2025, 3, 15), date(2025, 3, 16), Path(d), get=lambda u: {"events": [EV]})
    assert "0 dates read" in out, out
    assert len(eh.load(Path(d))) == 1


# Predictor: earlier games only, needs 4 games per side at the venue, shrunk to the league
def match(i, h, a, ft):
    return ta.norm({"id": str(i), "date": f"2025-0{1 + i // 28}-{1 + i % 28:02d}T15:00Z", "lid": "1", "year": 2025, "hid": h,
                    "aid": a, "home": h, "away": a, "league": "L", "ft": ft, "ht": None, "goals": None, "cards": None,
                    "corners": None}, "espn")


p = ta.Predictor(["goals over 2.5"])
ms = [match(i, "X", "Y", [3, 1]) for i in range(4)] + [match(10 + i, "Y", "X", [0, 0]) for i in range(4)]
q = match(99, "X", "Y", [0, 0])
assert p.chance("goals over 2.5", q) is None
for x in ms:
    p.see(x)
c = p.chance("goals over 2.5", q)
assert c is not None and 0.5 < c["p"] < 1.0, c     # X scores high at home; Y concedes high away; shrunk below 1

# SportyBet prices -> markets, de-vigged
pr = tas.sb_prices({"1x2": [2.0, 3.4, 4.0], "btts": [1.8, 1.95],
                    "ladder": {"SB:18|total=2.5|Over 2.5": 1.9, "SB:18|total=2.5|Under 2.5": 1.9,
                               "SB:19|total=0.5|Over 0.5": 1.25, "SB:19|total=0.5|Under 0.5": 3.6}})
assert abs(tas.fair("goals over 2.5", pr) - 0.5) < 1e-9
assert pr["home scores"] == (1.25, 3.6) and pr["BTTS yes"] == (1.8, 1.95)
assert 0.47 < tas.fair("home win", pr) < 0.49

# gap rules: chosen on the early bets, judged on the late ones
bets = [{"ko": f"2026-10-{d:02d}", "market": "goals over 2.5", "p": 0.65, "q": 0.5, "yes": 2.0, "no": 2.0, "y": 1.0}
        for d in range(1, 29)]
rules = tas.gap_rules(bets, "2026-10-15")
yes = [x for x in rules if x["side"] == "yes" and x["gap"] == 0.05][0]
assert yes["disc_n"] == 14 and yes["hold_n"] == 14 and abs(yes["hold_roi"] - 1.0) < 1e-9
assert not [x for x in rules if x["side"] == "no"]      # the trend never sits below the price here
print("trend_atlas_test OK")
