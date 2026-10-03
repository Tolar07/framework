"""
Offline test of the AI Survivor lineage (engine/survivor.py): one loss is
extinction, a win pays stake x (price-1) and breeds, slots never delete a
survivor, the starvation floor, pick selection (most likely winner first,
Under last, no started matches), idempotent selection, grading from
Flashscore-shaped events, and the stale-pick release. No network.
"""
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import survivor as sv


def pop_of(*bankrolls):
    return {"lineages": [dict(sv._lineage(bankroll=b), to_breed=True, last_result="WIN")
                         for b in bankrolls], "last_bred_date": None}


# WIN pays, LOSS kills.
p = {"lineages": [sv._lineage(bankroll=10)], "last_bred_date": None}
lid = p["lineages"][0]["lineage_id"]
rec = {"lineage_id": lid, "price": 1.5}
sv.apply_result(p, rec, "WIN")
assert p["lineages"][0]["bankroll"] == 10.5 and p["lineages"][0]["to_breed"]
sv.apply_result(p, rec, "LOSS")          # already applied -> ignored
assert p["lineages"][0]["alive"]
sv.apply_result(p, {"lineage_id": lid, "price": 1.5}, "LOSS")
assert not p["lineages"][0]["alive"] and p["lineages"][0]["bankroll"] == 9.5
print("win pays / one loss is extinction: OK")

# Breeding: 12 winners, cap 16 -> 4 richest split in two, 8 carry; capital conserved.
p = pop_of(13.81, 13.10, 13.03, 13.00, 12.84, 12.5, 12.4, 12.3, 12.2, 12.1, 12.0, 11.9)
before = sum(l["bankroll"] for l in sv.living(p))
births = sv.breed(p, "2026-09-19")
alive = sv.living(p)
assert len(alive) == 16 and births == 8, (len(alive), births)
assert abs(sum(l["bankroll"] for l in alive) - before) < 0.05
assert sv.breed(p, "2026-09-19") == 0, "no second breeding without a new win"
# Without the history a winner holding a pending pick waits (nothing orphaned).
p = pop_of(10.0)
p["lineages"][0]["holding"] = {"date": "2026-10-04"}
assert sv.breed(p, "2026-10-03") == 0 and p["lineages"][0]["to_breed"]
# With the history it splits now and its first child inherits the pending pick.
parent = p["lineages"][0]["lineage_id"]
h = [{"date": "2026-10-04", "lineage_id": parent, "generation": 0, "result": "PENDING"}]
assert sv.breed(p, "2026-10-03", h) == 2
kids = sv.living(p)
assert len(kids) == 2 and h[0]["lineage_id"] == kids[0]["lineage_id"] != parent
assert kids[0]["holding"] and not kids[1].get("holding"), "one child keeps the pick, one is free"
assert abs(sum(k["bankroll"] for k in kids) - 10.0) < 0.02
assert not any(l["to_breed"] for l in alive)
# 9 survivors over the cap: nobody is deleted.
p = pop_of(*[5.0] * 17)
sv.breed(p, "2026-10-03")
assert len(sv.living(p)) == 17
# Starvation floor.
p = {"lineages": [dict(sv._lineage(), alive=False)], "last_bred_date": None}
sv.breed(p, "2026-10-03")
assert len(sv.living(p)) == 1 and sv.living(p)[0]["bankroll"] == sv.STARVATION_FLOOR
print("breeding slots / no deletion / starvation floor: OK")


def bf(fx, key, chance, cert="HIGH", day="2026-10-03", ko="2026-10-03T15:00:00Z", price=1.4):
    h, a = fx.split(" v ")
    return NS(fixture=f"{fx} (Serie A)", probs=NS(home_team=h, away_team=a),
              on_deploy_shortlist=True, best_market_key=key, best_price=price,
              best_model_prob=chance, kickoff_date=day, kickoff_utc=ko, certainty=cert,
              tier="SAFE", booking_code="ABC", news_level=None)


board = [bf("A v B", "UNDER_3_5", 0.90), bf("C v D", "DC_1X", 0.80),
         bf("E v F", "1X2_HOME", 0.85, cert="LOW"), bf("G v H", "OVER_1_5", 0.75),
         bf("I v J", "DC_X2", 0.95, ko="2026-10-03T08:00:00Z"),          # already started
         bf("K v L", "DC_12", 0.99, day="2026-10-04")]                    # wrong day
now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
order = [b.fixture.split(" (")[0] for b in sv.candidates(board, "2026-10-03", now)]
assert order == ["C v D", "G v H", "E v F", "A v B"], order
p = pop_of(10, 20)
for l in p["lineages"]:
    l["to_breed"] = False
hist = []
new = sv.select(p, hist, board, "2026-10-03", now)
assert [r["fixture"] for r in new] == ["C v D", "G v H"]
assert new[0]["lineage_id"] == max(p["lineages"], key=lambda x: x["bankroll"])["lineage_id"]
assert sv.select(p, hist, board, "2026-10-03", now) == [], "idempotent per day"
print("selection (likeliest first, Under last, pre-match, idempotent): OK")

# Grading from Flashscore-shaped events + stale release.
ev = [{"home": "C", "away": "D", "date": "2026-10-03", "fthg": 0, "ftag": 0,
       "finished_regular": True, "finished_other": False}]
import data.flashscore_results as fr
orig = fr.find_result
fr.find_result = lambda events, h, a, d: next((e for e in events if e["home"] == h), None)
try:
    flags = sv.grade(p, hist, ev, today="2026-10-04")
    r_cd = next(r for r in hist if r["fixture"] == "C v D")
    r_gh = next(r for r in hist if r["fixture"] == "G v H")
    assert r_cd["result"] == "WIN" and r_cd["score"] == "0-0", r_cd
    assert r_gh["result"] == "PENDING"
    sv.grade(p, hist, ev, today="2026-10-09")
    assert r_gh["result"] == "NO_RESULT", "unmatched after 4 days -> stake back"
    assert all(l["alive"] for l in sv.living(p)) and len(sv.living(p)) == 2
finally:
    fr.find_result = orig
print("grading + stale release: OK")

# Persistence round-trip + report.
with tempfile.TemporaryDirectory() as d:
    sv.save(p, hist, Path(d))
    p2, h2 = sv.load(Path(d))
    assert p2 == p and h2 == hist
    text = sv.report(p2, h2, "2026-10-03")
    assert "AI SURVIVOR" in text and "lifeforce" in text, text
print("save/load + report: OK")

# The rebuilt lineage loads and reports.
pop, hist = sv.load()
assert sv.living(pop) and hist, "data/survivor state present"
print(sv.report(pop, hist, "2026-10-03").splitlines()[1])

print("\n✅ ALL SURVIVOR TESTS PASSED")
