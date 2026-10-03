"""
Rebuild the heartbeat lineage population by REPLAYING the real graded history.

WHY THIS EXISTS (Architect, 2026-09-17): "the last one that happened,
everything won ... I think it was three that won. So by now we should have six
or more."

That is correct, and the state file disagreed with it. Both independent records
agree that 2026-09-01 graded THREE heartbeats and all three won:

  data/heartbeat/history.jsonl   3 records dated 2026-09-01, result WIN
  lineage_ledger.jsonl           3 legs dated 2026-09-01, outcome_hit true

Under the Architect's reproduction model (WIN -> up to OFFSPRING_PER_WIN
offspring) three simultaneous wins breed six lineages. Instead
data/heartbeat/lineage.json held ONE genesis lineage born 2026-09-03 at the
starvation floor, 0W-0L -- the population had been reset, not evolved, because
nothing ever routed the graded results into the lineage engine (history records
carry no lineage_id at all: 0 of 9).

WHAT THIS DOES
Replays the nine real graded results, in date order, through the real engine
functions -- breed_next_generation then record_heartbeat_result -- so the
resulting population is produced by the model rather than asserted by hand.

WHAT THIS IS NOT
It does not invent a single result. Only the nine graded records are replayed.
Days with no record are skipped, not filled.

KNOWN RECONSTRUCTION LIMIT, stated rather than hidden: history.jsonl carries no
lineage_id, so on a multi-heartbeat day (2026-08-31, 2026-09-01) which result
belongs to which lineage cannot be recovered. Results are therefore assigned in
the engine's own order -- strongest lineage first, matching
select_daily_heartbeats -- which reproduces the correct POPULATION SHAPE and
total lifeforce, but the per-lineage fixture attribution on those two days is
inferred. Every day from here on records its lineage_id, so this ambiguity
cannot recur.

Usage:
    python scripts/rebuild_lineage_from_history.py --dry-run
    python scripts/rebuild_lineage_from_history.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import heartbeat_lineage as HL  # noqa: E402
from output.heartbeat import HISTORY_FILE, HeartbeatFixture  # noqa: E402


def load_graded_history() -> "OrderedDict[str, list[dict]]":
    """Group graded (WIN/LOSS) heartbeat records by date, in date order.

    Ungraded records (result PENDING/None) are ignored: a result that was never
    settled must not drive a birth or a death.
    """
    if not HISTORY_FILE.exists():
        raise SystemExit(f"no history file at {HISTORY_FILE}")

    rows: list[dict] = []
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))

    graded = [r for r in rows if r.get("result") in ("WIN", "LOSS")]
    by_date: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in sorted(graded, key=lambda x: (x.get("date") or "", x.get("timestamp") or "")):
        by_date.setdefault(r["date"], []).append(r)
    return by_date


def replay(by_date: "OrderedDict[str, list[dict]]") -> list[str]:
    """Replay each day's results through the real engine. Returns a trace."""
    trace: list[str] = []

    for day, records in by_date.items():
        # Breed first: yesterday's winners reproduce into today's population,
        # exactly as the daily run now does.
        HL.breed_next_generation([], target_date=day)
        pop = HL.load_population()
        living = sorted(pop.living(), key=lambda ln: ln.bankroll, reverse=True)

        trace.append(
            f"{day}: {len(living)} living lineage(s), {len(records)} graded result(s)"
        )

        for i, rec in enumerate(records):
            if i >= len(living):
                trace.append(
                    f"    ! {rec['fixture']} {rec['result']} — no living lineage "
                    f"to attribute it to; result not applied"
                )
                continue

            hb = HeartbeatFixture(
                fixture=rec.get("fixture", "?"),
                kickoff_time=rec.get("kickoff_time", "??:??"),
                league=rec.get("league", "Unknown"),
                pick=rec.get("pick", "?"),
                probability=rec.get("probability") or 0.0,
                edge=rec.get("edge") or 0.0,
                market_type=rec.get("market_type", "OTHER"),
                bookmaker=rec.get("bookmaker"),
                price=rec.get("price"),
            )
            hb.lineage_id = living[i].lineage_id
            HL.record_heartbeat_result(hb, rec["result"], target_date=day)

            price_note = "" if rec.get("price") else "  (UNPRICED — win counted, not paid)"
            trace.append(
                f"    {living[i].lineage_id[:8]} <- {rec['fixture'][:38]} "
                f"{rec['result']}{price_note}"
            )

    return trace


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="replay against a scratch file; do not touch live state")
    g.add_argument("--apply", action="store_true",
                   help="back up and overwrite data/heartbeat/lineage.json")
    args = ap.parse_args()

    by_date = load_graded_history()
    total = sum(len(v) for v in by_date.values())
    wins = sum(1 for v in by_date.values() for r in v if r["result"] == "WIN")
    print(f"Graded history: {total} result(s) across {len(by_date)} date(s) "
          f"({wins}W-{total - wins}L), {min(by_date)} -> {max(by_date)}")
    print()

    live_file = HL.LINEAGE_FILE
    if args.dry_run:
        HL.LINEAGE_FILE = REPO_ROOT / "data" / "heartbeat" / "lineage.dryrun.json"
        if HL.LINEAGE_FILE.exists():
            HL.LINEAGE_FILE.unlink()
    else:
        if live_file.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = live_file.with_name(f"lineage.json.bak-{stamp}")
            shutil.copy2(live_file, backup)
            print(f"Backed up existing population -> {backup.name}")
        if live_file.exists():
            live_file.unlink()

    # Seed genesis explicitly so the replay starts from a known state rather
    # than whatever happened to be on disk.
    HL.save_population(HL.LineagePopulation(lineages=[HL.Lineage(
        lineage_id=HL._new_id(), parent_id=None, generation=0,
        bankroll=HL.DEFAULT_STARTING_BANKROLL,
        current_stake=HL.DEFAULT_STARTING_STAKE,
        wins=0, losses=0, alive=True, born_date=min(by_date),
    )]))

    for line in replay(by_date):
        print(line)

    print()
    print(HL.render_lineage_report())

    pop = HL.load_population()
    print()
    print(f"RESULT: {len(pop.living())} living lineage(s), "
          f"{len([l for l in pop.lineages if not l.alive])} extinct, "
          f"total lifeforce {sum(l.bankroll for l in pop.living()):.2f}")

    if args.dry_run:
        print(f"\nDRY RUN — live state untouched. Scratch file: {HL.LINEAGE_FILE.name}")
    else:
        print(f"\nAPPLIED to {HL.LINEAGE_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
