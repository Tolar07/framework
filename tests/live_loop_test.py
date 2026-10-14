"""
LIVE LOOP TEST — the matchday tracker as an Actions job (monitor/live_loop.py).

What it pins down, all offline:
  * round_once is SHARED with the session script, so both see the same events:
    a goal, a red card, half time and full time each produce exactly one line,
    a quiet poll produces none, and the snapshot is written either way;
  * a match that has not kicked off is never polled, and counts as still to
    come — the loop must not declare the day over before it starts;
  * the full-time summary names every tracked match and reads PENDING for one
    whose score never arrived (HR35), never a guess;
  * the loop hands off before GitHub's 6-hour job limit;
  * the Telegram route is the Architect's chat only (order 33) — the workflow
    must not carry the subscriber secret.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import live_loop as ll  # noqa: E402
from monitor import live_tracker as lt  # noqa: E402

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'  OK  ' if ok else ' FAIL '} {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


def match(mid: str, ko: str) -> dict:
    return {"id": mid, "home": "Norwich", "away": "Southampton", "kickoff_utc": ko,
            "calls": ["board: Southampton (+1.5) Asian handicap @1.22"]}


def snapshot(score: str, live: str, finished: bool, reds=(0, 0)) -> dict:
    return {"at": "18:55", "score": score, "live": live, "finished": finished,
            "reds": list(reds), "stats": {"xg": [0.4, 1.1], "sot": [1, 3]}}


# --------------------------------------------------------------------------
# round_once: the event detector both paths share
started_ko = (datetime.now(UTC) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%MZ")
future_ko = (datetime.now(UTC) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%MZ")

_saved_snap, _saved_sb = lt.snap, lt.sportybet_live
try:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        lt.sportybet_live = lambda live, m: None          # no live prices in a test
        state = {"s": snapshot("0-0", "25'", False)}
        lt.snap = lambda mid: state["s"]

        seen: dict = {}
        m = [match("1", started_ko)]

        # First poll of a match already under way: recorded, but not announced —
        # "0-0 after 25 minutes" is not news.
        lines, still = lt.round_once(m, seen, out, live=[])
        check("round_once: the first poll records without announcing", lines == [] and still == 1,
              f"{lines}")
        check("round_once: the snapshot is written", (out / "1.jsonl").exists())

        # A goal is one line.
        state["s"] = snapshot("0-1", "31'", False)
        lines, still = lt.round_once(m, seen, out, live=[])
        check("round_once: a goal is announced once", len(lines) == 1 and "0-1" in lines[0],
              f"{lines}")
        check("round_once: the call is carried in the line", "Asian handicap" in lines[0])

        # The same score again is silence, not a repeat.
        lines, _ = lt.round_once(m, seen, out, live=[])
        check("round_once: an unchanged score says nothing", lines == [], f"{lines}")

        # Half time, a red card and full time each announce.
        state["s"] = snapshot("0-1", "HT", False)
        lines, _ = lt.round_once(m, seen, out, live=[])
        check("round_once: half time is announced", len(lines) == 1 and "HALF TIME" in lines[0])
        state["s"] = snapshot("0-1", "63'", False, reds=(1, 0))
        lines, _ = lt.round_once(m, seen, out, live=[])
        check("round_once: a red card is announced", len(lines) == 1 and "reds 1-0" in lines[0],
              f"{lines}")
        state["s"] = snapshot("1-1", "FT", True)
        lines, still = lt.round_once(m, seen, out, live=[])
        check("round_once: full time is announced and the match stops counting",
              len(lines) == 1 and "FULL TIME" in lines[0] and still == 0, f"{lines} still={still}")
        check("round_once: every poll kept its snapshot",
              len((out / "1.jsonl").read_text(encoding="utf-8").strip().splitlines()) == 6)

        # A match that has not kicked off is never polled and keeps the day open.
        lt.snap = lambda mid: (_ for _ in ()).throw(AssertionError("polled before kickoff"))
        lines, still = lt.round_once([match("2", future_ko)], {}, out, live=[])
        check("round_once: a match before kickoff is not polled, and the day stays open",
              lines == [] and still == 1, f"{lines} still={still}")
finally:
    lt.snap, lt.sportybet_live = _saved_snap, _saved_sb

# --------------------------------------------------------------------------
# The full-time summary
_matches = [match("1", "2026-10-14T18:45Z"), match("2", "2026-10-14T19:00Z")]
_text = ll.summary("2026-10-14", _matches, {"1": ("2-1", True, (0, 0), False)})
check("summary: names every tracked match", _text.count("Norwich") == 2)
check("summary: carries the final score it saw", "2-1" in _text)
check("summary: a score that never arrived reads PENDING (HR35)", "PENDING" in _text)
check("summary: says nothing was bet", "Architect deploys" in _text)

# --------------------------------------------------------------------------
# Hand-off before the 6-hour job limit
_t0 = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)
check("hand off: not before the limit is near",
      not ll.should_hand_off(_t0, _t0 + timedelta(hours=5)))
check("hand off: before GitHub kills the job at 6 h",
      ll.should_hand_off(_t0, _t0 + timedelta(hours=5, minutes=31)))
check("hand off: the window leaves room to save and dispatch",
      timedelta(hours=6) - timedelta(minutes=20) > ll.HANDOFF_AFTER,
      f"{ll.HANDOFF_AFTER}")

# first_kickoff drives the "too early" exit
check("first kickoff: the earliest of the day",
      ll.first_kickoff(_matches) == datetime(2026, 10, 14, 18, 45, tzinfo=UTC))
check("first kickoff: no fixture carries a kickoff -> None, never a guess",
      ll.first_kickoff([{"id": "x", "calls": []}]) is None)

# --------------------------------------------------------------------------
# Order 33: the Architect's chat only
_wf = (ROOT / ".github" / "workflows" / "live.yml").read_text(encoding="utf-8")
# The comment in live.yml names the secret to say it is deliberately absent, so
# what matters is that the SECRET is never bound into the job's environment.
check("order 33: the tracker never carries the subscriber secret",
      "secrets.TELEGRAM_SUBSCRIBER_CHAT_IDS" not in _wf)
check("order 33: it does carry the Architect's chat", "TELEGRAM_CHAT_ID" in _wf)
check("live.yml: one loop at a time, handed off before the job limit",
      "handoff" in _wf and "timeout-minutes: 355" in _wf)
check("live.yml: started by the board run too",
      "live.yml/dispatches" in (ROOT / ".github" / "workflows" / "daily.yml")
      .read_text(encoding="utf-8"))
_src = (ROOT / "monitor" / "live_loop.py").read_text(encoding="utf-8")
check("live_loop: sends through send_architect, never deliver()",
      "send_architect" in _src and "notify.deliver(" not in _src)
check("live_loop: a quiet round sends nothing", "if lines:" in _src)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    for n in FAILED:
        print(f"  - {n}")
    sys.exit(1)
print("live loop: all checks passed")
