"""Run watchdog — notices when a scheduled daily board run DIDN'T happen.

daily.yml alerts on a run that FAILS, but nothing noticed a run that never
started: GitHub fires scheduled crons hours late or drops them (2026-09-30:
the 06:00 run never fired), and a dropped run is pure silence. This closes
that gap.

It runs from .github/workflows/watchdog.yml a couple of hours after each
board slot and asks the GitHub API whether ANY daily.yml run (scheduled,
Routine dispatch or manual) completed successfully inside the slot's window.
If none did, it sends a Telegram alert. A failed run already alerted from
daily.yml itself, so a window holding only failures is reported as such but
not re-alerted.

Slots (UTC; Lagos is UTC+1, no DST):
  evening — board run due 20:47, window 18:00-now, checked ~23:17
  morning — board run due 05:47, window 03:00-now, checked ~08:17

Never raises from the CLI: a watchdog that crashes is just more silence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import notify  # noqa: E402

WINDOW_START_UTC_HOUR = {"evening": 18, "morning": 3}
WORKFLOW_FILE = "daily.yml"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_runs(runs: list[dict], window_start: datetime) -> tuple[bool, str]:
    """(ok, reason) for the daily.yml runs GitHub lists.

    ok is True when at least one run created at/after window_start finished
    with conclusion 'success'. Otherwise reason says what was seen: nothing
    at all, only failures (already alerted by daily.yml), or a run still
    in progress."""
    in_window = [r for r in runs if _parse_ts(r["created_at"]) >= window_start]
    if any(r.get("conclusion") == "success" for r in in_window):
        return True, "a daily board run succeeded in the window"
    if not in_window:
        return False, "no daily board run started at all"
    if any(r.get("status") != "completed" for r in in_window):
        return False, "a daily board run started but has not finished"
    return False, "every daily board run in the window failed"


def alert_needed(ok: bool, reason: str) -> bool:
    """Failures already alert from daily.yml; alert here for the silent cases."""
    return not ok and reason != "every daily board run in the window failed"


def alert_text(slot: str, reason: str, repo: str) -> str:
    return (f"⚠ OLP XDV WATCHDOG — no {slot} board yet: {reason}.\n"
            f"GitHub may have dropped or delayed the run. Start it by hand from GitHub Actions "
            f"(OLP XDV daily board → Run workflow): "
            f"https://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}")


def fetch_runs(repo: str, token: str, since: datetime) -> list[dict]:
    url = (f"https://api.github.com/repos/{repo}/actions/workflows/"
           f"{WORKFLOW_FILE}/runs?per_page=50&created=%3E%3D"
           f"{since.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (fixed https URL)
        return json.load(r).get("workflow_runs", [])


def window_start(slot: str, now: datetime) -> datetime:
    return now.replace(hour=WINDOW_START_UTC_HOUR[slot], minute=0,
                       second=0, microsecond=0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV missed-run watchdog")
    ap.add_argument("--slot", choices=sorted(WINDOW_START_UTC_HOUR), required=True)
    a = ap.parse_args(argv)
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    now = datetime.now(UTC)
    start = window_start(a.slot, now)
    try:
        ok, reason = check_runs(fetch_runs(repo, token, start), start)
    except Exception as e:  # can't see the runs: say so rather than guess
        ok, reason = False, f"watchdog could not read run history ({e})"
    print(f"{a.slot} slot since {start:%Y-%m-%d %H:%M}Z: "
          f"{'OK' if ok else 'MISSED'} — {reason}")
    if alert_needed(ok, reason):
        sent, notes = notify.send_telegram(alert_text(a.slot, reason, repo))
        print("alert sent" if sent else f"alert NOT sent: {notes}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
