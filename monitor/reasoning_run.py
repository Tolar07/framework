"""
REASONING RUN — the framework's thinking step over today's and tomorrow's picks files
(engine/reasoning.py), then the record of every past verdict against its result.

    python monitor/reasoning_run.py [--date YYYY-MM-DD] [--force]

A picks file is reasoned once per generated_at: a board rebuilt later is reasoned again.
Advisory only: it writes output/reasoning/ and memory/reasoning_record.json, nothing else.
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
            if (old.get("picks_generated_at") == picks.get("generated_at") and not old.get("note")
                    and old.get("prompt_version") == R.prompt_version()):
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
    rec = R.record()
    R.RECORD.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(R.summary_line(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
