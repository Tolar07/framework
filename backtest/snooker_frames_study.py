"""
SNOOKER frame-score model study (framework#340; record-only, a SHADOW candidate, no price in the source).

The board prices only the match winner (Elo). Snooker's other markets are frame handicap and total frames. Here the
walk-forward Elo match-win probability p is turned into a per-frame win chance f by solving
P(win a best-of-n) = p (n read from the match: the winner's frame count is the target, n = 2*target-1), then the
exact frame-score distribution gives P(favourite covers -1.5 frames) and P(total frames over the line). Each is
scored BEFORE the match is learned, against the climatology of the earlier matches (same format) so a model that
only repeats the base rate scores zero. Missing/unplayed formats read PENDING (HR35). No odds history exists, so
this is accuracy, never an edge. Nothing here changes a stake, a bar, a threshold or the live switch.

  python backtest/snooker_frames_study.py     writes backtest/SNOOKER_FRAMES_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import results_walkforward as wf  # noqa: E402
from backtest import snooker_backtest as sb  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "SNOOKER_FRAMES_STUDY.md"
SPLIT = sb.SPLIT
MIN_FORMAT = 150          # a format (target frames) needs this many earlier matches for a climatology


def score_probs(f: float, t: int) -> dict[tuple[int, int], float]:
    """P(final frames (a, b)) for a first-to-t match when a wins each frame with chance f."""
    out: dict[tuple[int, int], float] = {}
    for lose in range(t):
        out[(t, lose)] = comb(t - 1 + lose, lose) * f**t * (1 - f)**lose
        out[(lose, t)] = comb(t - 1 + lose, lose) * (1 - f)**t * f**lose
    return out


def win_prob(f: float, t: int) -> float:
    return sum(p for (a, b), p in score_probs(f, t).items() if a == t)


def solve_f(p: float, t: int) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if win_prob(mid, t) < p else (lo, mid)
    return (lo + hi) / 2


def markets(f: float, t: int, line: float) -> tuple[float, float]:
    """(P(side a wins by 2+ frames), P(total frames > line))."""
    sp = score_probs(f, t)
    return (sum(p for (a, b), p in sp.items() if a - b >= 2),
            sum(p for (a, b), p in sp.items() if a + b > line))


def rows_for_study(rows: list[dict]) -> list[dict]:
    out = []
    for r in sorted(rows, key=lambda x: x["kickoff_utc"]):
        h, a = ms.norm(r["home"]), ms.norm(r["away"])
        hf, af = r.get("home_frames"), r.get("away_frames")
        if not h or not a or h == a or hf is None or af is None or hf == af:
            continue
        t = max(hf, af)
        first = h < a
        fa, fb = (hf, af) if first else (af, hf)
        out.append({"key": r["kickoff_utc"], "a": min(h, a), "b": max(h, a), "t": t, "fa": fa, "fb": fb,
                    "y": 1.0 if fa > fb else 0.0})
    return out


def run_study(rows: list[dict]) -> dict:
    g = rows_for_study(rows)
    probs = wf.replay(g, ms.ELO_K, ms.MIN_GAMES)
    hist: dict[int, list[dict]] = {}
    acc = {"n": 0, "m": 0.0, "c": 0.0, "mt": 0.0, "ct": 0.0, "mf": 0.0, "cf": 0.0, "fmt": {}}
    for x, p in zip(g, probs):
        h = hist.setdefault(x["t"], [])
        if p is not None and x["key"][:10] >= SPLIT and len(h) >= MIN_FORMAT and x["t"] >= 4:
            tot = sorted(m["fa"] + m["fb"] for m in h)
            line = tot[len(tot) // 2] - 0.5            # earlier median total, as a half-line
            f = solve_f(min(max(p, 0.02), 0.98), x["t"])
            # side a = the Elo favourite; flip when a is the underdog
            fav_a = p >= 0.5
            cov_m, over_m = markets(f if fav_a else 1 - f, x["t"], line)
            win_fav = (x["fa"] - x["fb"] >= 2) if fav_a else (x["fb"] - x["fa"] >= 2)
            over = (x["fa"] + x["fb"]) > line
            base_over = sum(1 for m in h if m["fa"] + m["fb"] > line) / len(h)
            base_fav = sum(1 for m in h if abs(m["fa"] - m["fb"]) >= 2) / len(h) * 0.6
            acc["n"] += 1
            acc["m"] += (cov_m - win_fav) ** 2
            acc["c"] += (base_fav - win_fav) ** 2
            acc["mt"] += (over_m - over) ** 2
            acc["ct"] += (base_over - over) ** 2
            # expected-frame-margin error of the favourite, model vs "winner by 0"
            em = sum((a - b) * pr for (a, b), pr in score_probs(f if fav_a else 1 - f, x["t"]).items())
            am = (x["fa"] - x["fb"]) if fav_a else (x["fb"] - x["fa"])
            acc["mf"] += abs(em - am)
            acc["cf"] += abs(am)
            acc["fmt"][x["t"]] = acc["fmt"].get(x["t"], 0) + 1
        h.append(x)
    return acc


def render(rows: list[dict], now: datetime) -> str:
    L = ["# Snooker frame-score model study", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_frames_study.py` (framework#340). Record only, "
         "a shadow candidate; no price in the source, so accuracy not edge.", ""]
    if not rows:
        return "\n".join(L + ["NO DATA - PENDING (run `python data/snooker_results.py`).", ""])
    a = run_study(rows)
    if not a["n"]:
        return "\n".join(L + ["No held-out match in a format with enough history - PENDING.", ""])
    n = a["n"]
    L += [f"Held-out matches ({SPLIT} on, formats first-to-4 or longer with {MIN_FORMAT}+ earlier matches): **{n}**. "
          f"By target frames: " + ", ".join(f"first-to-{k}: {v}" for k, v in sorted(a["fmt"].items())) + ".", "",
          "| Test | Frame model Brier | Base-rate Brier |", "|---|---|---|",
          f"| Favourite wins by 2+ frames | {a['m'] / n:.4f} | {a['c'] / n:.4f} |",
          f"| Total frames over the earlier median line | {a['mt'] / n:.4f} | {a['ct'] / n:.4f} |", "",
          f"Mean absolute error of the favourite's frame margin: model expectation {a['mf'] / n:.2f} frames, "
          f"naive 'margin 0' {a['cf'] / n:.2f} frames.", "",
          "## Reading", "",
          "- Elo gives a match probability; the best-of-n frame ladder turns it into a frame handicap and total. "
          "The base rate is the earlier share for the same format (favourite cover uses 0.6x the margin>=2 rate, a "
          "fixed anchor, no fitting).",
          "- Lower Brier than the base rate means the ladder adds information; if not, the board keeps pricing the "
          "winner only. Every try is counted: one line, one anchor, no tuning.",
          "- Record only: nothing here changes a stake, a bar, a threshold or the live switch.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    text = render(sb.load(), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
