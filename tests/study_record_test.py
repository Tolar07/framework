"""
Offline test of engine/study_record.py (how the study boards' stated chances
held up — a warning, never a filter) and the live tracker's fixture matching.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "monitor")]

import live_tracker as lt  # noqa: E402

from engine import study_record as sr  # noqa: E402

tmp = Path(tempfile.mkdtemp())
day = tmp / "2026-10-13"
day.mkdir()
legs = [("A v B", 0.80, "lost"), ("C v D", 0.79, "lost"), ("E v F", 0.81, "won"), ("G v H", 0.70, "won"),
        ("I v J", 0.78, "void")]
(day / "engine_board.json").write_text(json.dumps({"legs": [{"match": m, "pick": {"win": w, "fam": "x"}}
                                                            for m, w, _r in legs]}))
(day / "grades.json").write_text(json.dumps({"study": {"legs": [{"match": m, "result": r} for m, _w, r in legs]}}))
rows = sr.picks(tmp)
assert len(rows) == 4, "voids are not a record either way"
w = sr.warning(0.80, rows)
assert w.startswith("⚠") and "landed 1/3" in w, w
assert sr.warning(0.55, rows) == "", "no record in a band: no warning, never a guess"
assert "4 graded study picks" in sr.summary(rows)[0]
print("study record: OK")

calls = [{"home": "Man City", "away": "PSG", "call": "board: x"}]
m = {"home": "Manchester City", "away": "Paris Saint-Germain", "league": "Champions League"}
real = lt.fm.matches_on
lt.fm.matches_on = lambda d: [m, {**m, "home": "Manchester City U19", "away": "Paris Saint-Germain U19",
                                   "league": "UEFA Youth League"}]
try:
    got = lt.tracked("2026-10-14", calls)
finally:
    lt.fm.matches_on = real
assert [g["home"] for g in got] == ["Manchester City"] and got[0]["calls"] == ["board: x"], got
print("live tracker matching: OK")
print("ALL STUDY RECORD TESTS PASSED")
