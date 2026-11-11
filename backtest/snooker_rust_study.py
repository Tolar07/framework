"""
SNOOKER LAYOFF ("RUST") STUDY (framework#340; record-only, a SHADOW candidate, results only).

Does a long gap since a player's last match make the Elo chance less reliable? For each match the longer layoff of the
two players (days since each one's previous match in the results file, known BEFORE the match) is bucketed. Per
bucket we ask whether stretching/shrinking the walk-forward Elo log-odds by a factor s improves the Brier score. s is
chosen on matches before SPLIT only, from a fixed grid; held-out matches (SPLIT on) are then scored with the frozen s
beside plain Elo. Tries counted = grid size x buckets. No price in the source, so accuracy, never an edge. Thin
buckets read PENDING (HR35). Nothing here changes a pick rule, a stake, a bar or the live switch.

  python backtest/snooker_rust_study.py     writes backtest/SNOOKER_RUST_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from backtest import snooker_backtest as sb  # noqa: E402
from backtest import snooker_frames_study as sf  # noqa: E402
from backtest import snooker_length_study as sl  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "SNOOKER_RUST_STUDY.md"
SPLIT = sb.SPLIT
GRID = (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2)
MIN_TUNE = 100
MIN_HELD = 50
BUCKETS = ("layoff<=30d", "layoff 31-90d", "layoff>90d", "first match seen")


def bucket(days: int | None) -> str:
    if days is None:
        return BUCKETS[3]
    return BUCKETS[0] if days <= 30 else BUCKETS[1] if days <= 90 else BUCKETS[2]


def layoff(last: dict[str, str], a: str, b: str, day: str) -> int | None:
    """Longer gap in days (either player's previous match); None when either has no earlier match."""
    if a not in last or b not in last:
        return None
    d = date.fromisoformat(day)
    return max((d - date.fromisoformat(last[a])).days, (d - date.fromisoformat(last[b])).days)


def collect(rows: list[dict]) -> dict[str, dict[str, list[tuple[float, float]]]]:
    g = sf.rows_for_study(rows)
    probs = wf.replay(g, ms.ELO_K, ms.MIN_GAMES)
    out = {b: {"tune": [], "held": []} for b in BUCKETS}
    last: dict[str, str] = {}
    for x, p in zip(g, probs, strict=True):
        day = x["key"][:10]
        bk = bucket(layoff(last, x["a"], x["b"], day))
        last[x["a"]] = last[x["b"]] = day          # learned only after the match is bucketed
        if p is not None:
            out[bk]["held" if day >= SPLIT else "tune"].append((p, x["y"]))
    return out


def fit(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < MIN_TUNE:
        return None
    return min(GRID, key=lambda s: sl.brier(pairs, s))


def run_study(rows: list[dict]) -> dict:
    res = {}
    for b, d in collect(rows).items():
        s = fit(d["tune"])
        held = d["held"]
        ok = s is not None and len(held) >= MIN_HELD
        res[b] = {"tune_n": len(d["tune"]), "held_n": len(held), "s": s,
                  "plain": sl.brier(held, 1.0) if held else None,
                  "cand": sl.brier(held, s) if ok else None}
    return res


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Snooker layoff (rust) study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_rust_study.py` (framework#340). Record only, a "
         "shadow candidate; no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/snooker_results.py`).", ""])
    res = run_study(rows)
    L += [f"Tuning: matches before {SPLIT} (factor s picked from {list(GRID)} per bucket); held out: {SPLIT} on. "
          f"Tries counted: **{len(GRID) * len(BUCKETS)}**.", "",
          "| Layoff (longer of the two players) | Tune n | Held n | s (tuned) | Plain Elo Brier | Adjusted Brier | Verdict |",
          "|---|---|---|---|---|---|---|"]
    for b in BUCKETS:
        r = res[b]
        plain = "PENDING" if r["plain"] is None else f"{r['plain']:.4f}"
        if r["cand"] is None:
            L.append(f"| {b} | {r['tune_n']} | {r['held_n']} | PENDING | {plain} | PENDING | PENDING (too few) |")
            continue
        v = "helps" if r["cand"] < r["plain"] - 1e-4 else "no better"
        L.append(f"| {b} | {r['tune_n']} | {r['held_n']} | {r['s']} | {plain} | {r['cand']:.4f} | {v} |")
    L += ["", "## Reading", "",
          "- s below 1 means the Elo chance is overconfident after a long layoff; 1.0 means no layoff effect. A bucket "
          "that does not beat plain Elo on held-out matches stays out.",
          "- Shadow only: the board's chance is not changed. Promotion needs the shadow board's own graded record.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(sb.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
