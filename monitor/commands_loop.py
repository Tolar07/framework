"""
COMMANDS LOOP — answer the Architect's Telegram commands within minutes
instead of hours (Architect 2026-10-14: "do the command and dispatch").

WHY. `commands.yml` polled once per hourly cron tick. Measured over the 35
hours to 2026-10-14 17:00 UTC it ran SIX times: 13:36, 07:28, 01:47, 22:36,
17:31, 09:17. So /board or /status could sit unanswered for six hours, and
nothing said so — the workflow's own history looks like a wall of green.
GitHub drops these ticks; that is not a fault we can fix from here.

WHAT. One job stays up and calls `telegram_commands.poll_once()` every
EVERY_MIN minutes, following the pre-kickoff loop's discipline through
`monitor/loop_util.py`: one loop at a time, hand off before GitHub's 6-hour
job limit, save state as it goes. Four jobs cover a day, and the hourly cron
becomes a backup STARTER — a tick that finds a loop running exits at once.

Each round starts from the latest main, because /board and /status read the
board and ledger files that `daily.yml` commits. State the next round must see
(/log's paper legs, /note's corrections, the read offset) is committed right
after the round that produced it, so an answered command is never answered
twice.

    python monitor/commands_loop.py              poll every 5 min, all day
    python monitor/commands_loop.py --once       one pass (what the old job did)
    python monitor/commands_loop.py --handoff    internal: started by the previous run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import loop_util as lu  # noqa: E402

WORKFLOW = "commands.yml"
EVERY_MIN = 5
SAVE_PATHS = ["clv/clv_log.json", "memory/"]


def sync() -> None:
    """Start each round from the latest main: /board and /status must answer
    from the board that is live now, not the one this job checked out."""
    lu.git("fetch", "-q", "origin", "main")
    lu.git("reset", "-q", "--hard", "origin/main")
    from monitor import fdata
    fdata.refresh()


def round_once(now: datetime) -> list[str]:
    """One poll. Returns the log lines; the caller decides what to save."""
    from output import telegram_commands as tc
    try:
        return tc.poll_once()
    except Exception as e:  # noqa: BLE001 — one bad round never ends the loop
        return [f"poll failed: {str(e)[:80]}"]


def handled_something(notes: list[str]) -> bool:
    """True when the round actually answered a command, so there is state worth
    committing. "no new commands" and a failed poll are not state."""
    return any(n.startswith("handled ") for n in notes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="answer Telegram commands all day")
    ap.add_argument("--once", action="store_true", help="a single poll, then exit")
    ap.add_argument("--handoff", action="store_true",
                    help="started by the previous loop run — don't wait for it to end")
    a = ap.parse_args(argv)
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0") or 0)
    started = datetime.now(UTC)

    if a.once:
        for n in round_once(started):
            print(n, flush=True)
        return 0

    if not a.handoff and repo and token and lu.other_loop_running(WORKFLOW, repo, token, run_id):
        print("a commands loop is already running — nothing to do")
        return 0

    print(f"answering commands every {EVERY_MIN} min until the job limit", flush=True)
    while True:
        now = datetime.now(UTC)
        sync()
        notes = round_once(now)
        for n in notes:
            print(f"[{now:%H:%M}Z] {n}", flush=True)
        if handled_something(notes):
            print(f"[{now:%H:%M}Z] {lu.save(SAVE_PATHS, f'telegram commands {now:%Y-%m-%dT%H:%M} [skip ci]')}",
                  flush=True)
        if datetime.now(UTC) - started >= lu.HANDOFF_AFTER:
            if repo and token:
                lu.hand_off(WORKFLOW, repo, token)
                print("handed off to a fresh run (job time limit)", flush=True)
            else:
                print("job time limit reached and no token to hand off with — "
                      "commands are NOT answered until the next cron tick", flush=True)
            return 0
        time.sleep(EVERY_MIN * 60)


if __name__ == "__main__":
    raise SystemExit(main())
