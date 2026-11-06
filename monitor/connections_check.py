"""
CONNECTION GAPS (Architect 2026-11-06: "make sure it's all connected, it's all inheriting what's
supposed to inherit, and there are no gaps"). Reads config/sport_connections.json and prints every
open gap per sport. Exit 1 when a LIVE-BLOCKING gap (a bot that cannot stake the sport) is still
open on or after the sport's live date (config/sport_rollout.json), so the run fails, the watchdog
opens an auto-fix issue and the fixer closes it.

    python monitor/connections_check.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def gaps(today: str, reg: dict | None = None, rollout: dict | None = None) -> tuple[list[str], list[str]]:
    reg = reg or json.loads((ROOT / "config" / "sport_connections.json").read_text(encoding="utf-8"))
    rollout = rollout or json.loads((ROOT / "config" / "sport_rollout.json").read_text(encoding="utf-8"))
    live: dict[str, str] = {}
    for s in rollout["sports"]:
        for name in [s["sport"], *s.get("covers", [])]:
            live[name] = s["live_from"]
    lines, blocking = [], []
    for sport, caps in reg["sports"].items():
        open_ = [c for c, v in caps.items() if v["status"] == "todo"]
        if open_:
            lines.append(f"{sport}: {len(open_)} open: " + ", ".join(f"{c} ({caps[c].get('issue')})" for c in open_))
        due = live.get(sport)
        if due and due[:1].isdigit() and today >= due:
            blocking += [f"{sport} is live since {due} but {c} is open ({caps[c].get('issue')})"
                         for c in reg["live_blocking"] if caps[c]["status"] == "todo"]
    return lines, blocking


def main() -> int:
    lines, blocking = gaps(datetime.now(UTC).strftime("%Y-%m-%d"))
    print("\n".join(lines) or "no open connection gaps")
    for b in blocking:
        print("LIVE GAP:", b)
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
