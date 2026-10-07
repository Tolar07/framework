"""
Offline test of the universe (engine/universe.py, backtest/universe_study.py):
prices read from SportyBet events, first/last look kept, strict result
matching, grading / waiting / giving up, settlement of every kept market
(90 minutes only in football; pushes skipped in basketball), and the study.
"""
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backtest"))

import pipeline.odds_sportybet as osb
from engine import universe as uv

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
KO = int(datetime(2026, 10, 7, 18, 0, tzinfo=UTC).timestamp() * 1000)


def mk(mid, outs, spec=None):
    return {"id": mid, "specifier": spec, "outcomes": [{"desc": d, "odds": str(p)} for d, p in outs]}


fb_event = {"eventId": "sr:match:1", "estimateStartTime": KO, "homeTeamName": "Galatasaray Istanbul",
            "awayTeamName": "Kasimpasa Istanbul", "sport": {"category": {"name": "Turkiye"}},
            "markets": [mk("1", [("Home", 1.30), ("Draw", 5.5), ("Away", 9.0)]),
                        mk("18", [("Over 2.5", 1.6), ("Under 2.5", 2.3)], "total=2.5"),
                        mk("18", [("Over 4", 3.0), ("Under 4", 1.4)], "total=4"),
                        mk("29", [("Yes", 1.9), ("No", 1.85)]),
                        mk("10", [("Home or Draw", 1.05), ("Home or Away", 1.15), ("Draw or Away", 3.3)])]}
p = uv.prices("football", fb_event)
assert p == {"1x2": [1.3, 5.5, 9.0], "ou2.5": [1.6, 2.3], "btts": [1.9, 1.85], "dc": [1.05, 1.15, 3.3]}, p

bb_event = {"eventId": "sr:match:2", "estimateStartTime": KO, "homeTeamName": "Paris Basketball",
            "awayTeamName": "ASVEL", "sport": {"category": {"name": "International"}},
            "markets": [mk("219", [("Home", 1.5), ("Away", 2.6)]),
                        mk("225", [("Over 170.5", 1.5), ("Under 170.5", 2.5)], "total=170.5"),
                        mk("225", [("Over 173.5", 1.92), ("Under 173.5", 1.90)], "total=173.5"),
                        mk("223", [("Home (-5.5)", 1.95), ("Away (+5.5)", 1.88)], "hcp=-5.5"),
                        mk("223", [("Home (-9.5)", 2.6), ("Away (+9.5)", 1.45)], "hcp=-9.5")]}
assert uv.prices("basketball", bb_event) == {"win": [1.5, 2.6], "total": [173.5, 1.92, 1.9],
                                             "hcp": [-5.5, 1.95, 1.88]}, "main line = closest to even"
shut = {**fb_event, "markets": [{**m, "status": 2} if m["id"] == "29" else m for m in fb_event["markets"]]}
assert "btts" not in uv.prices("football", shut), "a closed market is not a real price"
assert [m["id"] for m in osb.parse_markets(shut)] == ["1", "18", "18", "10"], "football reads open markets only"
print("prices from SportyBet events (main basketball line = closest to even; closed lines dropped): OK")

tour = {"name": "Super Lig", "id": "sr:tournament:52"}
pending = {}
r1 = uv.event_row("football", fb_event, tour, {"sr:tournament:52"}, T0)
assert r1["covered"] and r1["ko"] == "2026-10-07T18:00Z" and r1["country"] == "Turkiye"
assert uv.update(pending, [r1]) == 1
later = {**fb_event, "markets": [mk("1", [("Home", 1.25), ("Draw", 6.0), ("Away", 10.0)])]}
r2 = uv.event_row("football", later, tour, set(), T0.replace(hour=15))
assert uv.update(pending, [r2]) == 0
g = pending["sr:match:1"]
assert g["first"]["p"]["1x2"] == [1.3, 5.5, 9.0] and g["last"]["p"]["1x2"] == [1.25, 6.0, 10.0] and g["looks"] == 2
print("first look kept, last look replaced: OK")

fs = [{"league": "TURKEY: Super Lig", "home": "Galatasaray", "away": "Kasimpasa", "fthg": 3, "ftag": 1,
       "fh_home": 1, "fh_away": 0, "finished_regular": True, "finished_other": False,
       "kickoff_utc": "2026-10-07T18:00:00Z"},
      {"league": "X", "home": "Galatasaray U19", "away": "Kasimpasa U19", "fthg": 0, "ftag": 0,
       "finished_regular": True, "finished_other": False, "kickoff_utc": "2026-10-07T10:00:00Z"}]
idx = {"football": uv.ResultIndex(fs), "basketball": uv.ResultIndex([])}
assert uv.grade(pending, idx, T0.replace(hour=19)) == ([], 0) and pending, "too soon after kick-off: waits"
done, gave_up = uv.grade(pending, idx, T0.replace(hour=22))
assert gave_up == 0 and len(done) == 1 and not pending
assert done[0]["result"] == {"h": 3, "a": 1, "ht": [1, 0], "after_90": False}
lost = {"sr:match:9": {**r1, "id": "sr:match:9", "home": "Nobody FC", "away": "Nowhere"}}
assert uv.grade(lost, idx, T0.replace(day=16))[1] == 1 and not lost, "no result after 7 days: given up"
print("strict result match, waits 3 h, gives up after 7 days: OK")

o = {k: (w, x) for k, w, x, _m in uv.outcomes("football", g["last"]["p"], done[0]["result"])}
assert o["1x2:home"] == (1, 1.25) and o["1x2:draw"][0] == 0
o = {k: w for k, w, _x, _m in uv.outcomes("football", p, {"h": 1, "a": 1, "after_90": False})}
assert o == {"1x2:home": 0, "1x2:draw": 1, "1x2:away": 0, "o/u2.5:over": 0, "o/u2.5:under": 1,
             "btts:yes": 1, "btts:no": 0, "dc:1x": 1, "dc:12": 0, "dc:x2": 1}, o
assert uv.outcomes("football", p, {"h": 2, "a": 1, "after_90": True}) == [], "never a 90' score from ET"
b = uv.prices("basketball", bb_event)
o = {k: w for k, w, _x, _m in uv.outcomes("basketball", b, {"h": 90, "a": 83})}
assert o == {"win:home": 1, "win:away": 0, "total:over": 0, "total:under": 1, "hcp:home": 1, "hcp:away": 0}, o
assert [k for k, *_ in uv.outcomes("basketball", {"total": [170.0, 1.9, 1.9]}, {"h": 85, "a": 85})] == []
print("settlement of every kept market: OK")

d = Path(tempfile.mkdtemp())
uv.save_pending({"x": r1}, d / "p.json.gz")
assert uv.load_pending(d / "p.json.gz") == {"x": r1}
rows = []
for i in range(40):                                 # 40 home wins at 1.30: +30% return
    rows.append({**done[0], "id": f"g{i}", "result": {"h": 2, "a": 0, "ht": [1, 0], "after_90": False}})
assert uv.archive(rows, d) == 40 and len(uv.load_graded(d)) == 40
import universe_study as us  # noqa: E402

uv.GRADED_DIR, us.OUT = d, d / "UNIVERSE_STUDY.md"
_orig = uv.load_graded
us.uv.load_graded = lambda folder=d: _orig(d)
us.main()
txt = us.OUT.read_text(encoding="utf-8")
assert "40 games graded" in txt and "| 1x2:home | 40 | 100.0%" in txt and "+30.0%" in txt
assert "Turkiye · Super Lig — 1x2:home" in txt, "a 40-game standout competition is listed"
print("study written (sides, bands, standout competitions): OK")

print("ALL UNIVERSE TESTS PASSED")
