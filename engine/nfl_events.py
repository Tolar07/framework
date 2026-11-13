"""
NFL EVENTS (framework #588, Event models #9): quarter totals, half totals, team totals. RECORD-ONLY / SHADOW.
Picks nothing, stakes nothing, moves no other number.

Idea: each side's expected regulation points (from team ratings, or from the board's own total and spread) are split over
the four quarters by the SHARES the NFL record shows (home and away have their own set), so a half is the sum of two
quarters and the two sides always add up to the game. Counts use a negative binomial (points come in 3s and 7s, so
they are clumpier than Poisson), one dispersion per kind of event, fitted in backtest/nfl_events_study.py. Re-implemented
from the idea in engine/event_model.py's distributions, not copied; reuses the team-ratings shrink of
engine/baseball_events.py (it works for any number of periods).

It agrees with the framework by construction: the sides' means add up to the game mean, and from_total() keeps the board's
own total and spread (test). Missing inputs read PENDING (HR35); nothing is invented (HR59).
"""
from __future__ import annotations

from engine import event_model as em
from engine.baseball_events import Ratings  # noqa: F401  (points for / against shrink)

# NFL 2019-25 regular season: share of a side's regulation points scored in each quarter (study, NFL_EVENTS_STUDY.md).
SHARE_HOME = (0.197, 0.317, 0.199, 0.286)
SHARE_AWAY = (0.194, 0.306, 0.214, 0.286)
LINES_QUARTER = (6.5, 7.5, 9.5, 10.5)       # both teams' points in one quarter
LINES_HALF = (20.5, 23.5, 26.5)             # both teams' points in a half
LINES_TEAM = (17.5, 20.5, 23.5, 26.5)       # one team's regulation points
DISP_QUARTER = 3.0
DISP_HALF = 3.0
DISP_TEAM = 6.0


def fit_shares(rows: list[dict]) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """Per-quarter share of a side's regulation points, home and away. None (PENDING) with no points."""
    if not rows:
        return None
    h = [sum(r["r"][i][0] for r in rows) for i in range(4)]
    a = [sum(r["r"][i][1] for r in rows) for i in range(4)]
    if not sum(h) or not sum(a):
        return None
    return tuple(x / sum(h) for x in h), tuple(x / sum(a) for x in a)


def predict(mh: float | None, ma: float | None, share_home=SHARE_HOME, share_away=SHARE_AWAY,
            d_q: float = DISP_QUARTER, d_h: float = DISP_HALF, d_t: float = DISP_TEAM) -> dict | None:
    """Event numbers from each side's expected regulation points. None (PENDING) when a mean is missing or not positive."""
    if not mh or not ma or mh <= 0 or ma <= 0:
        return None
    th, ta = sum(share_home), sum(share_away)
    sh, sa = tuple(x / th for x in share_home), tuple(x / ta for x in share_away)
    quarters = []
    for i in range(4):
        h, a = mh * sh[i], ma * sa[i]
        quarters.append({"quarter": i + 1, "home_points": round(h, 3), "away_points": round(a, 3),
                         "over": {str(ln): round(em.over(ln, h + a, d_q), 4) for ln in LINES_QUARTER}})
    halves = []
    for name, (lo, hi) in (("first", (0, 2)), ("second", (2, 4))):
        h, a = mh * sum(sh[lo:hi]), ma * sum(sa[lo:hi])
        halves.append({"half": name, "home_points": round(h, 3), "away_points": round(a, 3),
                       "over": {str(ln): round(em.over(ln, h + a, d_h), 4) for ln in LINES_HALF}})
    return {"shadow": True, "home_points": round(mh, 3), "away_points": round(ma, 3), "quarters": quarters, "halves": halves,
            "team_over": {"home": {str(ln): round(em.over(ln, mh, d_t), 4) for ln in LINES_TEAM},
                          "away": {str(ln): round(em.over(ln, ma, d_t), 4) for ln in LINES_TEAM}}}


def from_total(total: float | None, spread_home: float | None) -> dict | None:
    """Event numbers from the board's own total and home spread (negative = home favoured, e.g. -3.5): the sides are
    (total -/+ spread) / 2, so they add up to the board's total and differ by its spread. None (PENDING) without both,
    or when the spread is larger than the total."""
    if not total or total <= 0 or spread_home is None:
        return None
    return predict((total - spread_home) / 2, (total + spread_home) / 2)
