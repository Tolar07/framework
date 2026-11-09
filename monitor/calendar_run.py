"""
SPORT CALENDAR RUN: engine/sport_calendar.py for today (UTC) over every sport (football, basketball incl. NBA /
NCAA / EuroLeague, and the rollout sports), written to output/calendar/calendar_<date>.json, then the COMING UP
lines and the expected-volume label of each sport's next board day.

    python monitor/calendar_run.py [--date YYYY-MM-DD] [--sport football ...]

Started by .github/workflows/preview.yml (twice a day, before the preview boards). RECORDED ONLY: it changes no
pick, stake, threshold or rule; its file is saved to framework-data with the previews.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import sport_calendar as SC  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="sport calendar (recorded only)")
    ap.add_argument("--date", default=None, help="the calendar's first day (default today, UTC)")
    ap.add_argument("--sport", action="append", choices=SC.SPORTS, help="only these sports (default all)")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.date) if a.date else None
    doc = SC.build(today, sports=tuple(a.sport) if a.sport else SC.SPORTS)
    path = SC.save(doc)
    bad = [s for s in doc["sources"] if not s["ok"]]
    print(f"calendar {doc['date']}: {len(doc['sports'])} sports, {len(doc['sources'])} sources "
          f"({len(bad)} failed) -> {path.relative_to(ROOT).as_posix()}")
    for s in bad:
        print(f"  source failed: {s['sport']} {s['source']} {s.get('league') or ''}: {s.get('error')}")
    print("COMING UP (next 14 days)")
    for line in SC.coming_up_lines(doc, doc["date"], 14):
        print("  " + line)
    tomorrow = sorted(doc["sports"].get("football", {}).get("days", {}))[1:2]
    for sport, s in doc["sports"].items():
        for d in tomorrow:
            v = s["volume"].get(d) or {}
            print(f"  volume {sport} {d}: {v.get('level')} ({v.get('reason')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
