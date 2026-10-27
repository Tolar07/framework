"""Run watchdog — notices when a scheduled daily board run DIDN'T happen,
and starts it.

daily.yml alerts on a run that FAILS, but nothing noticed a run that never
started: GitHub fires scheduled crons hours late or drops them (2026-09-30:
the 06:00 run never fired), and a dropped run is pure silence. This closes
that gap.

It runs from .github/workflows/watchdog.yml a couple of hours after each
board slot and asks the GitHub API whether ANY daily.yml run (scheduled,
Routine dispatch or manual) completed successfully inside the slot's window.
If none did, it starts the slot's board itself (workflow_dispatch with the
slot's target_date and slot, so daily.yml's duplicate guard stops a late
GitHub cron from sending it twice) and says so on Telegram. If it cannot
start it, the alert gives the exact inputs to start it by hand. A failed
run already alerted from daily.yml, and a run still going will either
deliver or alert, so neither is acted on here.

Slots (UK time, daylight saving included — engine/uktime.py; Architect
2026-10-15: "we are in the UK, not Lagos" -> "UK time for everything"):
  evening — board run due 21:47 UK for TOMORROW's card
  morning — board run due 06:47 UK for today's card
The window opens WINDOW_LEAD before the slot's UK time. It used to open hours
earlier (18:00 / 03:00 UTC), but in winter daily.yml's BST cron fires an hour
before the slot and ends at its UK-time gate with conclusion 'success' — a
run that sent nothing must not count as the board.
The crons are UTC, so in winter (GMT) a check can land before its slot's UK
time; such an EARLY check does nothing and leaves the slot to the board clock.
GitHub fires this repo's crons hours late, so an evening check that lands
after midnight UTC still checks (and if needed starts) the evening just past.

Never raises from the CLI: a watchdog that crashes is just more silence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import uktime  # noqa: E402
from output import notify  # noqa: E402

SLOTS = tuple(uktime.SLOT_UK)
WINDOW_LEAD = timedelta(minutes=10)    # a starter a few minutes early still counts
WORKFLOW_FILE = "daily.yml"
API = "https://api.github.com/repos/{repo}/actions/workflows/" + WORKFLOW_FILE

OK, RUNNING, FAILED, MISSED = "ok", "running", "failed", "missed"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_runs(runs: list[dict], window_start: datetime) -> tuple[str, str]:
    """(state, reason) for the daily.yml runs GitHub lists.

    OK when at least one run created at/after window_start finished with
    conclusion 'success'; RUNNING when one is still queued or in progress;
    FAILED when one failed (daily.yml's own failure alert already went out);
    MISSED when none started, or the only ones were cancelled or timed out
    (those send no failure alert)."""
    in_window = [r for r in runs if _parse_ts(r["created_at"]) >= window_start]
    if any(r.get("conclusion") == "success" for r in in_window):
        return OK, "a daily board run succeeded in the window"
    if any(r.get("status") != "completed" for r in in_window):
        return RUNNING, "a daily board run started and has not finished yet"
    if any(r.get("conclusion") == "failure" for r in in_window):
        return FAILED, "the daily board run failed (daily.yml sent the failure alert)"
    if in_window:
        return MISSED, "the daily board run was cancelled or timed out"
    return MISSED, "no daily board run started at all"


def window_start(slot: str, now: datetime) -> datetime:
    """Start of the slot's window: WINDOW_LEAD before today's slot (UK time),
    or yesterday's when the check lands before it (an evening check GitHub
    fired after midnight)."""
    today = uktime.uk(now).date()
    start = uktime.slot_start(slot, today) - WINDOW_LEAD
    if start > now:
        start = uktime.slot_start(slot, today - timedelta(days=1)) - WINDOW_LEAD
    return start


def target_date(slot: str, start: datetime) -> date:
    """The card the slot builds (UK date): the evening run builds TOMORROW's,
    the morning run today's (same rule as daily.yml)."""
    return uktime.target_card(slot, uktime.uk(start + WINDOW_LEAD).date())


def missed_text(slot: str, reason: str, now: datetime, day: date, repo: str,
                started: bool, error: str = "") -> str:
    head = f"⚠ OLP XDV WATCHDOG — no {slot} board by {uktime.hm(now)} UK time: {reason}."
    link = f"https://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}"
    if started:
        return (f"{head}\nStarted it now: the {slot} board for {day}. "
                f"It follows in a few minutes. Runs: {link}")
    return (f"{head}\nCould not start it automatically ({error}). Start it by hand: "
            f"GitHub Actions → OLP XDV daily board → Run workflow, with day {day} "
            f"and slot {slot} (that slot stops a late GitHub run from sending it "
            f"twice): {link}")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def fetch_runs(repo: str, token: str, since: datetime) -> list[dict]:
    url = (API.format(repo=repo) + "/runs?per_page=50&created=%3E%3D"
           + since.strftime("%Y-%m-%dT%H:%M:%SZ"))
    req = urllib.request.Request(url, headers=_headers(token))  # noqa: S310 (fixed https URL)
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        return json.load(r).get("workflow_runs", [])


def start_board(repo: str, token: str, slot: str, day: date) -> None:
    """workflow_dispatch daily.yml on main for one slot's card. Raises on
    any refusal (GitHub answers 204 when the run is created)."""
    body = json.dumps({"ref": "main",
                       "inputs": {"target_date": day.isoformat(), "slot": slot}})
    req = urllib.request.Request(  # noqa: S310 (fixed https URL)
        API.format(repo=repo) + "/dispatches", data=body.encode(), method="POST",
        headers=_headers(token))
    with urllib.request.urlopen(req, timeout=30):  # noqa: S310 (fixed https URL)
        pass


def _send(msg: str) -> None:
    # The Architect's own chat only — subscribers get the board alone (order 33).
    sent, notes = notify.send_architect(msg)
    print(msg)
    print("alert sent" if sent else "alert NOT sent")
    print("\n".join(notes))


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV missed-run watchdog")
    ap.add_argument("--slot", choices=sorted(SLOTS), required=True)
    a = ap.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    now = now or datetime.now(UTC)
    if uktime.early(a.slot, now):
        print(f"{a.slot} slot: {uktime.hm(now)} UK is before its {a.slot} time — "
              "nothing to check yet (the board clock starts it)")
        return 0
    start = window_start(a.slot, now)
    day = target_date(a.slot, start)
    try:
        state, reason = check_runs(fetch_runs(repo, token, start), start)
    except Exception as e:  # can't see the runs: say so rather than guess
        msg = missed_text(a.slot, f"watchdog could not read run history ({e})",
                          now, day, repo, started=False, error="run history unreadable")
        _send(msg)
        return 1
    print(f"{a.slot} slot ({day} card) since {start:%Y-%m-%d %H:%M}Z: "
          f"{state.upper()} — {reason}")
    if state != MISSED:
        return 0
    try:
        start_board(repo, token, a.slot, day)
        started, error = True, ""
    except Exception as e:
        started, error = False, str(e)
    _send(missed_text(a.slot, reason, now, day, repo, started, error))
    return 0 if started else 1


if __name__ == "__main__":
    sys.exit(main())
