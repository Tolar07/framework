"""Run watchdog — the instrument that notices when the daily run DIDN'T happen.

The daily run logs loudly inside itself (proof-of-life marker, delivery lines,
'run completed OK') but nothing notices when the run never fires — a disabled
Task Scheduler job, a crash before the first log line, or a machine asleep at
07:00 all produce the same silence. This module closes that gap.

Designed to run on its OWN schedule (Task Scheduler, or any cron) AFTER the
daily run's slot. It checks today's daily log for the two lines that prove a
complete, delivered run:

    - 'run completed OK'               (the run got all the way through)
    - 'delivered N part(s) to Telegram' (the phone actually received the board)

A run that failed on Telegram is NOT complete (run_daily raises on that
deliberately), and a missing log is proof Python never started — both alert.

The alert is best-effort Telegram (send_telegram): the watchdog must never
crash the scheduler. Same discipline as notify/email/whatsapp: returns
(ok, notes), never raises.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import notify

DEFAULT_LOGS_DIR = Path(__file__).parent.parent / "logs"


def check_run_log(log_path: Path) -> tuple[bool, list[str]]:
    """Did the daily run for this date complete AND deliver?

    True only when BOTH 'run completed OK' and a Telegram delivery line are
    present. Anything else is surfaced as a concrete reason, never a guess."""
    if not log_path.exists():
        return False, [f"no log at {log_path} — Python never started the run"]
    text = log_path.read_text(encoding="utf-8", errors="replace")
    reasons: list[str] = []
    ok = "run completed OK" in text
    if not ok:
        reasons.append("log exists but no 'run completed OK' — "
                       "the run did not finish (crashed or still running?)")
    delivered = any("delivered" in line and "to Telegram" in line
                    for line in text.splitlines())
    if not delivered:
        reasons.append("no 'delivered N part(s) to Telegram' line — "
                       "the board did not reach the phone")
    return ok and delivered, reasons


def _alert_text(date_iso: str, reasons: list[str]) -> str:
    return (f"⚠ OLP XDV WATCHDOG — the {date_iso} daily push did NOT happen\n\n"
            + "\n".join(f"• {r}" for r in reasons)
            + "\n\nThe 07:00 board was not delivered. Check the scheduler task "
              "and logs/daily_" + date_iso + ".log.")


def verify(date_iso: str | None = None, logs_dir: Path | None = None,
           notify_fn=None) -> tuple[bool, list[str]]:
    """Verify today's (or --date's) run; alert via Telegram when it's missing.
    Returns (run_was_complete, notes). Never raises."""
    date_iso = date_iso or date.today().isoformat()
    logs_dir = logs_dir or DEFAULT_LOGS_DIR
    notes: list[str] = []
    log_path = logs_dir / f"daily_{date_iso}.log"
    complete, reasons = check_run_log(log_path)
    if complete:
        notes.append(f"{date_iso}: daily run complete and delivered — OK")
        return True, notes
    # Alert (best-effort). notify_fn injectable for tests.
    notes.append(f"{date_iso}: run MISSING or incomplete — "
                 f"{'; '.join(reasons)}")
    send = notify_fn or notify.send_alert
    try:
        ok, n = send(_alert_text(date_iso, reasons))
        notes.append("ALERT sent to Telegram" if ok
                     else f"ALERT delivery failed: {n}")
    except Exception as e:  # watchdog must never crash the scheduler
        notes.append(f"ALERT delivery raised ({e}) — watchdog continues")
    return False, notes


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OLP XDV run watchdog")
    ap.add_argument("--date", default=None,
                    help="ISO date to verify (default: today)")
    ap.add_argument("--logs-dir", default=None,
                    help="path to logs/ (default: repo logs/)")
    a = ap.parse_args()
    logs = Path(a.logs_dir) if a.logs_dir else None
    complete, notes = verify(a.date, logs)
    for n in notes:
        print(n)
    sys.exit(0 if complete else 2)
