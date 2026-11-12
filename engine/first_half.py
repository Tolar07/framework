"""
FIRST-HALF GOALS MODEL (framework #582) - the chance of a goal before half-time and the likely half-time score.
SHADOW ONLY: nothing here picks, stakes or blocks; no bot reads output/first_half/.

The Architect posted two videos on 2026-11-12: a "secret first-half goal filter" (37 of 144 games pass, "hit
75.8%", 90-96% quoted for the top five) and the home sides with the most first-half goals at home (Rapid Vienna
16 in 7, Viking 26 in 13). Check first: a goal comes before half-time in about 70% of games anyway
(backtest/LEAGUE_PROFILE_STUDY.md section C), so a 75.8% filter is little better than every game.

Model (Poisson on half-time goals, like the full-game goals model):
  each team's first-half goals FOR and AGAINST per game, at home and away separately, shrunk to the league's
  first-half rate with SHRINK (50) pseudo-games (a team needs MIN_TEAM games of that venue before its own rate is
  used at all; under that it is the league rate, labelled 'league');
  home lambda = league home rate x (home attack / league home rate) x (away defence / league home rate)
  away lambda = league away rate x (away attack / league away rate) x (home defence / league away rate)
  -> P(1st-half over 0.5), P(over 1.5), P(home scores before the break), the three likeliest half-time scores.

Walk-forward evidence: backtest/FIRST_HALF_STUDY.md (Brier against the league-rate baseline, calibration by
decile, and what a 'filter' of the most confident games really hits).
"""
from __future__ import annotations

import math
from collections import defaultdict

SHRINK = 50.0       # chosen on 2019/20-2022/23 from 6/12/20/30/50 (backtest/FIRST_HALF_STUDY.md); less overconfident
MIN_TEAM = 6
MAX_GOALS = 6


def _pois(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


class FirstHalf:
    """Fit on rows with half-time scores (engine/stats_history.py); predict any league/home/away."""

    def __init__(self, rows: list[dict] | None = None):
        self.lg = defaultdict(lambda: [0, 0.0, 0.0])                 # league -> games, home fh goals, away fh goals
        self.tm = defaultdict(lambda: [0, 0.0, 0.0])                 # (team, 'h'|'a') -> games, for, against
        self.all = [0, 0.0, 0.0]
        for r in rows or []:
            self.add(r)

    def add(self, r: dict) -> None:
        h, a = r.get("hthg"), r.get("htag")
        if h is None or a is None:
            return
        for acc in (self.lg[r["league"]], self.all):
            acc[0] += 1
            acc[1] += h
            acc[2] += a
        th, ta = self.tm[(r["home"], "h")], self.tm[(r["away"], "a")]
        th[0] += 1
        th[1] += h
        th[2] += a
        ta[0] += 1
        ta[1] += a
        ta[2] += h

    def league_rates(self, league: str | None) -> tuple[float, float, int]:
        g = self.lg.get(league) if league else None
        if not g or g[0] < 30:
            g = self.all
        n = max(g[0], 1)
        return max(g[1] / n, 0.05), max(g[2] / n, 0.05), g[0]

    def _team(self, team: str, venue: str, mean_for: float, mean_against: float) -> tuple[float, float, int]:
        t = self.tm.get((team, venue))
        if not t or t[0] < MIN_TEAM:
            return mean_for, mean_against, t[0] if t else 0
        return ((t[1] + SHRINK * mean_for) / (t[0] + SHRINK),
                (t[2] + SHRINK * mean_against) / (t[0] + SHRINK), t[0])

    def lambdas(self, league: str | None, home: str, away: str) -> tuple[float, float, dict]:
        lh, la, n = self.league_rates(league)
        h_for, h_against, hn = self._team(home, "h", lh, la)
        a_for, a_against, an = self._team(away, "a", la, lh)
        lam_h = lh * (h_for / lh) * (a_against / lh)
        lam_a = la * (a_for / la) * (h_against / la)
        basis = {"league_games": n, "home_games": hn, "away_games": an,
                 "home_basis": "team" if hn >= MIN_TEAM else "league",
                 "away_basis": "team" if an >= MIN_TEAM else "league"}
        return lam_h, lam_a, basis

    def predict(self, league: str | None, home: str, away: str) -> dict:
        lam_h, lam_a, basis = self.lambdas(league, home, away)
        grid = {(i, j): _pois(i, lam_h) * _pois(j, lam_a) for i in range(MAX_GOALS) for j in range(MAX_GOALS)}
        tot = sum(grid.values())
        grid = {k: v / tot for k, v in grid.items()}
        top = sorted(grid.items(), key=lambda kv: -kv[1])[:3]
        p0 = grid[(0, 0)]
        p_le1 = p0 + grid[(1, 0)] + grid[(0, 1)]
        return {"lambda": [round(lam_h, 3), round(lam_a, 3)],
                "over05": round(1 - p0, 4), "over15": round(1 - p_le1, 4),
                "home_scores": round(1 - sum(v for (i, _j), v in grid.items() if i == 0), 4),
                "away_scores": round(1 - sum(v for (_i, j), v in grid.items() if j == 0), 4),
                "likely_ht": [{"score": f"{i}-{j}", "p": round(v, 4)} for (i, j), v in top], **basis}

    def league_over05(self, league: str | None) -> float:
        lh, la, _n = self.league_rates(league)
        return 1 - math.exp(-(lh + la))


def top_home(rows: list[dict], min_games: int = MIN_TEAM, top: int = 30) -> list[dict]:
    """Home sides with the most first-half goals per home game (rows of one season / window)."""
    acc: dict[tuple, list] = {}
    for r in rows:
        if r.get("hthg") is None:
            continue
        a = acc.setdefault((r["home"], r["league"]), [0, 0, 0, 0])
        a[0] += 1
        a[1] += r["hthg"]
        a[2] += r["hg"]
        a[3] += r["hg"] > r["ag"]
    out = [{"team": t, "league": lg, "home_games": a[0], "fh_goals": a[1], "fh_per_game": round(a[1] / a[0], 2),
            "goals": a[2], "wins": a[3]}
           for (t, lg), a in acc.items() if a[0] >= min_games]
    out.sort(key=lambda x: (-x["fh_per_game"], -x["goals"]))
    return out[:top]
