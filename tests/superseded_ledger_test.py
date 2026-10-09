"""
Every code that went out stays graded (Architect 2026-10-09: "all codes that
were generated should be kept for verification"). A rewrite of a day's
ledger that drops codes (a --refreeze) archives the old ledger under
output/picks/superseded/, which grade_all reads and the scorecard does not.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import picks_ledger as pl

with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    path = pl.LEDGER_DIR / "picks_2026-10-09.json"
    old = {"date": "2026-10-09", "generated_at": "2026-10-08T20:51:54Z", "singles": [],
           "accas": [{"name": "Acca A", "code": "XBBKK0", "legs": [], "result": None}]}
    path.write_text(json.dumps(old), encoding="utf-8")
    same = dict(old, generated_at="2026-10-09T05:50:00Z")
    pl._archive_if_codes_change(path, same)
    assert not pl.SUPERSEDED_DIR.exists(), "same codes: nothing archived"
    new = dict(old, accas=[{"name": "Acca A", "code": "Q13HC7", "legs": [], "result": None}])
    pl._archive_if_codes_change(path, new)
    kept = list(pl.SUPERSEDED_DIR.glob("picks_2026-10-09_*.json"))
    assert len(kept) == 1 and "XBBKK0" in kept[0].read_text(encoding="utf-8"), kept

src = (Path(__file__).parent.parent / "engine" / "picks_ledger.py").read_text(encoding="utf-8")
assert 'SUPERSEDED_DIR.glob("picks_*.json")' in src.split("def grade_all")[1].split("\ndef ")[0], \
    "grade_all grades superseded ledgers too"
assert "_archive_if_codes_change(path, doc)" in src, "write_ledger archives before overwriting"
print("superseded_ledger_test: OK")
