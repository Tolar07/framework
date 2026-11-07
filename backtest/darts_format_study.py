"""
DARTS format shadow (framework#341; record-only).

No free dated PDC results feed exists in the repo, so this is a pure format table, not a backtest: no result is invented
(HR59). It turns a per-leg strength edge into the chance of winning a set (first to N legs) and a match (first to M sets,
or first to K legs when there are no sets), with the throw alternating each leg (darts throw-first advantage), and the
inverse solves the edge that reproduces a given match price so a shadow board can price correct-score and total-legs
markets from the match price. The throw-first hold chance HOLD (equal players) is an assumption, PENDING a grade on the
shadow board (HR35). Nothing here changes a pick, stake, bar or live switch.

  python backtest/darts_format_study.py      writes backtest/DARTS_FORMAT_STUDY.md
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "backtest" / "DARTS_FORMAT_STUDY.md"
HOLD = 0.60  # assumed chance the player throwing first wins the leg, equal players (PENDING a grade)


def leg_chances(edge: float, hold: float = HOLD) -> tuple[float, float]:
    """(A wins a leg when A throws first, A wins a leg when B throws first); edge shifts both in A's favour."""
    if not 0.0 < hold < 1.0:
        raise ValueError("hold must be in (0, 1)")
    a_first = min(1.0, max(0.0, hold + edge))
    a_second = min(1.0, max(0.0, (1.0 - hold) + edge))
    return a_first, a_second


def _race(need: int, a_throws: bool, pa: tuple[float, float]) -> dict[tuple[int, int], float]:
    """Distribution of final (A legs, B legs) in a race to `need` with the throw alternating every leg."""
    @lru_cache(maxsize=None)
    def go(a: int, b: int, a_th: bool) -> tuple[tuple[tuple[int, int], float], ...]:
        if a == need or b == need:
            return (((a, b), 1.0),)
        p = pa[0] if a_th else pa[1]
        out: dict[tuple[int, int], float] = {}
        for k, v in go(a + 1, b, not a_th):
            out[k] = out.get(k, 0.0) + p * v
        for k, v in go(a, b + 1, not a_th):
            out[k] = out.get(k, 0.0) + (1.0 - p) * v
        return tuple(out.items())
    return dict(go(0, 0, a_throws))


def leg_match(edge: float, legs: int, hold: float = HOLD) -> dict[tuple[int, int], float]:
    """Legs-only match (first to `legs`): final-score distribution, averaged over who throws first (bull-up)."""
    pa = leg_chances(edge, hold)
    out: dict[tuple[int, int], float] = {}
    for first in (True, False):
        for k, v in _race(legs, first, pa).items():
            out[k] = out.get(k, 0.0) + 0.5 * v
    return out


def set_win(edge: float, legs: int, a_throws: bool, hold: float = HOLD) -> float:
    pa = leg_chances(edge, hold)
    return sum(v for (a, _b), v in _race(legs, a_throws, pa).items() if a == legs)


def set_match(edge: float, legs: int, sets: int, hold: float = HOLD) -> float:
    """Match-win chance, first to `sets` sets of first-to-`legs`; the set starter alternates every set."""
    s_first, s_second = set_win(edge, legs, True, hold), set_win(edge, legs, False, hold)

    @lru_cache(maxsize=None)
    def go(a: int, b: int, a_th: bool) -> float:
        if a == sets:
            return 1.0
        if b == sets:
            return 0.0
        p = s_first if a_th else s_second
        return p * go(a + 1, b, not a_th) + (1.0 - p) * go(a, b + 1, not a_th)
    return 0.5 * go(0, 0, True) + 0.5 * go(0, 0, False)


def leg_match_win(edge: float, legs: int, hold: float = HOLD) -> float:
    return sum(v for (a, _b), v in leg_match(edge, legs, hold).items() if a == legs)


def total_legs_over(dist: dict[tuple[int, int], float], line: float) -> float:
    return sum(v for (a, b), v in dist.items() if a + b > line)


def _solve(fn, match_p: float, hold: float) -> float | None:
    """Edge whose match chance equals match_p (bisection; fn increases with the edge). None outside (0, 1)."""
    if not 0.0 < match_p < 1.0:
        return None
    lo, hi = -hold, 1.0 - hold
    if fn(lo) > match_p or fn(hi) < match_p:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if fn(mid) < match_p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def price_legs(match_p: float, legs: int, hold: float = HOLD) -> dict | None:
    """Correct-score and total-legs chances implied by a match-win chance, legs-only match (the shadow-board hook)."""
    e = _solve(lambda x: leg_match_win(x, legs, hold), match_p, hold)
    if e is None:
        return None
    d = leg_match(e, legs, hold)
    lines = [float(legs) + 0.5 + i for i in range(legs - 1)]
    return {"edge": e, "scores": d, "over": {ln: total_legs_over(d, ln) for ln in lines}}


def price_sets(match_p: float, legs: int, sets: int, hold: float = HOLD) -> float | None:
    """Average per-leg chance that reproduces a set-match price (PENDING None when out of range)."""
    e = _solve(lambda x: set_match(x, legs, sets, hold), match_p, hold)
    if e is None:
        return None
    return sum(leg_chances(e, hold)) / 2


def run() -> str:
    made = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Darts format shadow", "",
         f"Made {made} by `backtest/darts_format_study.py` (framework#341). Record only.", "",
         f"A pure format table (no PDC results data exists to backtest on, HR35/HR59): per-leg edge -> set / match. The "
         f"throw alternates every leg and the player throwing first wins {HOLD:.0%} of legs between equals (an assumption, "
         "PENDING a grade on the shadow board).", "",
         "## Edge -> match chance", "",
         "| Leg edge | Leg chance (avg) | First to 6 legs | First to 10 legs | First to 3 sets of 3 | First to 4 sets of 3 |",
         "|---|---|---|---|---|---|"]
    for e in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        L.append(f"| {e:+.0%} | {sum(leg_chances(e)) / 2:.1%} | {leg_match_win(e, 6):.1%} | {leg_match_win(e, 10):.1%} | "
                 f"{set_match(e, 3, 3):.1%} | {set_match(e, 3, 4):.1%} |")
    L += ["", "## First-to-6-legs prices implied by a match chance", "",
          "| Match chance | Leg edge | 6-0 | 6-3 | 6-5 | Over 9.5 legs | Over 10.5 legs |", "|---|---|---|---|---|---|---|"]
    for m in (0.50, 0.60, 0.70, 0.80, 0.90):
        p = price_legs(m, 6)
        s = p["scores"]
        L.append(f"| {m:.0%} | {p['edge']:+.1%} | {s[(6, 0)]:.1%} | {s[(6, 3)]:.1%} | {s[(6, 5)]:.1%} | "
                 f"{p['over'][9.5]:.1%} | {p['over'][10.5]:.1%} |")
    L += ["", "(Scores are the first player's wins averaged over who throws first; mirror scores are in `price_legs()`.)", "",
          "## Reading", "",
          "- A small per-leg edge compounds, and longer matches (more legs / sets) lift the favourite's match chance.",
          "- Method: a YouTube search on 2026-11-07 for darts prediction-model method videos found only technique and "
          "highlight clips (none teaching a model), so nothing was taken from video; the format maths is standard race "
          "arithmetic.",
          "- Next (needs a results feed, PENDING): grade the throw-first hold chance and the independent-leg assumption on "
          "shadow-board results before any of this is trusted.",
          "- Record only: nothing here changes a stake, a bar or the live switch."]
    return "\n".join(L) + "\n"


def main() -> None:
    OUT.write_text(run(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
