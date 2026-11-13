"""
VOLLEYBALL EVENTS (framework #591, Event models #12): set totals, set handicap and total points.
RECORD-ONLY / SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: the board's volleyball match-win chance p (Elo) is turned into a best-of-5 set-score ladder with the set-momentum
rule already studied in backtest/volleyball_momentum_study.py (a side wins a set with q, q+m after winning the last
one, q-m after losing it; q is solved so the match chance equals p). Set totals and set handicaps are sums of ladder
cells, so they agree with the board by construction. Total points: the points of a match depend mostly on how many
sets were played (a 5th set is short, to 15), so the chance that points go over a line is the ladder's chance of
3 / 4 / 5 sets mixed with the earlier matches' own point totals for that many sets. Re-implemented from the idea.

Missing history or chance reads PENDING (None, HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from bisect import bisect_right

SCORES = ("3-0", "3-1", "3-2", "2-3", "1-3", "0-3")
MIN_PER_COUNT = 30          # earlier matches needed for a set count before its points are modelled


def score_probs(q: float, m: float) -> dict[str, float]:
    """Best-of-5 score chances for the home side; set-1 chance q, then q+m after a set win, q-m after a loss."""
    out = {k: 0.0 for k in SCORES}

    def walk(h: int, a: int, last: int, w: float) -> None:
        if h == 3 or a == 3:
            out[f"{h}-{a}"] += w
            return
        p = min(max(q + m * last, 0.001), 0.999)
        walk(h + 1, a, 1, w * p)
        walk(h, a + 1, -1, w * (1 - p))
    walk(0, 0, 0, 1.0)
    return out


def solve_q(p: float, m: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        s = score_probs(mid, m)
        lo, hi = (mid, hi) if s["3-0"] + s["3-1"] + s["3-2"] < p else (lo, mid)
    return (lo + hi) / 2


def point_lines(hist: dict[int, list[int]]) -> tuple[float, ...]:
    """Half-lines at the 10/30/50/70/90th percentile of the earlier totals (sorted lists by set count)."""
    pool = sorted(t for v in hist.values() for t in v)
    if len(pool) < 5:
        return ()
    return tuple(sorted({int(pool[min(len(pool) - 1, int(len(pool) * f))]) + 0.5 for f in (0.1, 0.3, 0.5, 0.7, 0.9)}))


def over(vals: list[int], line: float) -> float:
    """Share of the sorted earlier totals above the line (+1/+2 smoothing)."""
    return (len(vals) - bisect_right(vals, int(line)) + 1) / (len(vals) + 2)


def predict(p: float | None, m: float, hist: dict[int, list[int]] | None) -> dict | None:
    """Event numbers for the home side with match-win chance p. hist = {3|4|5: sorted match point totals of earlier
    matches with that many sets}. None (PENDING) for a missing/out-of-range chance; points None while any set count
    has fewer than MIN_PER_COUNT earlier matches."""
    if p is None or not 0.0 < p < 1.0:
        return None
    sc = score_probs(solve_q(p, m), m)
    n_sets = {3: sc["3-0"] + sc["0-3"], 4: sc["3-1"] + sc["1-3"], 5: sc["3-2"] + sc["2-3"]}
    out = {"shadow": True, "match_win": round(sc["3-0"] + sc["3-1"] + sc["3-2"], 4),
           "score": {k: round(v, 4) for k, v in sc.items()},
           "sets_over": {"3.5": round(n_sets[4] + n_sets[5], 4), "4.5": round(n_sets[5], 4)},
           "handicap_cover": {"home -1.5": round(sc["3-0"] + sc["3-1"], 4), "away -1.5": round(sc["0-3"] + sc["1-3"], 4)},
           "points_over": None}
    if hist and all(len(hist.get(n, [])) >= MIN_PER_COUNT for n in (3, 4, 5)):
        out["points_over"] = {str(ln): round(sum(n_sets[n] * over(hist[n], ln) for n in (3, 4, 5)), 4)
                              for ln in point_lines(hist)}
    return out
