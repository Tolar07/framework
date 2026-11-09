"""MLB starting-pitcher model (framework#382; SHADOW / record-only).

Idea (practitioner videos, see .claude/skills/multisport-markets): the First-5-innings (F5) result is decided by the two
starters and the top of the line-ups; the bullpen barely matters. A full game is the starter for the innings he lasts,
the league-average pen for the rest. Re-implemented from the idea, nothing copied.

Everything is walk-forward: a game's inputs use only games finished BEFORE it. A starter's rating is his opponents'
first-five-innings runs per start (a proxy for runs allowed while he pitches), exponentially weighted and shrunk
towards the league mean; a team's offence is its own F5 runs, same treatment. Missing starter -> league-average
starter (flagged), never invented (HR35). Nothing here changes a pick rule, stake, bar or live switch.
"""
from __future__ import annotations

import math
from collections import defaultdict

F5 = 5
INNINGS = 9


def pois_pmf(lam: float, n: int = 25) -> list[float]:
    p = [math.exp(-lam)]
    for i in range(1, n):
        p.append(p[-1] * lam / i)
    return p


def win_prob(lam_a: float, lam_b: float, tie_to_a: float = 0.5) -> tuple[float, float]:
    """(P side a wins, P tie) for two independent Poisson run counts; ties are returned separately."""
    pa, pb = pois_pmf(lam_a), pois_pmf(lam_b)
    win = tie = 0.0
    for i, x in enumerate(pa):
        for j, y in enumerate(pb):
            if i > j:
                win += x * y
            elif i == j:
                tie += x * y
    return win, tie


class Ratings:
    """Walk-forward starter + offence ratings. Call `predict` BEFORE `update` for each game."""

    def __init__(self, shrink: float = 8.0, decay: float = 0.97, home_f: float = 1.04):
        self.shrink, self.decay, self.home_f = shrink, decay, home_f
        self.sp = defaultdict(lambda: [0.0, 0.0])    # starter id -> [weighted F5 runs allowed, weighted starts]
        self.off = defaultdict(lambda: [0.0, 0.0])   # team -> [weighted F5 runs scored, weighted games]
        self.lg = [0.0, 0.0]                         # league F5 runs per team-game

    def league(self) -> float:
        return self.lg[0] / self.lg[1] if self.lg[1] > 20 else 2.4

    def _rel(self, store, key) -> float:
        """Runs relative to league, shrunk towards 1.0 by `shrink` pseudo-games."""
        s, n = store[key]
        lg = self.league()
        return (s + self.shrink * lg) / ((n + self.shrink) * lg)

    def sp_factor(self, pid) -> float:
        return 1.0 if pid is None else self._rel(self.sp, pid)

    def predict(self, g: dict) -> dict | None:
        """g: a (visitor), b (home), spa, spb (starter ids or None). Returns F5 and full-game chances that a wins
        (PENDING = None until the league has a sample)."""
        if self.lg[1] < 400:
            return None
        lg = self.league()
        la5 = lg * self._rel(self.off, g["a"]) * self.sp_factor(g["spb"]) / self.home_f ** 0.5
        lb5 = lg * self._rel(self.off, g["b"]) * self.sp_factor(g["spa"]) * self.home_f ** 0.5
        w5, t5 = win_prob(la5, lb5)
        # full game: starter-adjusted first five, then the league-rate pen for the last four (offence kept)
        rest = lg * (INNINGS - F5) / F5
        la9 = la5 + rest * self._rel(self.off, g["a"]) / self.home_f ** 0.5
        lb9 = lb5 + rest * self._rel(self.off, g["b"]) * self.home_f ** 0.5
        w9, t9 = win_prob(la9, lb9)
        return {"f5_a": w5 + 0.5 * t5, "f5_tie": t5, "full_a": w9 + 0.5 * t9,
                "missing_sp": g["spa"] is None or g["spb"] is None}

    def update(self, g: dict) -> None:
        """g also carries f5a / f5b: runs each side scored in innings 1-5 (None if the linescore is short)."""
        if g.get("f5a") is None or g.get("f5b") is None:
            return
        d = self.decay
        for store, key, val in ((self.off, g["a"], g["f5a"]), (self.off, g["b"], g["f5b"]),
                                (self.sp, g["spb"], g["f5a"]), (self.sp, g["spa"], g["f5b"])):
            if key is None:
                continue
            s, n = store[key]
            store[key] = [s * d + val, n * d + 1.0]
        self.lg = [self.lg[0] + g["f5a"] + g["f5b"], self.lg[1] + 2.0]
