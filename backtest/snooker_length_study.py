"""
SNOOKER MATCH-LENGTH CALIBRATION STUDY (framework#340; record-only, a SHADOW candidate, results only).

The board's snooker Elo ignores how long the match is, but a longer match (first-to-10) should favour the better
player more than a short one (first-to-4): luck evens out over more frames. This study takes the walk-forward Elo
chance p (every match scored BEFORE it is learned, same K and min games as the board) and asks, per length bucket
(first-to-4 / 5-6 / 9+), whether stretching its log-odds by a factor s improves the Brier score.
s is chosen on matches before SPLIT only, from a fixed grid; the held-out matches (SPLIT on) are then scored with
that frozen s beside plain Elo. Tries counted = grid size x buckets. No price in the source, so this is accuracy,
never an edge. Missing / thin buckets read PENDING (HR35). Nothing here changes a pick rule, a stake, a bar or the
live switch.

  python backtest/snooker_length_study.py     writes backtest/SNOOKER_LENGTH_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from math import exp, log
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from backtest import snooker_backtest as sb  # noqa: E402
from backtest import snooker_frames_study as sf  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "SNOOKER_LENGTH_STUDY.md"
SPLIT = sb.SPLIT
GRID = (0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5)
MIN_TUNE = 100                 # matches in a bucket before SPLIT to trust a fitted factor
MIN_HELD = 50                  # held-out matches in a bucket before a verdict
BUCKETS = ("first-to-4", "first-to-5-6", "first-to-9+")


def bucket(t: int) -> str:
    return BUCKETS[0] if t <= 4 else BUCKETS[1] if t <= 6 else BUCKETS[2]


def stretch(p: float, s: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    z = s * log(p / (1 - p))
    return 1 / (1 + exp(-z))


def brier(pairs: list[tuple[float, float]], s: float) -> float:
    return sum((stretch(p, s) - y) ** 2 for p, y in pairs) / len(pairs)


def collect(rows: list[dict]) -> dict[str, dict[str, list[tuple[float, float]]]]:
    """{bucket: {'tune': [(p, y)], 'held': [(p, y)]}} from walk-forward Elo, no look-ahead."""
    g = sf.rows_for_study(rows)
    probs = wf.replay(g, ms.ELO_K, ms.MIN_GAMES)
    out: dict[str, dict[str, list]] = {b: {"tune": [], "held": []} for b in BUCKETS}
    for x, p in zip(g, probs, strict=True):
        if p is None:
            continue
        out[bucket(x["t"])]["held" if x["key"][:10] >= SPLIT else "tune"].append((p, x["y"]))
    return out


def fit(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < MIN_TUNE:
        return None
    return min(GRID, key=lambda s: brier(pairs, s))


def run_study(rows: list[dict]) -> dict:
    data = collect(rows)
    res = {}
    for b, d in data.items():
        s = fit(d["tune"])
        held = d["held"]
        ok = s is not None and len(held) >= MIN_HELD
        res[b] = {"tune_n": len(d["tune"]), "held_n": len(held), "s": s,
                  "plain": brier(held, 1.0) if held else None,
                  "cand": brier(held, s) if ok else None}
    return res


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Snooker match-length calibration study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_length_study.py` (framework#340). Record only, a "
         "shadow candidate; no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/snooker_results.py`).", ""])
    res = run_study(rows)
    L += [f"Tuning: matches before {SPLIT} (factor s picked from {list(GRID)} per bucket); held out: {SPLIT} on. "
          f"Tries counted: **{len(GRID) * len(BUCKETS)}**.", "",
          "| Length | Tune n | Held n | s (tuned) | Plain Elo Brier | Stretched Brier | Verdict |",
          "|---|---|---|---|---|---|---|"]
    for b in BUCKETS:
        r = res[b]
        if r["cand"] is None:
            L.append(f"| {b} | {r['tune_n']} | {r['held_n']} | PENDING | "
                     f"{'PENDING' if r['plain'] is None else f'{r['plain']:.4f}'} | PENDING | PENDING (too few) |")
            continue
        v = "helps" if r["cand"] < r["plain"] - 1e-4 else "no better"
        L.append(f"| {b} | {r['tune_n']} | {r['held_n']} | {r['s']} | {r['plain']:.4f} | {r['cand']:.4f} | {v} |")
    L += ["", "## Reading", "",
          "- s above 1 means longer matches are more predictable than the plain Elo says; s of 1.0 means no length "
          "effect. A bucket that does not beat plain Elo on held-out matches stays out.",
          "- Shadow only: the board's chance is not changed. Promotion needs the shadow board's own graded record.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(sb.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
