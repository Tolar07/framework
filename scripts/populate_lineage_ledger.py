#!/usr/bin/env python3
"""
Populate lineage_ledger.jsonl from history.jsonl as single source of truth.
"""

import json
from datetime import date
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage_ledger import DayRecord, LegOutcome, record_day

REPO_ROOT = Path(__file__).parent.parent
HISTORY_FILE = REPO_ROOT / "data" / "heartbeat" / "history.jsonl"


def main():
    print("Populating lineage_ledger from history.jsonl...")

    if not HISTORY_FILE.exists():
        print("History file not found!")
        return

    # Read history - handle potential missing newlines between records
    records_by_date = {}
    with HISTORY_FILE.open("r", encoding="utf-8") as f:
        content = f.read().strip()

    # Split by '}\n{' or '}\n' patterns to handle malformed JSONL
    # First try standard line-by-line
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # Try to fix by finding record boundaries
            continue
        d = record["date"]
        if d not in records_by_date:
            records_by_date[d] = []
        records_by_date[d].append(record)

    # Create DayRecords and write to ledger
    for d_str in sorted(records_by_date.keys()):
        day_records = records_by_date[d_str]
        legs = []
        for rec in day_records:
            outcome = None
            if rec.get("result") == "WIN":
                outcome = True
            elif rec.get("result") == "LOSS":
                outcome = False
            # PENDING or None stays None

            legs.append(LegOutcome(
                fixture=rec["fixture"],
                market=rec["market_type"],
                predicted_prob=rec["probability"],
                outcome_hit=outcome,
            ))

        day_record = DayRecord(
            date=d_str,
            legs=legs,
            generation=None,  # not tracked in history
            notes="" if legs else "no heartbeat recorded",
        )

        record_day(day_record)
        wins = sum(1 for l in legs if l.outcome_hit is True)
        losses = sum(1 for l in legs if l.outcome_hit is False)
        pending = sum(1 for l in legs if l.outcome_hit is None)
        print(f"  {d_str}: {wins}W / {losses}L / {pending} pending")

    print("\nDone! Lineage ledger populated.")


if __name__ == "__main__":
    main()