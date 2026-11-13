"""
BASEBALL EVENTS (framework #587, Event models #8): runs per innings, first five innings, team totals. RECORD-ONLY /
SHADOW. Picks nothing, stakes nothing, moves no other number.

Idea: each side's expected runs over nine innings (from team ratings, or from the board's own win / total numbers) are
split over the innings by the SHARES the MLB record shows (the home side's first inning scores most; its bottom of the 9th least, 5%, because it is often not played),
one set of shares for the home side and one for the away side. First-five-innings and one-inning numbers are sums of
those shares; every count uses a negative binomial (runs come in bunches). Re-implemented from the idea in
engine/event_model.py's distributions, not copied.

It agrees with the framework by construction: the two sides' means add up to the game mean, and from_total() keeps the
board's own total and win edge (test). Missing inputs read PENDING (HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from engine import event_model as em

# MLB 2022-25 regular season, 9,695 games: share of a side's nine-inning runs scored in each inning (study).
SHARE_HOME = (0.131, 0.110, 0.122, 0.116, 0.118, 0.120, 0.114, 0.117, 0.051)
SHARE_AWAY = (0.107, 0.102, 0.116, 0.116, 0.118, 0.114, 0.110, 0.106, 0.112)
LINES_F5 = (3.5, 4.5, 5.5)                     # both teams' runs, innings 1-5
LINES_TEAM = (2.5, 3.5, 4.5)                   # one team's runs in nine innings
LINES_INN = (0.5, 1.5)                         # both teams' runs in one inning
SPLIT_SLOPE = 0.5                              # ASSUMED, not fitted: run-share edge per point of win-chance edge (no priced history here yet)
DISP_GAME = 8.0
DISP_INNING = 1.0                              # one inning's runs clump: Poisson says 64% for a run in inning 1, 50% happen (study)                                # negative binomial dispersion of a side's runs


class Ratings:
    """Runs for and against per team from prior games, summed once so a whole day's games share the work."""

    def __init__(self, hist: list[dict]):
        self.rf: dict[str, list[float]] = {}
        self.ra: dict[str, list[float]] = {}
        hs = as_ = 0.0
        for r in hist:
            h, a = sum(x[0] for x in r["r"]), sum(x[1] for x in r["r"])
            hs += h
            as_ += a
            for team, f, c in ((r["home"], h, a), (r["away"], a, h)):
                v = self.rf.setdefault(team, [0, 0.0])
                v[0] += 1
                v[1] += f
                w = self.ra.setdefault(team, [0, 0.0])
                w[0] += 1
                w[1] += c
        self.n = len(hist)
        if self.n:
            self.lg_h, self.lg_a = hs / self.n, as_ / self.n

    def rates(self, home: str, away: str, k: float = 30.0) -> tuple[float, float] | None:
        """Expected nine-inning (home, away) runs: each team's for / against relative to the league, shrunk to the
        league with weight k games. None (PENDING, HR35) with no history."""
        if not self.n:
            return None
        lg = (self.lg_h + self.lg_a) / 2

        def rel(v: list | None) -> float:
            c, t = (v or [0, 0.0])
            return (t + k * lg) / ((c + k) * lg)

        return (self.lg_h * rel(self.rf.get(home)) * rel(self.ra.get(away)),
                self.lg_a * rel(self.rf.get(away)) * rel(self.ra.get(home)))


def fit_shares(rows: list[dict]) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """Per-inning share of a side's runs, home and away, from recorded games. None (PENDING) with no runs."""
    if not rows:
        return None
    h = [sum(r["r"][i][0] for r in rows) for i in range(9)]
    a = [sum(r["r"][i][1] for r in rows) for i in range(9)]
    if not sum(h) or not sum(a):
        return None
    return tuple(x / sum(h) for x in h), tuple(x / sum(a) for x in a)


def predict(mh: float | None, ma: float | None, share_home=SHARE_HOME, share_away=SHARE_AWAY,
            disp: float = DISP_GAME) -> dict | None:
    """Event numbers from each side's expected nine-inning runs. None (PENDING) when a mean is missing or not
    positive. Innings are Poisson-thin slices of the game mean, the first five and team totals use the dispersion."""
    if not mh or not ma or mh <= 0 or ma <= 0:
        return None
    th, ta = sum(share_home), sum(share_away)                # rounded shares: renormalise so innings add up to the game
    share_home, share_away = tuple(x / th for x in share_home), tuple(x / ta for x in share_away)
    f5h, f5a = mh * sum(share_home[:5]), ma * sum(share_away[:5])
    innings = []
    for i in range(9):
        m = mh * share_home[i] + ma * share_away[i]
        innings.append({"inning": i + 1, "home_runs": round(mh * share_home[i], 4), "away_runs": round(ma * share_away[i], 4),
                        "over": {str(ln): round(em.over(ln, m, DISP_INNING), 4) for ln in LINES_INN},
                        "scoreless": round(1 - em.over(0.5, m, DISP_INNING), 4)})
    return {"shadow": True, "home_runs": round(mh, 4), "away_runs": round(ma, 4),
            "first5": {"home_runs": round(f5h, 4), "away_runs": round(f5a, 4),
                       "over": {str(ln): round(em.over(ln, f5h + f5a, disp * 2), 4) for ln in LINES_F5}},
            "innings": innings,
            "team_over": {"home": {str(ln): round(em.over(ln, mh, disp), 4) for ln in LINES_TEAM},
                          "away": {str(ln): round(em.over(ln, ma, disp), 4) for ln in LINES_TEAM}}}


def from_total(total: float | None, p_home: float | None) -> dict | None:
    """Event numbers from the board's own expected total runs and home win chance: the total is split between the two
    sides by the win chance (SPLIT_SLOPE, an assumption until priced history fits it), so the sides add up to the board's total. None (PENDING) without both."""
    if not total or total <= 0 or p_home is None or not 0 < p_home < 1:
        return None
    edge = 0.5 + (p_home - 0.5) * SPLIT_SLOPE
    return predict(total * edge, total * (1 - edge))
