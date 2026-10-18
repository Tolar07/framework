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
  * a match with no full time GIVE_UP after kickoff (postponed, abandoned) is
    let go, said once — it can never hold the day open, and a day older than
    yesterday is never tracked (2026-10-18: one loop followed the 17th all day);
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
from monitor import loop_util as lu  # noqa: E402

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

        # A match that never kicks off (postponed) or never reaches full time is
        # let go GIVE_UP after kickoff: said once, then never polled, and it no
        # longer keeps the day open.
        old_ko = (datetime.now(UTC) - lt.GIVE_UP - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%MZ")
        lt.snap = lambda mid: snapshot(None, None, False)
        seen = {}
        lines, still = lt.round_once([match("3", old_ko)], seen, out, live=[])
        check("round_once: a match with no full time after GIVE_UP is let go",
              still == 0 and len(lines) == 1 and "NO FULL TIME" in lines[0], f"{lines} still={still}")
        lt.snap = lambda mid: (_ for _ in ()).throw(AssertionError("polled after giving up"))
        lines, still = lt.round_once([match("3", old_ko)], seen, out, live=[])
        check("round_once: and is said once, then never polled again",
              lines == [] and still == 0, f"{lines} still={still}")
        check("summary: a match let go reads PENDING (HR35)",
              "PENDING" in ll.summary("2026-10-17", [match("3", old_ko)], seen))

        # A match that already reached full time is NOT reported as given up —
        # not even by a run that starts late or after a hand-off (empty seen):
        # it is polled once and its real full time recorded.
        lt.snap = lambda mid: snapshot("2-0", "FT", True)
        seen = {"4": ("2-0", True, (0, 0), False)}
        lines, still = lt.round_once([match("4", old_ko)], seen, out, live=[])
        check("round_once: a finished match is never called 'no full time'",
              lines == [] and still == 0, f"{lines} still={still}")
        seen = {}
        lines, still = lt.round_once([match("5", old_ko)], seen, out, live=[])
        check("round_once: a late start still records the real full time, not 'no full time'",
              still == 0 and len(lines) == 1 and "FULL TIME" in lines[0]
              and "NO FULL TIME" not in lines[0], f"{lines} still={still}")

        # A feed that fails for good is let go too, once past GIVE_UP.
        lt.snap = lambda mid: (_ for _ in ()).throw(RuntimeError("feed down"))
        seen = {}
        lines, still = lt.round_once([match("6", old_ko)], seen, out, live=[])
        check("round_once: a poll that keeps failing past GIVE_UP is let go",
              still == 0 and any("NO FULL TIME" in x for x in lines), f"{lines} still={still}")
finally:
    lt.snap, lt.sportybet_live = _saved_snap, _saved_sb

# A day older than yesterday is over: the loop exits without tracking it.
_old_day = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%d")
_saved_tracked = lt.tracked
try:
    lt.tracked = lambda day, calls: (_ for _ in ()).throw(AssertionError("tracked an old day"))
    check("live_loop: a day older than yesterday is never tracked",
          ll.main(["--day", _old_day, "--handoff"]) == 0)
finally:
    lt.tracked = _saved_tracked

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
      timedelta(hours=6) - timedelta(minutes=20) > lu.HANDOFF_AFTER,
      f"{lu.HANDOFF_AFTER}")

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
check("live.yml: no concurrency group — queued starters were cancelled and a stuck "
      "loop blocked every later day", "\nconcurrency:" not in _wf)
check("live.yml: started by the board run too",
      "live.yml/dispatches" in (ROOT / ".github" / "workflows" / "daily.yml")
      .read_text(encoding="utf-8"))
_src = (ROOT / "monitor" / "live_loop.py").read_text(encoding="utf-8")
check("live_loop: sends through send_architect, never deliver()",
      "send_architect" in _src and "notify.deliver(" not in _src)
check("live_loop: a quiet round sends nothing", "if send:" in _src)
check("live_loop: what is sent goes through the failure filter",
      "worth_telling(lines, said)" in _src)

# --------------------------------------------------------------------------
# A broken feed is said ONCE, not every two minutes for ninety minutes.
# 2026-10-14: snap() crashed on every poll of one match (FotMob sends
# "Periods": null around kickoff and a .get default only covers a MISSING key),
# so on Actions that match would have Telegrammed the same failure ~45 times.
_said: set[str] = set()
_fail = "[16:46Z] Feyenoord v Como: poll failed ('NoneType' object has no attribute 'get')"
_first = ll.worth_telling([_fail], _said)
check("worth_telling: a failure is reported the first time", len(_first) == 1, f"{_first}")
check("worth_telling: and says it will not repeat", "said once" in _first[0])
_again = ll.worth_telling(["[16:48Z] Feyenoord v Como: poll failed "
                           "('NoneType' object has no attribute 'get')"], _said)
check("worth_telling: the same failure two minutes later is silent", _again == [], f"{_again}")
_other = ll.worth_telling(["[16:50Z] Norwich v Southampton: poll failed (timed out)"], _said)
check("worth_telling: a DIFFERENT failure still gets through", len(_other) == 1)
_goal = ll.worth_telling(["[16:52] CHANGE Norwich 1-0 Southampton (20') · xG 0.3-0.1"], _said)
check("worth_telling: a goal always goes through", len(_goal) == 1)
_goal2 = ll.worth_telling(["[16:54] CHANGE Norwich 2-0 Southampton (24') · xG 0.6-0.1"], _said)
check("worth_telling: and so does the next one — events are never deduped",
      len(_goal2) == 1)

# snap()'s null-safety, on the payload shape that actually broke it
_src = (ROOT / "monitor" / "live_tracker.py").read_text(encoding="utf-8")
check("snap: the stats chain uses `or {}`, never a bare .get default",
      '.get("Periods", {})' not in _src and '.get("All", {})' not in _src)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    for n in FAILED:
        print(f"  - {n}")
    sys.exit(1)
print("live loop: all checks passed")
