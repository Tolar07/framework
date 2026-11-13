"""
SNOOKER EVENTS (framework #590, Event models #11): exact frame score (correct score), total frames and frame handicap.
Centuries are PENDING. RECORD-ONLY / SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: the board's snooker match-win chance p (Elo) is turned into a per-frame win chance f by solving
P(win a first-to-t match) = p, then the frame score is the exact negative-binomial ladder at f. Every event number is a
sum over that one ladder, so they agree with the board by construction: the win chance of the ladder IS p (test), the
score probabilities add to 1, and the totals and handicaps are sums of score cells. Re-implemented from the idea, not copied.

Centuries need a per-frame break record (cuetracker.net / snooker.org); none is stored in the framework, so they read
PENDING (HR35) and nothing is invented (HR59).
"""
from __future__ import annotations

from math import comb


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
    """Per-frame win chance whose first-to-t match-win chance is p (bisection)."""
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if win_prob(mid, t) < p else (lo, mid)
    return (lo + hi) / 2


def total_lines(t: int) -> tuple[float, ...]:
    """Every total-frames half-line the format can settle: t+0.5 .. 2t-1.5 (totals run t .. 2t-1)."""
    return tuple(k + 0.5 for k in range(t, 2 * t - 1))


def predict(p: float | None, t: int | None) -> dict | None:
    """Event numbers for side a (the one p is for) in a first-to-t match. None (PENDING, HR35) for a missing or
    out-of-range chance or a format shorter than first-to-2."""
    if p is None or t is None or t < 2 or not 0.0 < p < 1.0:
        return None
    f = solve_f(p, t)
    sp = score_probs(f, t)
    return {"shadow": True, "target": t, "frame_win": round(f, 4), "match_win": round(win_prob(f, t), 4),
            "score": {f"{a}-{b}": round(q, 4) for (a, b), q in sorted(sp.items(), key=lambda kv: (-kv[0][0], kv[0][1]))},
            "total_over": {str(ln): round(sum(q for (a, b), q in sp.items() if a + b > ln), 4) for ln in total_lines(t)},
            "handicap_cover": {str(h): round(sum(q for (a, b), q in sp.items() if a - b > h), 4) for h in (-1.5, 1.5, 2.5)},
            "centuries": None}      # PENDING: no per-frame break record is stored
