"""Learning-loop watch (2026-10-28): a loop with no new tested evidence is STALLED."""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import learning_watch as lw  # noqa: E402

today = date(2026, 10, 28)
loops = [("fresh ok", "", "fresh", lambda: "2026-10-27", None, 3),
         ("fresh stale", "", "fresh", lambda: "2026-10-20", None, 3),
         ("fresh none", "", "fresh", lambda: None, None, 3),
         ("grew", "", "grew", lambda t: json.loads(t or "{}").get("n", 0), "memory/tactics_lessons.json", 5)]
old = {"memory/tactics_lessons.json": '{"n": 0}'}
real = lw._read
lw._read = lambda rel: '{"n": 0}'
rows = {r["loop"]: r for r in lw.check(today, loops=loops, git_old=lambda rel, b: old.get(rel))}
assert rows["fresh ok"]["ok"] and not rows["fresh stale"]["ok"] and not rows["fresh none"]["ok"]
assert not rows["grew"]["ok"], "test_n stuck at 0 = the stalled tactics loop"
lw._read = lambda rel: '{"n": 50}'
rows = {r["loop"]: r for r in lw.check(today, loops=loops, git_old=lambda rel, b: old.get(rel))}
assert rows["grew"]["ok"] and "0 -> 50" in rows["grew"]["note"]
rows = {r["loop"]: r for r in lw.check(today, loops=loops, git_old=lambda rel, b: '{"n": 50}')}
assert not rows["grew"]["ok"], "no growth over the allowance"
lw._read = real
assert "STALLED" in lw.render(list(rows.values()))
assert {x[0] for x in lw.LOOPS} >= {"tactics lessons", "why record", "results learning", "match study"}
print("learning watch: fresh / grew checks, stalled loops flagged: OK")

# bot-training plan loops (2026-11-01): a new loop is fresh during its grace, stalled after it
from datetime import date as _d  # noqa: E402
assert lw._or_grace(None, 2, _d(2026, 11, 2)) == lw.NEW_LOOPS_START
assert lw._or_grace(None, 2, _d(2026, 11, 10)) is None
assert lw._or_grace("2026-11-09", 2, _d(2026, 11, 10)) == "2026-11-09"
assert {"AI fact sheet", "verdict panel", "learned weights", "prompt contest", "AI weekly review"} <= {
    x[0] for x in lw.LOOPS}

# match study through an international break (2026-11-13): no new matches, but the run checked
import tempfile  # noqa: E402
_real = lw._read
lw._read = lambda rel: '{"checked": "2026-11-13"}' if rel.endswith("match_study_checked.json") else _real(rel)
assert lw.newest_study() >= "2026-11-13", "a caught-up check counts as fresh evidence"
lw._read = lambda rel: None if rel.endswith("match_study_checked.json") else _real(rel)
_real_jsonl = lw._jsonl
lw._jsonl = lambda path: []  # isolate from the live match-study log (it now holds 2026-11-13 matches)
assert lw.newest_study() != "2026-11-13"
lw._jsonl = _real_jsonl
lw._read = _real
from data import match_study as _ms  # noqa: E402
from monitor import match_study_run as _msr  # noqa: E402
_p = Path(tempfile.mkdtemp()) / "c.json"
_ms.LAST.update(leagues_ok=False, unread=0)
assert not _msr.mark_checked("2026-11-13", _p) and not _p.exists(), "a failed league page is not caught up"
_ms.LAST.update(leagues_ok=True, unread=99)
assert not _msr.mark_checked("2026-11-13", _p), "most pages unread is not caught up"
_ms.LAST.update(leagues_ok=True, unread=18)
assert _msr.mark_checked("2026-11-13", _p) and json.loads(_p.read_text())["checked"] == "2026-11-13"
print("match study caught-up marker: OK")

# collect() fills LAST (the crash of 2026-11-13 hid behind continue-on-error): stubbed FotMob, one page unread
import tempfile as _tf  # noqa: E402
_fm = _ms.league_matches
_ms.league_matches = lambda lid: [{"id": "1", "ko": "2026-11-08T16:00:00Z", "finished": True}]
import data.fotmob as _fotmob  # noqa: E402
_md = _fotmob.match_details
_fotmob.match_details = lambda i: {}
try:
    _n, _notes = _ms.collect(["Premier League"], Path(_tf.mkdtemp()), pause=0)
finally:
    _ms.league_matches, _fotmob.match_details = _fm, _md
assert _n == 0 and _ms.LAST == {"leagues_ok": True, "unread": 1}, _ms.LAST
print("match study collect() state: OK")
