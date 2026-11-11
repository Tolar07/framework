"""engine/event_model.py (framework #555): football match events, record-only. Offline, no network."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import event_model as em  # noqa: E402


def match(day, lg, h, a, yellow, fouls=(11, 11), corners=(5, 4), shots=(13, 10), sot=(5, 3), red=(0, 0), xg=(1.5, 1.0)):
    return {"date": day, "league": lg, "home": h, "away": a,
            "stats": {"yellow": list(yellow), "fouls": list(fouls), "corners": list(corners), "shots": list(shots),
                      "sot": list(sot), "red": list(red), "xg": list(xg)}}


rows = []
for i in range(20):
    d = f"2026-10-{i + 1:02d}"
    rows.append(match(d, "L", "Rough FC", "Calm Town", (4, 1), fouls=(16, 9)))
    rows.append(match(d, "L", "Calm Town", "Middle United", (1, 2), fouls=(9, 11)))
    rows.append(match(d, "L", "Middle United", "Rough FC", (2, 4), fouls=(11, 15)))

# 1. distributions are proper
p = [em.nb_pmf(k, 4.2, 6.0) for k in range(60)]
assert abs(sum(p) - 1) < 1e-6
assert abs(sum(k * x for k, x in enumerate(p)) - 4.2) < 1e-3
assert abs(em.over(3.5, 4.2, math.inf) - (1 - sum(em.nb_pmf(k, 4.2, math.inf) for k in range(4)))) < 1e-9
print("negative binomial and over-line chances: OK")

# 2. a card-happy side gets more cards than a calm one, and the total sits near what they actually do
m = em.EventModel.fit(rows)
rough = m.predict("L", "Rough FC", "Calm Town")["events"]["yellow"]
calm = m.predict("L", "Calm Town", "Rough FC")["events"]["yellow"]
assert rough["home"] > calm["home"] and rough["total"] > 3.5, (rough, calm)
assert 0 < rough["over"]["4.5"] < 1 and rough["over"]["2.5"] > rough["over"]["4.5"]
print("team rates move the counts the right way: OK")

# 3. walk-forward: fit(before=day) never sees that day
m2 = em.EventModel.fit(rows, before="2026-10-05")
assert all(n[2] <= 8 for t in m2.teams.values() for n in t.values())   # 4 days, 2 games a day each
print("fit(before=...) uses earlier days only: OK")

# 4. agrees with the goals model: shots on target follow the board's expected goals
lo = m.predict("L", "Middle United", "Calm Town", xg=(0.6, 0.6))["events"]["sot"]
hi = m.predict("L", "Middle United", "Calm Town", xg=(2.6, 2.4))["events"]["sot"]
assert hi["total"] > lo["total"] and hi["anchored_to_xg"]
L = m.league("L")
for e, x in ((lo, 1.2), (hi, 5.0)):
    goals_per_sot = x / e["total"]
    assert 0.12 < goals_per_sot < 0.6, goals_per_sot      # leagues show roughly 0.2-0.45 goals per shot on target
print("shots on target agree with the model's expected goals: OK")

# 5. board names pair with the stats' names only when certain
m.names["L"] += ["Dundee", "Dundee United"]
assert m.resolve("L", "Rough") == "Rough FC"
assert m.resolve("L", "Dundee Utd") is None          # never "Dundee": "Dundee United" half-matches too
assert m.resolve("L", "Nobody") is None
unknown = m.predict("L", "Nobody", "Calm Town")["events"]["yellow"]
assert unknown["matches_behind"][0] == 0
print("name pairing strict, unknown team falls back to the league: OK")

# 6. red card chance is a probability
r = m.predict("L", "Rough FC", "Calm Town")["events"]["red"]
assert 0 <= r["chance_any"] < 1
print("red card chance: OK")

# 7. expected goals from the board's score table
assert em.xg_from_grid([[0.5, 0.0], [0.5, 0.0]]) == (0.5, 0.0)
assert em.xg_from_grid(None) is None
print("xG from the score table: OK")

# 8. record-only: the module places nothing and touches no stake
src = (Path(__file__).parent.parent / "engine" / "event_model.py").read_text(encoding="utf-8")
src += (Path(__file__).parent.parent / "monitor" / "events_run.py").read_text(encoding="utf-8")
for word in ("stake", "place_bet", "booking", "send_message", "telegram"):
    assert word not in src.lower().replace("stakes nothing", "").replace("no pick, stake", ""), word
print("ALL EVENT MODEL TESTS PASSED")
