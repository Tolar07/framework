#!/usr/bin/env python3
"""
calibration_tracker.py — the real learning signal, separate from
"did yesterday's pick win."

Core idea: a single loss on a 51% pick tells you almost nothing. What
tells you something is whether, across many picks the model called
"~50-60%", the actual hit rate over time IS ~50-60%. This buckets every
graded pick by its predicted probability, tracks real outcome frequency
per bucket, and computes a Brier score (the standard proper scoring rule
for probabilistic forecasts) -- these are the numbers that should drive
engine parameter re-fits, not any single day's result.

Feed it verified results (from verify_results.py) joined back to the
original prediction that was made for that fixture. Run it periodically
(weekly, or every N new legs) -- not daily; calibration needs volume to
mean anything, and re-fitting engine parameters off a handful of new
results would itself be a form of chasing noise.

Usage:
    python calibration_tracker.py --log calibration_log.jsonl --report

Each call to record_outcome() appends one line to the log. Nothing here
touches engine parameters directly -- it produces the numbers a human (or
a separate, explicitly-approved re-fit step) uses to decide whether
recalibration is warranted. Keeping "measure" and "act" separate is
deliberate: an automatic pipeline that measures its own miscalibration
and immediately rewrites its own parameters with no review is the
self-rewriting-bot pattern the framework has already ruled out for
anything capital-adjacent.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class GradedPick:
    fixture: str
    market: str            # e.g. "Under 2.5 goals", "BTTS - no"
    predicted_prob: float  # 0.0-1.0, what the engine said at pick time
    outcome_hit: bool      # did the picked outcome actually happen
    date: str


def record_outcome(log_path: Path, pick: GradedPick) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(pick)) + "\n")


def load_log(log_path: Path) -> list[GradedPick]:
    if not log_path.exists():
        return []
    picks = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                picks.append(GradedPick(**json.loads(line)))
    return picks


def bucket(prob: float) -> str:
    lo = int(prob * 10) * 10
    hi = lo + 10
    return f"{lo}-{hi}%"


def brier_score(picks: list[GradedPick]) -> float:
    """Lower is better. 0 = perfect, 0.25 = no better than always guessing 50%."""
    if not picks:
        return float("nan")
    total = sum((p.predicted_prob - (1.0 if p.outcome_hit else 0.0)) ** 2 for p in picks)
    return total / len(picks)


def reliability_report(picks: list[GradedPick]) -> dict:
    buckets: dict[str, list[GradedPick]] = defaultdict(list)
    for p in picks:
        buckets[bucket(p.predicted_prob)].append(p)

    report = {}
    for b, items in sorted(buckets.items()):
        actual_rate = sum(1 for i in items if i.outcome_hit) / len(items)
        avg_predicted = sum(i.predicted_prob for i in items) / len(items)
        report[b] = {
            "n": len(items),
            "avg_predicted": round(avg_predicted, 3),
            "actual_hit_rate": round(actual_rate, 3),
            "gap": round(actual_rate - avg_predicted, 3),
        }
    return report


def print_report(picks: list[GradedPick]) -> None:
    n = len(picks)
    print(f"Total graded picks: {n}")
    if n < 30:
        print("Fewer than 30 legs — per the framework's own Phase 3 gate, this is "
              "too small a sample to draw calibration conclusions from. Report shown "
              "for visibility only; don't act on it yet.")
        print()

    print(f"Brier score (overall): {brier_score(picks):.4f}  "
          f"(0 = perfect, 0.25 = no better than a coin flip)")
    print()
    print("Reliability by predicted-probability bucket:")
    print(f"{'Bucket':<10} {'n':>5} {'Avg predicted':>15} {'Actual hit rate':>17} {'Gap':>8}")
    for b, stats in reliability_report(picks).items():
        flag = ""
        if stats["n"] >= 10 and abs(stats["gap"]) > 0.10:
            flag = "  ⚠ systematic gap — worth investigating (not a single-day thing)"
        print(f"{b:<10} {stats['n']:>5} {stats['avg_predicted']:>15} "
              f"{stats['actual_hit_rate']:>17} {stats['gap']:>+8.3f}{flag}")

    print()
    print("A bucket with n<10 isn't meaningful yet — small samples swing a lot by "
          "chance alone. A persistent gap in a bucket with real volume (n>=10, "
          "ideally much more) is the actual signal that engine parameters may need "
          "re-fitting — take that to a deliberate, reviewed re-fit step, not an "
          "automatic same-day adjustment.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="calibration_log.jsonl")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    picks = load_log(Path(args.log))
    if args.report:
        print_report(picks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())