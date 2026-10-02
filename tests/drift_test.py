"""
Offline test of the price-drift guard (pre-kickoff alert in news_check.py)
and the live calibration report (engine/picks_ledger.calibration). No network.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import news_check as nc
from engine import picks_ledger as pl

now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
ko = lambda m: (now + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ")
mk = {"id": 18, "spec": "total=1.5", "outcome": "Over 1.5"}
doc = {"singles": [
    {"fixture": "A v B", "pick": "Over 1.5", "price": 1.25, "kickoff_utc": ko(120),
     "sb_event_id": "e1", "sb_tid": "t", "sb_market": mk},
    {"fixture": "C v D", "pick": "Over 1.5", "price": 1.25, "kickoff_utc": ko(120),
     "sb_event_id": "e2", "sb_tid": "t", "sb_market": mk},
    {"fixture": "E v F", "pick": "Over 1.5", "price": 1.25, "kickoff_utc": ko(400),   # too early
     "sb_event_id": "e3", "sb_tid": "t", "sb_market": mk}]}
fake = {"e1": 1.33, "e2": 1.18, "e3": 1.50}
nc._current_prices = lambda due: {id(s): fake[s["sb_event_id"]] for s in due}
drifted = nc.check_drift(doc, now)
assert [s["fixture"] for s in drifted] == ["A v B"], drifted
assert doc["singles"][0]["drift_pct"] == 6.4 and doc["singles"][1]["drift_pct"] == -5.6
assert "drift_pct" not in doc["singles"][2], "outside the 1-3 h window: not checked yet"
assert nc.check_drift(doc, now) == [], "each pick checked once"
print("drift alert (5%+ out, once, 1-3 h window): OK")

singles = ([{"chance": 0.8, "result": "won"}] * 8 + [{"chance": 0.8, "result": "lost"}] * 2 +
           [{"chance": 0.6, "result": "won"}] * 3 + [{"chance": 0.6, "result": "lost"}] * 2 +
           [{"chance": 0.7, "result": "void"}])
lines = pl.calibration(singles)
assert lines and "Brier" in lines[0] and "15 picks" in lines[0], lines
assert "said 80-90% → won 80% (n=10)" in lines[1] and "said 60-70% → won 60% (n=5)" in lines[1], lines
assert pl.calibration(singles[:3]) == [], "too few picks -> no report"
print("calibration report: OK")

print("\n✅ ALL DRIFT/CALIBRATION TESTS PASSED")
