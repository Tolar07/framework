"""
Offline test of the NBA projection gate (engine/nba_gate.py, Architect OK 2026-10-28) and
the season refit in pricing (engine/nba_value.use_season_refit): the gate opens only on
150+ games beating the sharp line on both Brier and log loss with positive CLV; open, it
drops only picks the projection prices on the other side; closed, it drops nothing.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_gate as G
from engine import nba_value as nv


def rec(total_actual, proj_over, sharp_over=0.5):
    return {"result": {"hs": total_actual // 2, "as": total_actual - total_actual // 2, "h1": 0, "q1": 0},
            "sides": {"total": {"sharp": {"projection": {"line": 220.5, "over": proj_over},
                                          "sharp": {"line": 220.5, "over": sharp_over}}}}}


good = [rec(230, 0.7) for _ in range(100)] + [rec(210, 0.3) for _ in range(60)]     # projection right
st = G.status(good, {"mean_pts": 0.8})
assert st["open"] and st["games"] == 160 and st["lines"]["n"] == 160, st["why"]
assert st["lines"]["projection"]["brier"] < st["lines"]["sharp"]["brier"]
assert not G.status(good[:149], {"mean_pts": 0.8})["open"], "under 150 games stays closed"
assert not G.status(good, {"mean_pts": -0.1})["open"], "no positive CLV stays closed"
bad = [rec(230, 0.3) for _ in range(160)]
assert "does not beat the sharp line" in G.status(bad, {"mean_pts": 0.8})["why"][0]
print("gate status: OK")

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "gate.json"
    assert G.is_open(p) is False, "no file = closed"
    G.save(st, p)
    assert G.is_open(p) is True
    G.save(G.status(bad, {"mean_pts": 0.8}), p)
    assert G.is_open(p) is False, "closes again by itself"
print("gate file: OK")

picks = [{"espn_id": "1", "market_id": "68", "specifier": "total=112.5", "outcome": "Under 112.5"},
         {"espn_id": "1", "market_id": "225", "specifier": "total=225.5", "outcome": "Over 225.5"},
         {"espn_id": "2", "market_id": "219", "specifier": "", "outcome": "Home"},
         {"espn_id": "3", "market_id": "68", "specifier": "total=110.5", "outcome": "Over 110.5"}]
projs = [{"espn_id": "1", "projection": {"total": 232.0, "spread": -4.0}},     # high-scoring: Overs
         {"espn_id": "2", "projection": {"total": 220.0, "spread": -2.0}},
         {"espn_id": "3", "projection": None}]
kept, dropped = G.apply(picks, projs, False)
assert len(kept) == 4 and not dropped, "closed gate drops nothing"
assert kept[0]["projection_chance"] < 0.5 < kept[1]["projection_chance"] and kept[2]["projection_chance"] is None
kept, dropped = G.apply(picks, projs, True)
assert [p["outcome"] for p in dropped] == ["Under 112.5"] and dropped[0]["dropped_by"] == "projection gate"
assert [p["outcome"] for p in kept] == ["Over 225.5", "Home", "Over 110.5"], "unpriceable picks kept"
print("gate on picks: OK")

# season refit: only ADOPTED families change pricing
fixed = (nv.TOTAL_SD, nv.MARGIN_SD, nv.H1_SHARE, nv.H1_SD, nv.Q1_SHARE, nv.Q1_SD)
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "live.json"
    assert nv.use_season_refit(p) == [], "no file: fixed numbers"
    p.write_text(json.dumps({"h1": {"share": 0.496, "sd": 11.0, "adopted": "2026-11-02T03:31:00Z"},
                             "q1": {"share": 0.25, "sd": 7.0}}))
    notes = nv.use_season_refit(p)
    assert len(notes) == 1 and (nv.H1_SHARE, nv.H1_SD) == (0.496, 11.0)
    assert (fixed[4], fixed[5], fixed[0]) == (nv.Q1_SHARE, nv.Q1_SD, nv.TOTAL_SD), "not adopted: unchanged"
nv.TOTAL_SD, nv.MARGIN_SD, nv.H1_SHARE, nv.H1_SD, nv.Q1_SHARE, nv.Q1_SD = fixed
print("season refit in pricing: OK")

print("nba_gate_test: ALL OK")
