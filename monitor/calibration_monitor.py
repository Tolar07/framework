"""Calibration monitor — tracks model performance per probability bin.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from brain.store import Brain

BINS = [
    (0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
    (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)
]

def check_calibration(brain: Brain) -> str:
    """Analyze predictions and return a calibration report."""
    # Query settled predictions directly - don't rely on predictions_for
    # which returns most recent by predicted_at (unsettled recent runs).
    rows = brain.query("""
        SELECT model_prob, hit, market, model_engine
        FROM predictions
        WHERE hit IS NOT NULL AND model_prob IS NOT NULL
        ORDER BY id ASC
    """)
    preds = [{"model_prob": r["model_prob"], "hit": r["hit"],
              "market": r["market"], "model_engine": r["model_engine"]}
             for r in rows]

    bin_data = defaultdict(lambda: {"n": 0, "hits": 0, "sum_prob": 0.0})

    for p in preds:
        prob = p["model_prob"]
        hit = p["hit"]

        for lo, hi in BINS:
            if lo <= prob < hi:
                bin_data[(lo, hi)]["n"] += 1
                bin_data[(lo, hi)]["hits"] += hit
                bin_data[(lo, hi)]["sum_prob"] += prob
                break

    lines = ["CALIBRATION MONITOR — Per Probability Bin Analysis", ""]
    lines.append(f"{'Bin':<12} | {'n':<6} | {'Hits':<6} | {'Hit Rate':<10} | {'Avg Prob':<10} | {'Err':<6}")
    lines.append("-" * 75)

    for (lo, hi) in BINS:
        data = bin_data[(lo, hi)]
        if data["n"] == 0:
            continue

        hit_rate = data["hits"] / data["n"]
        avg_prob = data["sum_prob"] / data["n"]
        err = (hit_rate - avg_prob) * 100

        lines.append(f"{lo:.1f}-{hi:.1f}".ljust(12) + " | " +
                     f"{data['n']:<6} | {data['hits']:<6} | {hit_rate:>9.1%} | {avg_prob:>9.1%} | {err:>+5.1f}pp")

    return "\n".join(lines)

if __name__ == "__main__":
    with Brain() as brain:
        print(check_calibration(brain))
