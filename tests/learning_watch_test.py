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

# international break (2026-11-13): no new match, but a clean FotMob sweep today = quiet source, not a stall
_real_jsonl, _real_read = lw._jsonl, lw._read
lw._jsonl = lambda p: [{"ko": "2026-11-09T15:00"}]
lw._read = lambda rel: '{"date": "2026-11-13"}' if rel.endswith("last_sweep.json") else None
assert lw.newest_study() == "2026-11-13"
lw._read = lambda rel: None
assert lw.newest_study() == "2026-11-09", "no sweep file: the newest match decides"
lw._jsonl, lw._read = _real_jsonl, _real_read
print("learning watch: clean sweep during a break counts as evidence: OK")
