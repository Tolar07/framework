"""Apply the graded heartbeat backlog to the lineage population.

Grading was never wired (`record_heartbeat_result` had no caller), so results
accumulated in history.jsonl while the lineages sat at 0W/0L. This walks the
graded records and runs the survival transition that should have run daily.

ARCHITECT RULING 2026-09-19 — LATEST RESULT PER LINEAGE.
ln_d6ef3f7604 lost on 09-17, which under the extinction rule should have
ended it, and then staked and won again on 09-18 because nothing had applied
the 09-17 result. Asked how to treat that orphan, the Architect ruled that the
09-18 win stands: apply only each lineage's most recent graded result. So this
does NOT replay history chronologically — replaying would extinguish
ln_d6ef3f7604 at 09-17 and void a real, verified win.

Consequence, recorded deliberately: a LOSS did not end that bloodline. The
extinction rule holds from here forward, where grading runs daily and a loss
is applied before the lineage can stake again.

Usage:
    python scripts/apply_heartbeat_backlog.py           # report only
    python scripts/apply_heartbeat_backlog.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.heartbeat_lineage import (  # noqa: E402
    load_population, record_heartbeat_result,
)
from output.heartbeat import HeartbeatFixture  # noqa: E402

HISTORY = Path(__file__).resolve().parent.parent / "data" / "heartbeat" / "history.jsonl"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]
    graded = [r for r in rows
              if r.get("result") in ("WIN", "LOSS") and r.get("lineage_id")]

    latest: dict[str, dict] = {}
    for r in sorted(graded, key=lambda x: x["date"]):
        latest[r["lineage_id"]] = r  # later date wins

    pop = load_population()
    print(f"H| BEFORE: {len(pop.lineages)} lineages, "
          f"{sum(1 for l in pop.lineages if l.alive)} alive, "
          f"bankroll {round(sum(l.bankroll for l in pop.lineages if l.alive), 2)}")
    print(f"H| {len(graded)} graded records -> {len(latest)} lineages with a latest result")
    print()

    for lid, r in sorted(latest.items()):
        superseded = [x for x in graded
                      if x["lineage_id"] == lid and x["date"] < r["date"]]
        note = f"  (supersedes {', '.join(x['date'] + ' ' + x['result'] for x in superseded)})" if superseded else ""
        print(f"H| {lid}  {r['date']}  {r['result']:4} @ {r.get('price')}  "
              f"{str(r.get('fixture'))[:34]}{note}")
        if args.apply:
            hb = HeartbeatFixture(
                fixture=r.get("fixture") or "",
                kickoff_time=r.get("kickoff_time") or "",
                league=r.get("league") or "",
                pick=r.get("pick") or "",
                probability=r.get("probability") or 0.0,
                edge=r.get("edge") or 0.0,
                market_type=r.get("market_type") or "OTHER",
                market_key=r.get("market_key"),
                price=r.get("price"),
                lineage_id=lid,
            )
            record_heartbeat_result(hb, r["result"], target_date=r["date"])

    if not args.apply:
        print("\nH| report only; re-run with --apply")
        return 0

    pop = load_population()
    alive = [l for l in pop.lineages if l.alive]
    print()
    print(f"H| AFTER: {len(pop.lineages)} lineages, {len(alive)} alive, "
          f"bankroll {round(sum(l.bankroll for l in alive), 2)}")
    for l in sorted(pop.lineages, key=lambda x: (not x.alive, x.lineage_id)):
        print(f"H|   {l.lineage_id}  {'ALIVE ' if l.alive else 'EXTINCT'}  "
              f"bank {l.bankroll:<8} W{l.wins} L{l.losses}  last={l.last_result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
