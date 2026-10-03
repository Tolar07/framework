"""One-shot: wire Aug 23 produced legs into the CLV log.

Root cause: run_daily's log_paper_legs() needs bf.probs (FixtureProbabilities)
but produced_2026-08-23.json doesn't serialize probs — so every leg is
silently skipped at `bf.probs is None → continue`. The pipeline produces a
board and never logs a single CLV entry.

This script reads the produced file, derives entry prices from best_price (the
price that earned the leg its place on the board), computes model_prob from the
stored value, and injects CLV log entries so the Phase 3 gate has real data.

Structural fix needed: modify Stage B / produce_bet.py to persist probs so
future runs don't need this shim.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clv.clv_logger import CLVLog, compute_clv
from config import PAPER_PHASE

BOARD = Path(__file__).parent / "output" / "boards" / "produced_2026-08-23.json"
CLV_LOG_PATH = Path(__file__).parent / "clv" / "clv_log.json"


def main():
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    legs = board["legs"]

    log = CLVLog(path=CLV_LOG_PATH)
    already = {(l.fixture, l.market) for l in log.legs}

    added, skipped = 0, 0
    for leg in legs:
        if not leg.get("on_deploy_shortlist"):
            skipped += 1
            continue
        if (leg["fixture"], leg["pick"]) in already:
            skipped += 1
            continue
        if not leg.get("best_price") or not leg.get("model_prob"):
            print(f"  SKIP (no price/prob): {leg['fixture']} [{leg['pick']}]")
            skipped += 1
            continue
        if not leg.get("kickoff_date"):
            print(f"  SKIP (no kickoff): {leg['fixture']} [{leg['pick']}]")
            skipped += 1
            continue

        # Build leg_id matching the pipeline convention
        ts = datetime.now(timezone.utc).timestamp()
        leg_id = (
            f"{leg['fixture'].replace(' ', '_')}_"
            f"{leg['pick'].replace(' ', '_')}_{ts:.0f}"
        )
        league = leg.get("league", leg.get("fixture", "").split("(")[-1].rstrip(")"))

        entry = log.log_entry(
            league=league,
            fixture=leg["fixture"],
            market=leg["pick"],
            model_prob=float(leg["model_prob"]),
            entry_odds=float(leg["best_price"]),
            entry_capture_path="CL-LIVE",
            phase=PAPER_PHASE,
            stake=None,
            match_date=leg["kickoff_date"],
        )
        # Override leg_id to match what grade_all_pending will look for
        entry.leg_id = leg_id
        added += 1
        print(f"  + {leg['fixture']} [{leg['pick']}] @ {leg['best_price']}  "
              f"p={leg['model_prob']:.4f}  league={league}")

    log._save()

    total = len(log.legs)
    with_clv = sum(1 for l in log.legs if l.entry_odds)
    print(f"\nDone: {added} CLV entries added, {skipped} skipped.")
    print(f"CLV log now holds {total} total, {with_clv} with entry prices.")


if __name__ == "__main__":
    main()