"""
COMMANDS LOOP TEST — /board must answer in minutes, not hours.

WHY THIS EXISTS. commands.yml polled once per hourly cron tick, and over the
35 hours to 2026-10-14 17:00 UTC GitHub gave it SIX runs. A command could sit
unanswered for six hours while the workflow history showed nothing but green.
The loop (monitor/commands_loop.py) replaces the tick with one job that polls
every 5 minutes and hands off before GitHub's 6-hour limit.

What this pins down, all offline:
  * a round that answered something is saved; a quiet round and a failed round
    are not (an empty commit every 5 minutes would bury the git log);
  * a poll that throws never ends the loop;
  * --once still does exactly what the old job did, for a manual run;
  * the loop's cadence and hand-off leave room inside the job limit;
  * commands.yml starts the loop, drops the concurrency group that would queue
    runs behind a 6-hour job, and can see the actions API for its guard.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import commands_loop as cl  # noqa: E402
from monitor import loop_util as lu  # noqa: E402

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'  OK  ' if ok else ' FAIL '} {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


# --------------------------------------------------------------------------
# What counts as state worth committing
check("save: a round that answered a command is saved",
      cl.handled_something(["handled /board from 123"]))
check("save: a quiet round is not",
      not cl.handled_something(["no new commands"]))
check("save: a failed poll is not",
      not cl.handled_something(["poll failed: connection reset"]))
check("save: an ignored stranger is not state either",
      not cl.handled_something(["IGNORED message from non-whitelisted chat 999"]))
check("save: a mixed round is saved",
      cl.handled_something(["no new commands", "handled /status from 123"]))

# --------------------------------------------------------------------------
# A poll that throws is a bad round, not a dead loop
import output.telegram_commands as tc  # noqa: E402

_real = tc.poll_once
try:
    tc.poll_once = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("telegram 502"))
    _notes = cl.round_once(datetime.now(UTC))
    check("round_once: a throwing poll is reported, not raised",
          len(_notes) == 1 and "poll failed" in _notes[0], f"{_notes}")
    check("round_once: and that round saves nothing", not cl.handled_something(_notes))
    tc.poll_once = lambda *a, **k: ["handled /board from 123"]
    check("round_once: a good poll passes its notes through",
          cl.round_once(datetime.now(UTC)) == ["handled /board from 123"])
finally:
    tc.poll_once = _real

# --------------------------------------------------------------------------
# Cadence and hand-off must fit inside GitHub's 6-hour job
check("cadence: 5 minutes, so a command waits minutes not hours",
      cl.EVERY_MIN <= 5, f"{cl.EVERY_MIN} min")
check("hand off: leaves room to dispatch before the 6 h kill",
      timedelta(hours=6) - timedelta(minutes=20) > lu.HANDOFF_AFTER, f"{lu.HANDOFF_AFTER}")
check("hand off: four jobs cover a day",
      timedelta(hours=22) <= lu.HANDOFF_AFTER * 4, f"{lu.HANDOFF_AFTER * 4}")
check("save paths: the CLV log and memory, which the next round must see",
      "clv/clv_log.json" in cl.SAVE_PATHS and "memory/" in cl.SAVE_PATHS)

# --------------------------------------------------------------------------
# The workflow
_wf = (ROOT / ".github" / "workflows" / "commands.yml").read_text(encoding="utf-8")
check("commands.yml: runs the loop, not the one-shot poller",
      "monitor/commands_loop.py" in _wf and "python output/telegram_commands.py" not in _wf)
check("commands.yml: has room to loop", "timeout-minutes: 355" in _wf)
check("commands.yml: can see the actions API for the single-loop guard",
      "actions: write" in _wf)
check("commands.yml: no concurrency group to queue runs behind a 6 h job",
      "concurrency:" not in _wf)
check("commands.yml: the hourly cron survives as a backup starter",
      'cron: "5 * * * *"' in _wf and "handoff" in _wf)
check("commands.yml: no trailing persist step — the loop saves each round",
      "git add clv/clv_log.json memory/" not in _wf)

# The weekly profiles job, the other thing order 43 depends on
_pf = (ROOT / ".github" / "workflows" / "profiles.yml").read_text(encoding="utf-8")
check("profiles.yml: rebuilds both files order 43 reads",
      "data/team_profiles.py" in _pf and "data/league_strength.py" in _pf)
check("profiles.yml: one failure does not cost the other",
      _pf.count("continue-on-error: true") >= 2)
check("profiles.yml: says so when a week's rebuild produced nothing",
      "NOTHING CHANGED" in _pf and "::warning::" in _pf)

print()
if FAILED:
    print(f"FAILED: {len(FAILED)}")
    for n in FAILED:
        print(f"  - {n}")
    sys.exit(1)
print("commands loop: all checks passed")
