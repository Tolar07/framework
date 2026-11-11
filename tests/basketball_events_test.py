"""engine/basketball_events.py, monitor/basketball_events_run.py, backtest/basketball_events_study.py (framework #558).
Offline, no network."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest import basketball_events_study as study  # noqa: E402
from data import nba_source as ns  # noqa: E402
from engine import basketball_events as be  # noqa: E402
from monitor import basketball_events_run as run  # noqa: E402


def row(g, d, p, t="AAA", m=30, pts=15, reb=5, ast=4, tpm=2):
    return {"g": g, "d": d, "t": t, "p": p, "n": f"P{p}", "s": 1, "m": m, "pts": pts, "reb": reb, "ast": ast, "tpm": tpm}


from datetime import date, timedelta  # noqa: E402

DAYS = [(date(2026, 10, 1) + timedelta(days=i)).isoformat() for i in range(45)]
rows = [row(f"g{d}", d, str(k), m=30 - k, pts=20 - 2 * k) for d in DAYS for k in range(8)]

# 1. box score -> rows: DNP skipped, "7-12" threes read as 7 made
blob = {"boxscore": {"players": [{"team": {"abbreviation": "AAA"}, "statistics": [{
    "keys": ["minutes", "points", "rebounds", "assists", "threePointFieldGoalsMade-threePointFieldGoalsAttempted"],
    "athletes": [{"athlete": {"id": "1", "displayName": "A"}, "starter": True, "stats": ["31", "38", "5", "3", "7-12"]},
                 {"athlete": {"id": "2", "displayName": "B"}, "didNotPlay": True, "stats": []}]}]}]}}
rr = be.stat_rows(ns.Game("g", "2026-10-20", 0, 2, "AAA", "BBB", None, None, True), blob)
assert len(rr) == 1 and rr[0]["tpm"] == 7 and rr[0]["pts"] == 38 and rr[0]["m"] == 31
print("box score rows: OK")

# 2. too few games reads PENDING (HR35), enough games gives numbers
hist = be.by_player(rows)
lg = be.league_rates(rows)
assert be.expected(hist["0"][:3], lg) is None
e = be.expected(hist["0"], lg)
assert e and 29 < e["min"] < 31 and 18 < e["pts"] < 22
assert be.expected(hist["0"], lg, 0.5)["min"] == e["min"] / 2          # Questionable: half the minutes
print("pending / expected: OK")

# 3. the players' points add up to the team's projected points (agrees with engine/nba_projection.py)
pl = [{"pts": 20.0}, {"pts": 15.0}, {"pts": 10.0}]
f = be.scale_points(pl, 55.0)
assert abs(sum(p["pts"] for p in pl) - 55.0) < 1e-9 and f > 1
assert be.scale_points([{"pts": 5.0}], None) is None                    # no team number: left alone, flagged
pl2 = [{"pts": 1.0}]
assert be.scale_points(pl2, 500.0) == be.SCALE_CLIP[1]                  # never scaled wildly
print("player points sum to team: OK")

# 4. over / under: both sides add to 1, no whole lines, mean at the line is about even, spread widens the tails
ou = be.over_under(20.0, 19.5, 3.0)
assert abs(ou["over"] + ou["under"] - 1) < 1e-3 and 0.4 < ou["over"] < 0.6
assert be.over_under(20.0, 20.0, 3.0) is None
assert be.over_under(5.0, 9.5, 1.0)["over"] < be.over_under(5.0, 9.5, 3.0)["over"]   # wider = fatter upper tail
assert abs(sum(math.exp(-4) * 4 ** k / math.factorial(k) for k in range(0, 5)) - be._nb_cdf(4, 4.0, 1.0)) < 1e-9
print("over/under chances: OK")

# 5. SportyBet lines parsed ('Last, First' names, whole lines skipped)
mk = [{"id": "921", "name": "Grant, Jerami total points (incl. overtime)", "spec": "total=10.5|player=x", "open": True,
       "outcomes": [["Over 10.5", 1.87], ["Under 10.5", 1.83]]},
      {"id": "923", "name": "Grant, Jerami total rebounds (incl. overtime)", "spec": "total=4", "open": True,
       "outcomes": [["Over 4", 1.9], ["Under 4", 1.8]]}]
pls = be.player_lines(mk)
assert pls["jerami grant"]["pts"]["line"] == 10.5 and "reb" not in pls["jerami grant"]
print("SportyBet lines: OK")

# 6. study: walk-forward is purged (no game uses its own night or the night before), nothing published on thin data
sc = study.walk(rows)
assert sc and all(x["d"] >= DAYS[21] for x in sc)
res = study.study(rows)
assert all(not v["publish"] for v in res["stats"].values())             # n < MIN_N
assert "BASKET_PUBLISH = []" in study.render(res, date(2026, 11, 11))
print("study walk-forward + no publish on thin data: OK")

# 7. runner reads the study's numbers
assert run.study_numbers()[1]["pts"] > 1
print("OK")
