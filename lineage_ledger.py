"""
lineage_ledger.py — the missing single source of truth for "what has
the AI survivor / heartbeat actually done since 27 August."

Why this exists: two sessions asked the same lineage question and gave
two different answers, neither capturing yesterday's wins. The likely
cause isn't sessions reading carelessly — it's that lineage history is
scattered across logs/boards/state with no single record, so every
session reconstructs a different partial picture from different
fragments. This file is that missing record: one append-only ledger,
one line per day, and one function every session calls instead of
inferring anything.

This does NOT yet know the "correct" rule for how a win should expand
tomorrow's heartbeat count — that's still an open question for Claude
Code to answer from the real survivor code (see
TASK_prove_date_gate_and_lineage.md, item 3). What this fixes right now
is the disagreement itself: once every day's outcome is written here,
every session reads the same file and gets the same answer, mechanically.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from pathlib import Path

LEDGER_PATH = Path("lineage_ledger.jsonl")


@dataclass
class LegOutcome:
    fixture: str
    market: str
    predicted_prob: float
    outcome_hit: bool | None  # None = not yet verified / no result


@dataclass
class DayRecord:
    date: str                      # "2026-09-01"
    legs: list[LegOutcome] = field(default_factory=list)
    generation: int | None = None  # whatever "generation/tier" number the survivor mechanic uses
    notes: str = ""                # e.g. "pipeline failure — no fixtures produced"

    @property
    def win_count(self) -> int:
        return sum(1 for l in self.legs if l.outcome_hit is True)

    @property
    def loss_count(self) -> int:
        return sum(1 for l in self.legs if l.outcome_hit is False)

    @property
    def pending_count(self) -> int:
        return sum(1 for l in self.legs if l.outcome_hit is None)

    @property
    def had_zero_results(self) -> bool:
        return len(self.legs) == 0


def record_day(record: DayRecord) -> None:
    """
    Append one day's record. Called ONCE per day, by whatever verifies
    results (verify_results.py / the calibration tracker's
    record_outcome loop) — not reconstructed after the fact by a
    session trying to answer a question.

    If a date already has an entry, this appends a SECOND line for that
    date rather than silently overwriting — get_ledger() below always
    uses the LAST entry per date, so a correction is possible, but the
    history of what was recorded when is preserved rather than lost.
    """
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        payload = asdict(record)
        f.write(json.dumps(payload) + "\n")


def load_ledger() -> dict[str, DayRecord]:
    """Returns {date_str: DayRecord}, using the LAST entry per date if
    a date was recorded more than once (a correction)."""
    if not LEDGER_PATH.exists():
        return {}
    by_date: dict[str, DayRecord] = {}
    with open(LEDGER_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            legs = [LegOutcome(**l) for l in raw.get("legs", [])]
            by_date[raw["date"]] = DayRecord(
                date=raw["date"], legs=legs,
                generation=raw.get("generation"), notes=raw.get("notes", ""),
            )
    return by_date


def find_gaps(ledger: dict[str, DayRecord], since: date) -> list[str]:
    """
    Days between `since` and today with NO ledger entry at all — this is
    what "not even capturing wins from yesterday" looks like in data
    form: a hole in the record, not a disagreement about what's in it.
    """
    gaps = []
    d = since
    today = date.today()
    while d <= today:
        if d.isoformat() not in ledger:
            gaps.append(d.isoformat())
        d += timedelta(days=1)
    return gaps


def print_lineage_status(since_str: str = "2026-08-27") -> None:
    """
    THE command every session should run instead of reconstructing
    history from logs. Prints one unambiguous answer.
    """
    ledger = load_ledger()
    since = date.fromisoformat(since_str)

    print(f"=== Lineage status since {since_str} ===\n")

    if not ledger:
        print("LEDGER IS EMPTY. No days have ever been recorded here. "
              "This confirms there is no existing single source of truth — "
              "every prior answer about lineage was a reconstruction from "
              "scattered logs, which is why sessions disagreed.")
        return

    gaps = find_gaps(ledger, since)

    for d_str in sorted(ledger.keys()):
        if d_str < since_str:
            continue
        rec = ledger[d_str]
        if rec.had_zero_results:
            print(f"{d_str}: NO RESULTS RECORDED — {rec.notes or 'no reason given'}")
        else:
            print(f"{d_str}: {rec.win_count}W / {rec.loss_count}L / {rec.pending_count} pending "
                  f"(generation: {rec.generation if rec.generation is not None else 'not tracked'})")

    print(f"\nGaps (days since {since_str} with NO ledger entry at all): {len(gaps)}")
    for g in gaps:
        print(f"  - {g}: nothing recorded")

    if gaps:
        print("\nThese gaps are the actual answer to 'nothing captured yesterday's "
              "wins' — a missing day in the record, not a disagreement about it. "
              "Backfilling these (from whatever raw logs exist for those dates) "
              "is what closes the gap permanently.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print_lineage_status(sys.argv[2] if len(sys.argv) > 2 else "2026-08-27")
    else:
        print("Usage: python lineage_ledger.py status [since_date]")