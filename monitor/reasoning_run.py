"""
REASONING RUN — the framework's thinking step over today's and tomorrow's picks files
(engine/reasoning.py), then the record of every past verdict against its result.

    python monitor/reasoning_run.py [--date YYYY-MM-DD] [--force]

A picks file is reasoned once per generated_at: a board rebuilt later is reasoned again.
It writes output/reasoning/, memory/reasoning_record.json and memory/reasoning_lessons.json, nothing else.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine import reasoning as R  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OLP XDV reasoning step")
    ap.add_argument("--date", action="append", help="picks date(s); default today and tomorrow (UTC)")
    ap.add_argument("--force", action="store_true", help="reason again even if this board was done")
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    dates = a.date or [(now + timedelta(days=k)).date().isoformat() for k in (0, 1)]
    R.OUT_DIR.mkdir(parents=True, exist_ok=True)
    for d in dates:
        src = R.LEDGER_DIR / f"picks_{d}.json"
        if not src.exists():
            print(f"{d}: no picks file yet")
            continue
        picks = json.loads(src.read_text(encoding="utf-8"))
        out = R.OUT_DIR / f"reasoning_{d}.json"
        if out.exists() and not a.force:
            old = json.loads(out.read_text(encoding="utf-8"))
            if old.get("picks_generated_at") == picks.get("generated_at") and not old.get("note"):
                print(f"{d}: already reasoned for this board")
                continue
        doc = R.reason(picks, now=now)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        counts = {v: sum(1 for p in doc["picks"] if p["verdict"] == v) for v in (*R.VERDICTS, "PENDING")}
        print(f"{d}: {len(doc['picks'])} picks · model {doc['model']} · {counts}"
              + (f" · {doc['note']}" if doc["note"] else ""))
        for p in doc["picks"]:
            if p["verdict"] in ("veto", "lower"):
                print(f"  {p['verdict'].upper():5} {p['pick']} — {p['fixture']}: {p.get('reasons', '')}")
    # the NBA board too (Architect 2026-10-20: NBA treated as football is)
    for d in dates:
        src = R.LEDGER_DIR / f"nba_{d}.json"
        if not src.exists():
            continue
        board = json.loads(src.read_text(encoding="utf-8"))
        if not (board.get("picks") or board.get("picks_dropped")):
            print(f"NBA {d}: no picks")
            continue
        out = R.OUT_DIR / f"reasoning_nba_{d}.json"
        if out.exists() and not a.force:
            old = json.loads(out.read_text(encoding="utf-8"))
            if old.get("picks_generated_at") == board.get("generated_at") and not old.get("note"):
                print(f"NBA {d}: already reasoned for this board")
                continue
        doc = R.reason_nba(board, now=now)
        out.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"NBA {d}: {len(doc['picks'])} picks · model {doc['model']} · "
              + ", ".join(f"{p['verdict']} {p['pick']}" for p in doc["picks"])
              + (f" · {doc['note']}" if doc["note"] else ""))
    # the cognitive core grades its own past verdicts (history + post-mortem lessons) before the record
    print(f"cognitive core: {R.grade_cognitive(now=now)} newly graded")
    from engine import verdict_panel as VP     # to-do #5: the panel's out-of-sample record
    try:
        print(f"verdict panel: {VP.grade(now=now)} newly graded · {VP.summary_line()}")
    except Exception as e:  # noqa: BLE001 — never blocks the verdict record
        print(f"verdict panel: grading failed: {e}")
    rec = R.record()
    R.RECORD.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(R.summary_line(rec))
    # once a day per sport, the reasoning rewrites its own lessons from the graded record
    # (memory/reasoning_lessons.json, read by every later run: recursive self-improvement)
    for sport in ("football", "nba"):
        les = R.reflect(sport, now=now)
        if les:
            allx = R.load_lessons()
            allx[sport] = les
            R.LESSONS.write_text(json.dumps(allx, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"lessons {sport}: {len(les['lessons'])} from {les['graded']} graded · {les['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
