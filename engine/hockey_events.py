"""
ICE HOCKEY EVENTS (framework #586, Event models #7): goals and shots per period, team totals. RECORD-ONLY / SHADOW.
Picks nothing, stakes nothing, moves no other number.

Idea: the game's two goal rates (home, away) are split over the three periods by the SHARES the NHL's own
per-period record shows (period 1 scores least; refitted in backtest/hockey_events_study.py), and shots on goal follow
the same split with their own shares. Re-implemented from the idea in engine/hockey_periods.py, not copied.

It agrees with the framework by construction: the two rates come either from the framework's own regulation win /
draw prices (hockey_periods.solve_rates, so P(home win after 60 min) equals the board's) or from team ratings; the
per-period means always add up to the game mean (test). Missing inputs read PENDING (HR35); nothing is invented (HR59).
"""
from __future__ import annotations

import math

from engine import hockey_periods as hp

SHARE_GOALS = (0.294, 0.348, 0.358)            # NHL regulation goals by period, 5,248 games 2022-26 (study); hockey_periods assumed 0.31 for P1
SHARE_SHOTS = (0.327, 0.350, 0.323)            # NHL shots on goal by period, same games
LINES_PERIOD = (0.5, 1.5, 2.5)                 # total goals in one period, both teams
LINES_TEAM = (1.5, 2.5, 3.5)                   # one team's goals in regulation


def pois_over(line: float, mean: float) -> float:
    """P(X > line) for a half line, Poisson."""
    k = int(math.floor(line))
    p, c = math.exp(-mean), 0.0
    for i in range(k + 1):
        c += p
        p = p * mean / (i + 1)
    return max(0.0, min(1.0, 1.0 - c))


class Ratings:
    """Goals (key="g") or shots on goal (key="s") for and against per team, summed once from prior games so one
    matchday's games share the work."""

    def __init__(self, hist: list[dict], key: str = "g"):
        self.gf: dict[str, list[float]] = {}
        self.ga: dict[str, list[float]] = {}
        hs = as_ = 0.0
        for r in hist:
            h, a = sum(x[0] for x in r[key]), sum(x[1] for x in r[key])
            hs += h
            as_ += a
            for team, f, c in ((r["home"], h, a), (r["away"], a, h)):
                v = self.gf.setdefault(team, [0, 0.0])
                v[0] += 1
                v[1] += f
                w = self.ga.setdefault(team, [0, 0.0])
                w[0] += 1
                w[1] += c
        self.n = len(hist)
        if self.n:
            self.lg_h, self.lg_a = hs / self.n, as_ / self.n

    def rates(self, home: str, away: str, k: float = 20.0) -> tuple[float, float] | None:
        """Expected (home, away) values: each team's for / against relative to the league, shrunk to the league
        with weight k games. None (PENDING, HR35) with no history."""
        if not self.n:
            return None
        lg = (self.lg_h + self.lg_a) / 2

        def rel(v: list | None) -> float:
            c, t = (v or [0, 0.0])
            return (t + k * lg) / ((c + k) * lg)

        return (self.lg_h * rel(self.gf.get(home)) * rel(self.ga.get(away)),
                self.lg_a * rel(self.gf.get(away)) * rel(self.ga.get(home)))


def team_rates(hist: list[dict], home: str, away: str, k: float = 20.0, key: str = "g") -> tuple[float, float] | None:
    """Expected regulation goals (home, away; key="s" for shots on goal) from prior games only."""
    return Ratings(hist, key).rates(home, away, k)


def predict(lh: float | None, la: float | None, sh: float | None = None, sa: float | None = None,
            share_goals=SHARE_GOALS, share_shots=SHARE_SHOTS) -> dict | None:
    """Per-period and team event numbers from the game goal rates (lh, la) and, optionally, expected game shots on
    goal (sh, sa). None (PENDING) when a rate is missing or not positive."""
    if not lh or not la or lh <= 0 or la <= 0:
        return None
    periods = []
    for n, g in enumerate(share_goals, 1):
        mh, ma = lh * g, la * g
        row = {"period": n, "home_goals": round(mh, 4), "away_goals": round(ma, 4),
               "over": {str(ln): round(pois_over(ln, mh + ma), 4) for ln in LINES_PERIOD},
               "scoreless": round(math.exp(-(mh + ma)), 4)}
        if sh and sa:
            row["home_shots"] = round(sh * share_shots[n - 1], 3)
            row["away_shots"] = round(sa * share_shots[n - 1], 3)
        periods.append(row)
    return {"shadow": True, "home_goals": round(lh, 4), "away_goals": round(la, 4), "periods": periods,
            "team_over": {"home": {str(ln): round(pois_over(ln, lh), 4) for ln in LINES_TEAM},
                          "away": {str(ln): round(pois_over(ln, la), 4) for ln in LINES_TEAM}}}


def from_board(price_home: float | None, price_draw: float | None, price_away: float | None) -> dict | None:
    """Event numbers from the regulation (60 minute) 1X2 prices: the same rates the framework's period split uses, so
    the event model and the board agree. None (PENDING) without all three prices."""
    if not (price_home and price_draw and price_away) or min(price_home, price_draw, price_away) <= 1:
        return None
    ph, pd, pa = hp.devig(price_home, price_draw, price_away)
    lh, la = hp.solve_rates(ph, pa, pd)
    return predict(lh, la)


def fit_shares(rows: list[dict]) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    """Period shares of goals and of shots from recorded games. None (PENDING) when there are no games."""
    if not rows:
        return None
    g = [sum(r["g"][i][0] + r["g"][i][1] for r in rows) for i in range(3)]
    s = [sum(r["s"][i][0] + r["s"][i][1] for r in rows) for i in range(3)]
    if not sum(g) or not sum(s):
        return None
    return tuple(x / sum(g) for x in g), tuple(x / sum(s) for x in s)
