"""Dead-man's-switch alert for the 07:00 daily run.

The daily run and health monitor both log, but:
- The health monitor alerts on STATE CHANGES only (not on every check)
- A silent cron failure (Task Scheduler disabled, machine asleep) looks identical
  to "nothing to report today" — no run = no log = no alert

This module runs on its OWN schedule (~08:00, AFTER the daily run slot) and
fires a DISTINCT alert if no complete-and-delivered run is found for today.

Separate from the watchdog (which validates a known run's log) and the health
monitor (which checks system health on its own schedule). This is specifically:
"Did the 07:00 job fire and succeed?" — a yes/no dead-man's switch.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import run_watchdog
from output import notify
from monitor import alert_dispatcher

DEFAULT_LOGS_DIR = ROOT / "logs"


def check_today_complete(logs_dir: Path | None = None) -> tuple[bool, list[str]]:
    """Did TODAY's daily run complete AND deliver?

    Returns (complete, reasons). A missing log or incomplete delivery both
    return False with concrete reasons.
    """
    today = date.today().isoformat()
    logs_dir = logs_dir or DEFAULT_LOGS_DIR
    log_path = logs_dir / f"daily_{today}.log"

    reasons: list[str] = []
    if not log_path.exists():
        return False, [f"no daily log for {today} at {log_path} — the run never started"]

    text = log_path.read_text(encoding="utf-8", errors="replace")

    ok = "run completed OK" in text
    if not ok:
        reasons.append("log exists but no 'run completed OK' — the run did not finish")

    delivered = any("delivered" in line and "to Telegram" in line
                    for line in text.splitlines())
    if not delivered:
        reasons.append("no 'delivered N part(s) to Telegram' line — the board did not reach the phone")

    return ok and delivered, reasons


def alert_text(today: str, reasons: list[str]) -> str:
    return (
        f"🚨 OLP XDV DEAD-MAN'S-SWITCH — the {today} 07:00 run DID NOT COMPLETE\n\n"
        + "\n".join(f"• {r}" for r in reasons)
        + "\n\nThis is NOT the health monitor — this is the 08:00 dead-man's-switch. "
        "The daily run either didn't fire, crashed, or failed to deliver. "
        "Check Task Scheduler ('OLP XDV Daily Board') and "
        f"logs/daily_{today}.log immediately."
    )


def verify(logs_dir: Path | None = None, notify_fn=None) -> tuple[bool, list[str]]:
    """Verify today's run; alert via Telegram if incomplete.

    Returns (run_was_complete, notes). Never raises.
    """
    today = date.today().isoformat()
    notes: list[str] = []
    complete, reasons = check_today_complete(logs_dir)

    if complete:
        notes.append(f"{today}: 07:00 run complete and delivered — OK")
        return True, notes

    # Distinct alert — this is the dead-man's-switch, not health monitor
    notes.append(f"{today}: 07:00 run MISSING/INCOMPLETE — {'; '.join(reasons)}")
    try:
        # Multi-channel dispatch (Telegram + email + webhook)
        results_disp = alert_dispatcher.dispatch_alert(
            "critical",
            f"OLP XDV DEAD-MAN'S-SWITCH — the {today} 07:00 run DID NOT COMPLETE",
            "\n".join(f"• {r}" for r in reasons) + "\n\nThis is NOT the health monitor — this is the 08:00 dead-man's-switch. "
                "The daily run either didn't fire, crashed, or failed to deliver. "
                f"Check Task Scheduler ('OLP XDV Daily Board') and logs/daily_{today}.log immediately.",
            tags=["dead-man", "daily-run", today.replace("-", "")],
        )
        ok = any(ok for ok, _ in results_disp.values())
        notes.append("DEAD-MAN'S-SWITCH ALERT dispatched multi-channel" if ok
                     else f"ALERT delivery failed: {results_disp}")
    except Exception as e:
        # Fallback to original notify.send_alert
        send = notify_fn or notify.send_alert
        try:
            ok, n = send(alert_text(today, reasons))
            notes.append("DEAD-MAN'S-SWITCH ALERT sent to Telegram (fallback)" if ok
                         else f"ALERT delivery failed: {n}")
        except Exception as e2:
            notes.append(f"ALERT delivery raised ({e2}) — dead-man's-switch continues")
    return False, notes


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="OLP XDV 07:00 run dead-man's-switch (run ~08:00)")
    ap.add_argument("--logs-dir", default=None,
                    help="path to logs/ (default: repo logs/)")
    a = ap.parse_args()
    logs = Path(a.logs_dir) if a.logs_dir else None
    complete, notes = verify(logs)
    for n in notes:
        print(n)
    # Exit 0 if OK, 2 if incomplete (so scheduler history shows the difference)
    sys.exit(0 if complete else 2)