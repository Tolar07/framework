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

# Combined codes (Architect 2026-10-09): one slip for every acca / alt / value
_rd = (Path(__file__).parent.parent / "run_daily.py").read_text(encoding="utf-8")
assert '"accas_mega"' in _rd and '"alts_mega"' in _rd and '"value_mega"' in _rd, "combined codes booked"
_pb = (Path(__file__).parent.parent / "output" / "produce_bet.py").read_text(encoding="utf-8")
assert "ACCAS MEGA:" in _pb and "ALT MEGA:" in _pb and "VALUE MEGA:" in _pb, "combined codes in ALL CODES"
with tempfile.TemporaryDirectory() as tmp:
    pl.LEDGER_DIR, pl.SUPERSEDED_DIR = Path(tmp), Path(tmp) / "superseded"
    doc = {"date": "2026-10-01", "singles": [],
           "accas": [{"name": "Acca A", "legs": [], "result": "won"},
                     {"name": "Acca B", "legs": [], "result": "lost"}],
           "combined": [{"name": "ACCAS MEGA", "of": "accas", "code": "X", "result": None}]}
    (pl.LEDGER_DIR / "picks_2026-10-01.json").write_text(json.dumps(doc), encoding="utf-8")
    pl.grade_all([], today="2026-10-05")
    out = json.loads((pl.LEDGER_DIR / "picks_2026-10-01.json").read_text(encoding="utf-8"))
    assert out["combined"][0]["result"] == "lost", out["combined"]
print("combined codes: OK")
