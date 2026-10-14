"""
clv/clv_sync.py: the closing prices the pre-kickoff loop captures on the picks
ledger reach the CLV log the Phase 3 gate reads. Offline, on a scratch log.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from clv import clv_sync as cs  # noqa: E402
from clv.clv_logger import CLVLog  # noqa: E402

tmp = Path(tempfile.mkdtemp())
log = CLVLog(path=tmp / "clv_log.json")
a = log.log_entry(league="L", fixture="A v B", market="SB:10||Home or Away",
                  model_prob=0.8, entry_odds=1.30, match_date="2026-10-13")
b = log.log_entry(league="L", fixture="C v D", market="SB:18|total=2.5|Over 2.5",
                  model_prob=0.6, entry_odds=1.60, match_date="2026-10-13")
c = log.log_entry(league="L", fixture="E v F", market="SB:1||Home",
                  model_prob=0.7, entry_odds=1.50, match_date="2026-10-13")
log.log_close(c.leg_id, closing_odds=1.44)          # already closed: must not change
before = c.clv_pct

ledger = tmp / "picks"
ledger.mkdir()
(ledger / "picks_2026-10-13.json").write_text(json.dumps({
    "singles": [
        {"fixture": "A v B (L)", "market": "SB:10||Home or Away", "kickoff_utc": "2026-10-13T19:00Z",
         "price": 1.30, "closing_price": 1.25, "clv": 4.0},
        {"fixture": "E v F", "market": "SB:1||Home", "kickoff_utc": "2026-10-13T19:00Z",
         "price": 1.50, "closing_price": 1.11},            # already closed in the log
        {"fixture": "G v H", "market": "SB:1||Home", "kickoff_utc": "2026-10-13T19:00Z",
         "price": 1.50, "closing_price": 1.40},            # no leg in the log
        {"fixture": "X v Y", "market": "SB:1||Home", "kickoff_utc": "2026-10-13T19:00Z", "price": 1.5},
    ],
    "study": [{"fixture": "C v D", "market": "SB:18|total=2.5|Over 2.5",
               "kickoff_utc": "2026-10-13T19:00Z", "price": 1.60, "closing_price": 1.70}],
    "alts": [],
}))

rows = cs.ledger_closes(ledger)
assert len(rows) == 4, f"every pick with a captured closing price, deduped: {rows}"
assert not any(r["fixture"] == "X v Y" for r in rows), "no closing price: not synced, never invented"

rep = cs.sync(log=log, ledger_dir=ledger, dry_run=True)
assert (rep["filled"], rep["already_closed"], rep["unmatched_ledger_rows"]) == (2, 1, 1), rep
assert log.legs[0].closing_odds is None, "a dry run writes nothing"

rep = cs.sync(log=log, ledger_dir=ledger, dry_run=False)
assert (rep["filled"], rep["already_closed"], rep["unmatched_ledger_rows"]) == (2, 1, 1), rep
by = {x.leg_id: x for x in CLVLog(path=tmp / "clv_log.json").legs}
assert by[a.leg_id].closing_odds == 1.25 and by[a.leg_id].closing_capture_path == "CL-PREKICKOFF"
assert abs(by[a.leg_id].clv_pct - 4.0) < 0.01, "CLV computed by the logger's own formula, from entry 1.30"
assert by[b.leg_id].closing_odds == 1.70 and by[b.leg_id].clv_pct < 0, "study legs sync too; a drift against us is negative"
assert by[c.leg_id].closing_odds == 1.44 and by[c.leg_id].clv_pct == before, "a leg already closed is untouched"
print("clv_sync: OK")
print("ALL CLV SYNC TESTS PASSED")
