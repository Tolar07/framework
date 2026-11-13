"""
TABLE TENNIS EVENTS (framework #594, Event models #15): game score, total games and total points.
RECORD-ONLY / SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: the board's table tennis match-win chance p (Elo) becomes a best-of-5 game-score ladder with a momentum rule (a
player wins a game with q, q+m after winning the last one, q-m after losing it; q is solved so the match chance equals
p). Game totals and handicaps are sums of ladder cells, so they agree with the board by construction. Total points depend
mostly on how many games were played, so the chance that points go over a line is the ladder's chance of 3 / 4 / 5 games
mixed with the earlier matches' point totals for that many games. The ladder is the same best-of-5 maths as
engine/volleyball_events.py and is reused from it; only best-of-5 is modelled (best-of-7 PENDING: no data).

Missing history or chance reads PENDING (None, HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from engine import volleyball_events as _ladder

SCORES = _ladder.SCORES
MIN_PER_COUNT = _ladder.MIN_PER_COUNT
score_probs = _ladder.score_probs
solve_q = _ladder.solve_q
point_lines = _ladder.point_lines
over = _ladder.over


def predict(p: float | None, m: float, hist: dict[int, list[int]] | None) -> dict | None:
    """Event numbers for the home player with match-win chance p. hist = {3|4|5: sorted point totals of earlier matches
    with that many games}. None (PENDING) for a missing/out-of-range chance; points None while any game count has
    fewer than MIN_PER_COUNT earlier matches."""
    r = _ladder.predict(p, m, hist)
    if r is None:
        return None
    r["games_over"] = r.pop("sets_over")
    return r
