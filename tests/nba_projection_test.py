"""
Offline test of the player-built NBA projection (engine/nba_projection.py, Architect
2026-10-28 step 2): team table (pace, ratings, shrinkage), line-up factor, back-to-backs,
both sides of every line, SportyBet's main line and the line-up-shock flag.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_projection as P
from engine import nba_value as nv


def g(gid, tip, home, away, hp, ap, poss=100.0):
    return [{"g": gid, "tip": tip, "t": home, "o": away, "h": 1, "pts": hp, "poss": poss},
            {"g": gid, "tip": tip, "t": away, "o": home, "h": 0, "pts": ap, "poss": poss}]


trows = (g("1", "2026-10-21T23:30Z", "BOS", "NYK", 120, 100) + g("2", "2026-10-23T23:30Z", "NYK", "BOS", 100, 120)
         + g("3", "2026-10-25T23:30Z", "BOS", "NYK", 120, 100, poss=110.0))
teams, lg = P.team_table(trows)
assert abs(lg["ppg"] - 110) < 1e-9 and abs(lg["pace"] - 310 / 3) < 1e-9
assert abs(lg["rtg"] - 100 * 660 / 620) < 1e-9
b = teams["BOS"]
assert b["n"] == 3 and b["ppg"] == 120 and len(b["tips"]) == 3
raw = 100 * 360 / 310
assert abs(b["ortg"] - (raw * 3 + P.K_GAMES * lg["rtg"]) / (3 + P.K_GAMES)) < 1e-9, "shrunk toward the league"
assert teams["BOS"]["ortg"] > lg["rtg"] > teams["NYK"]["ortg"] and teams["BOS"]["drtg"] < lg["rtg"]
print("team table: OK")

# line-up factor: the usual five at 48 minutes each = 1.00; the star out = lower
five = [{"name": f"P{i}", "gp": 3, "min": 48.0, "min10": 48.0, "pts": 24.0, "status": ""} for i in range(5)]
assert P.lineup_factor({"players": five}, 120.0) == 1.0
star = [{**five[0], "pts": 40.0}] + [{**p, "pts": 20.0} for p in five[1:]]
full, no_star = P.lineup_factor({"players": star}, 120.0), P.lineup_factor({"players": star[1:]}, 120.0)
assert full == 1.0 and no_star is not None and no_star < 1.0, (full, no_star)
assert P.lineup_factor({"players": star[:2]}, 120.0) is None, "under 120 known minutes says nothing"
dtd = P.lineup_factor({"players": [{**star[0], "status": "Day-To-Day"}] + star[1:]}, 120.0)
assert dtd is not None and no_star < dtd < full, "a doubtful star counts in part"
print("line-up factor: OK")

# back-to-back: previous tip within 30 hours
assert P.back_to_back(["2026-10-27T23:30Z"], "2026-10-28T23:30Z")
assert not P.back_to_back(["2026-10-26T23:30Z"], "2026-10-28T23:30Z")
assert not P.back_to_back(["2026-10-28T23:30Z"], "2026-10-28T23:30Z"), "the game itself is not rest"
print("back-to-back: OK")


def sheet(team, players=five, top3_out=(), stale=()):
    return {"team": team, "players": list(players), "top3_out": list(top3_out), "stale": list(stale)}


game = {"espn_id": "9", "tip": "2026-10-28T23:30Z", "home_sheet": sheet("BOS"), "away_sheet": sheet("NYK")}
sharp = {"total": 220.5, "spread": -6.5, "open_total": 221.0, "open_spread": -6.5}
out = P.project(game, teams, lg, sharp, {"225": 219.5, "68": 110.5})
pr = out["projection"]
assert pr["home_pts"] > pr["away_pts"] and pr["spread"] < 0 and out["lineup_shock"] is None
assert abs(pr["total"] - (pr["home_pts"] + pr["away_pts"])) < 0.11
assert abs(pr["h1_total"] - pr["total"] * nv.H1_SHARE) < 0.11 and abs(pr["q1_total"] - pr["total"] * nv.Q1_SHARE) < 0.11
pace = teams["BOS"]["pace"] * teams["NYK"]["pace"] / lg["pace"]
want = pace * teams["BOS"]["ortg"] * teams["NYK"]["drtg"] / lg["rtg"] / 100 + P.HOME_PTS
assert abs(pr["home_pts"] - want) < 0.051, (pr["home_pts"], want)
# both sides recorded, summing to 1, for SportyBet's and the sharp line
s = out["sides"]
t = s["total"]["sportybet"]["projection"]
assert t["line"] == 219.5 and abs(t["over"] + t["under"] - 1) < 1e-3
assert s["total"]["sharp"]["sharp"]["line"] == 220.5 and abs(s["total"]["sharp"]["sharp"]["over"] - 0.5) < 1e-3
assert s["h1_total"]["sharp"]["sharp"]["line"] == 110.5 and "q1_total" in s
sp = s["spread"]["sharp"]["sharp"]
assert sp["line"] == -6.5 and abs(sp["home"] - 0.5) < 1e-3 and abs(sp["home"] + sp["away"] - 1) < 1e-3
print("projection + both sides: OK")

# back-to-back costs the home side
b2b = P.project({**game, "tip": "2026-10-26T20:00Z"}, teams, lg, sharp)
assert b2b["projection"]["b2b"]["home"] and b2b["projection"]["home_pts"] < pr["home_pts"]

# stale or unknown -> no projection, reasons kept
st = P.project({**game, "home_sheet": sheet("BOS", stale=["newest box score 2026-10-20"])}, teams, lg, sharp)
assert st["projection"] is None and st["why"] == ["BOS: newest box score 2026-10-20"]
assert P.project({**game, "away_sheet": sheet("LAL")}, teams, lg, sharp)["projection"] is None
print("stale gate: OK")

# line-up shock: a top-3 scorer out and the line has not moved
shock = P.project({**game, "home_sheet": sheet("BOS", top3_out=["Star"])}, teams, lg, sharp, {"225": 221.5})
assert shock["lineup_shock"] == {"out": ["Star"], "sharp_unmoved": True, "sportybet_unmoved": True, "flag": True}
moved = {**sharp, "total": 216.5, "spread": -3.5}
shock = P.project({**game, "home_sheet": sheet("BOS", top3_out=["Star"])}, teams, lg, moved, {"225": 216.5})
assert shock["lineup_shock"]["flag"] is False, shock["lineup_shock"]
shock = P.project({**game, "home_sheet": sheet("BOS", top3_out=["Star"])}, teams, lg, moved, {"225": 221.5})
assert shock["lineup_shock"]["flag"] is True and shock["lineup_shock"]["sharp_unmoved"] is False, "SportyBet slow"
print("line-up shock: OK")

# SportyBet's main line: the half line with the most even prices, 1st quarter only for 236
ev = {"markets": [
    {"id": "225", "specifier": "total=219.5", "status": 0, "outcomes": [{"desc": "Over 219.5", "odds": "1.85"}, {"desc": "Under 219.5", "odds": "1.90"}]},
    {"id": "225", "specifier": "total=225.5", "status": 0, "outcomes": [{"desc": "Over 225.5", "odds": "2.40"}, {"desc": "Under 225.5", "odds": "1.50"}]},
    {"id": "225", "specifier": "total=220", "status": 0, "outcomes": [{"desc": "Over 220", "odds": "1.87"}, {"desc": "Under 220", "odds": "1.87"}]},
    {"id": "68", "specifier": "total=110.5", "status": 2, "outcomes": [{"desc": "Over 110.5", "odds": "1.87"}, {"desc": "Under 110.5", "odds": "1.87"}]},
    {"id": "236", "specifier": "quarternr=2|total=55.5", "status": 0, "outcomes": [{"desc": "Over 55.5", "odds": "1.87"}, {"desc": "Under 55.5", "odds": "1.87"}]},
    {"id": "236", "specifier": "quarternr=1|total=56.5", "status": 0, "outcomes": [{"desc": "Over 56.5", "odds": "1.80"}, {"desc": "Under 56.5", "odds": "1.95"}]}]}
assert P.sportybet_main(ev) == {"225": 219.5, "236": 56.5}, P.sportybet_main(ev)
print("SportyBet main line: OK")

print("nba_projection_test: ALL OK")
