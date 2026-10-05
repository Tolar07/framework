#!/usr/bin/env python3
"""Rotate .bat-redirected log files that exceed the size threshold.

This script is designed to be called by Task Scheduler *before* each batch
run (run_daily.bat, steward.bat, health_monitor.bat) so that unbounded
append-only logs (poller.log, launcher.log, etc.) are capped at 10 MB with
5 backups. It uses the same rotation logic as monitor.json_log but as a
standalone CLI so it doesn't need to be imported by the batch launchers.

Usage:
    python scripts/rotate_logs.py           # rotate all, report to stderr
    python scripts/rotate_logs.py --json    # emit JSON result to stdout
    python scripts/rotate_logs.py --verify  # just report sizes, no rotation
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor.json_log import rotate_all_bat_logs, BAT_REDIRECTED_LOGS, DEFAULT_MAX_BYTES


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Rotate .bat-redirected log files")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON result to stdout (for automation)")
    ap.add_argument("--verify", action="store_true",
                    help="report current sizes without rotating")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                    help=f"rotation threshold in bytes (default: {DEFAULT_MAX_BYTES})")
    a = ap.parse_args()

    logs_dir = ROOT / "logs"
    if not logs_dir.exists():
        print(f"logs directory not found: {logs_dir}", file=sys.stderr)
        return 1

    if a.verify:
        result = {}
        for fname in BAT_REDIRECTED_LOGS:
            p = logs_dir / fname
            result[fname] = p.stat().st_size if p.exists() else None
        if a.json:
            print(json.dumps(result))
        else:
            for k, v in result.items():
                print(f"{k}: {v if v is not None else 'missing'} bytes")
        return 0

    results = rotate_all_bat_logs(logs_dir=logs_dir, max_bytes=a.max_bytes)
    if a.json:
        print(json.dumps(results))
    else:
        rotated = [k for k, v in results.items() if v]
        if rotated:
            sys.stderr.write(f"Rotated: {', '.join(rotated)}\n")
        else:
            sys.stderr.write("No logs needed rotation.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())