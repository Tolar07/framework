"""
Offline test of the NBA paper board (order 41): fair chances from the sharp
line, value picks only above the fair price, stale-line guard, settlement
incl. overtime, and team matching.
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import nba_value as nv
import run_nba

sharp = NS(ml_home=1.5405, ml_away=2.54, spread=-5.5, total=213.5)

# winner: the margin-free moneyline
p = nv.fair_chance("219", "", "Home", sharp)
assert abs(p - nv.devig(1.5405, 2.54)) < 1e-9 and abs(p + nv.fair_chance("219", "", "Away", sharp) - 1) < 1e-9
# handicap: home -5.5 when the sharp line is -5.5 is a coin flip; +11.5 for the away side is ~77%
assert abs(nv.fair_chance("223", "hcp=-5.5", "Home (-5.5)", sharp) - 0.5) < 1e-6
pa = nv.fair_chance("223", "hcp=-11.5", "Away (+11.5)", NS(ml_home=1.87, ml_away=1.95, spread=-1.5, total=220))
assert 0.75 < pa < 0.78, pa
assert nv.fair_chance("223", "hcp=-5", "Home (-5)", sharp) is None, "a whole-number line can push: skipped"
# totals: over the sharp line is a coin flip; 12.5 below it is ~75%
assert abs(nv.fair_chance("225", "total=213.5", "Over 213.5", sharp) - 0.5) < 1e-6
assert 0.74 < nv.fair_chance("225", "total=201", "Over 201", sharp) < 0.77
print("fair chances from the sharp line: OK")

ev = {"markets": [
    {"id": "219", "outcomes": [{"id": "4", "desc": "Home", "odds": "1.55"}, {"id": "5", "desc": "Away", "odds": "2.45"}]},
    {"id": "223", "specifier": "hcp=-11.5", "outcomes": [{"id": "1714", "desc": "Home (-11.5)", "odds": "2.85"},
                                                         {"id": "1715", "desc": "Away (+11.5)", "odds": "1.39"}]},
    {"id": "225", "specifier": "total=180.5", "outcomes": [{"id": "12", "desc": "Over 180.5", "odds": "1.40"},
                                                          {"id": "13", "desc": "Under 180.5", "odds": "2.9"}]}]}
sh = NS(ml_home=1.87, ml_away=1.95, spread=-1.5, total=220)
picks, suspect = nv.candidates(ev, sh)
assert [r["outcome"] for r in picks] == ["Away (+11.5)"], picks          # +6.7%
assert [r["outcome"] for r in suspect] == ["Over 180.5"], "a 40-point gap is a stale line, never a pick"
assert all(r["price"] >= 1.2 and r["chance"] >= 0.5 for r in picks)
print("value only above the fair price; stale gaps left out: OK")

assert nv.settle({"market_id": "219", "outcome": "Away", "specifier": ""}, 110, 112) == "won"
assert nv.settle({"market_id": "223", "outcome": "Away (+11.5)", "specifier": "hcp=-11.5"}, 120, 110) == "won"
assert nv.settle({"market_id": "223", "outcome": "Home (-11.5)", "specifier": "hcp=-11.5"}, 120, 110) == "lost"
assert nv.settle({"market_id": "225", "outcome": "Under 220.5", "specifier": "total=220.5"}, 110, 111) == "lost"
print("settlement (incl. OT): OK")

assert run_nba.nickname("LA Clippers") == run_nba.nickname("Los Angeles Clippers") == "clippers"
assert run_nba.nickname("Portland Trail Blazers") == "blazers"
assert nv.display({"market_id": "223", "outcome": "Away (+11.5)"}, "OKC", "New Orleans Pelicans") \
    == "New Orleans Pelicans (+11.5) handicap"
txt = run_nba.render([], "2026-10-21", "OLPXDV-20261020-2047-abcdef", 0, None, [])
assert "PAPER BOARD" in txt and "Run ID: OLPXDV-20261020-2047-abcdef" in txt
print("matching + board text: OK")

# 1st half / 1st quarter totals (the Architect's low-Over / high-Under method)
sh2 = NS(ml_home=1.9, ml_away=1.9, spread=-1.5, total=230.0)
assert abs(nv.fair_chance("68", "total=115.5", "Over 115.5", sh2) - 0.5) < 0.01          # 0.502 x 230 = 115.5
assert 0.84 < nv.fair_chance("68", "total=103.5", "Over 103.5", sh2) < 0.86              # 12 below
assert 0.81 < nv.fair_chance("236", "total=50.5|quarternr=1", "Over 50.5", sh2) < 0.85  # 7.7 below 58.2
assert nv.fair_chance("236", "total=50.5|quarternr=2", "Over 50.5", sh2) is None, "1st quarter only"
assert nv.settle({"market_id": "236", "outcome": "Over 50.5", "specifier": "total=50.5|quarternr=1"},
                 110, 100, [30, 25, 30, 25], [24, 25, 25, 26]) == "won"                 # Q1 = 54
assert nv.settle({"market_id": "68", "outcome": "Under 104.5", "specifier": "total=104.5"},
                 110, 100, [30, 25, 30, 25], [24, 25, 25, 26]) == "won"                 # H1 = 104 (OT never counts)
assert nv.settle({"market_id": "68", "outcome": "Over 100.5", "specifier": "total=100.5"}, 1, 0, None, None) is None
assert nv.display({"market_id": "236", "outcome": "Over 50.5"}, "A", "B") == "1st quarter Over 50.5 points"
print("1st half / 1st quarter totals: OK")

print("\n✅ ALL NBA TESTS PASSED")
