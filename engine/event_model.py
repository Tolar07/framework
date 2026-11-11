"""
Football match events: cards, red card, fouls, corners, shots, shots on target (framework #555). RECORD-ONLY.

Architect 2026-11-11: "I need to see all the predictions ... number of cards, numbers of fouls ... a possible red
card ... shots on target ... it needs to agree with the framework and the models." This predicts, for every rated
fixture, each team's count of each event with a full distribution, the totals at the usual SportyBet lines, and the
chance of at least one red card. It picks nothing, stakes nothing and moves no other number (shadow).

How (backtest/EVENT_MODEL_STUDY.md has the evidence):
- History: data/match_stats/<month>.jsonl (FotMob post-match stats of every rated fixture, monitor/universe_sweep.py).
- Each team's rate FOR and AGAINST per event, shrunk to its league's mean with SHRINK pseudo-matches, as a multiplier
  on the league's home or away mean: mu_home = league_home_mean * attack(home) * concede(away). The usual
  attack-defence form of the goals model, applied to other events.
- Spread: negative binomial per event, dispersion from the league's history (method of moments, never below Poisson).
- Red card: Poisson on both teams' red rates; reported as the chance of at least one.
- **Agrees with the framework's goals model:** shots and shots on target are also read off the model's own expected
  goals for the game (the Dixon-Coles score table on the board): the league's shots-on-target per expected goal times
  the model's xG. The two estimates are averaged (ANCHOR weight); `tests/event_model_test.py` checks that the result
  implies a goals-per-shot-on-target inside the range the leagues actually show.
- Teams: board names are paired with FotMob names inside the same league by engine/fixture_match.team_score: STRONG,
  and no other club in the league matches even weakly; an unpaired team falls back to the league mean (shown).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from engine import fixture_match as fm

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "data" / "match_stats"
EVENTS = ("yellow", "fouls", "corners", "shots", "sot", "red")
SHRINK = 6.0           # pseudo-matches at the league mean behind every team rate
MIN_LEAGUE = 12        # fewer matches than this in a league: use all leagues pooled
ANCHOR = 0.5           # weight of the expected-goals reading in shots and shots on target
LINES = {"yellow": (2.5, 3.5, 4.5, 5.5), "fouls": (20.5, 22.5, 24.5), "corners": (7.5, 8.5, 9.5, 10.5, 11.5),
         "shots": (20.5, 23.5, 26.5), "sot": (6.5, 7.5, 8.5, 9.5)}
TEAM_LINES = {"yellow": (0.5, 1.5, 2.5), "corners": (3.5, 4.5, 5.5), "sot": (2.5, 3.5, 4.5)}
LABEL = {"yellow": "Yellow cards", "fouls": "Fouls", "corners": "Corners", "shots": "Shots", "sot": "Shots on target",
         "red": "Red card"}


def load_history(paths: Iterable[Path] | None = None) -> list[dict]:
    """Every saved match with its stats, oldest first. Matches missing a stat simply don't count for it."""
    rows = []
    for p in sorted(paths if paths is not None else STATS_DIR.glob("*.jsonl")):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("stats") and r.get("home") and r.get("away") and r.get("date"):
                    rows.append(r)
    rows.sort(key=lambda r: r["date"])
    return rows


# ---------------------------------------------------------------- distributions

def nb_pmf(k: int, mean: float, disp: float) -> float:
    """Negative binomial P(X=k) with variance mean + mean^2/disp; disp=inf is Poisson."""
    mean = max(mean, 1e-9)
    if not math.isfinite(disp) or disp > 1e6:
        return math.exp(k * math.log(mean) - mean - math.lgamma(k + 1))
    p = disp / (disp + mean)
    return math.exp(math.lgamma(k + disp) - math.lgamma(disp) - math.lgamma(k + 1) + disp * math.log(p) + k * math.log1p(-p))


def over(line: float, mean: float, disp: float) -> float:
    """P(X > line) for a half line."""
    return max(0.0, min(1.0, 1.0 - sum(nb_pmf(k, mean, disp) for k in range(int(math.floor(line)) + 1))))


def _disp(values: list[float]) -> float:
    if len(values) < 8:
        return math.inf
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.inf if v <= m * 1.02 else max(m * m / (v - m), 0.5)


# ---------------------------------------------------------------- the model

@dataclass
class League:
    n: int = 0
    home: dict = field(default_factory=dict)       # event -> mean for the home side
    away: dict = field(default_factory=dict)
    disp_team: dict = field(default_factory=dict)  # event -> dispersion of one side's count
    disp_total: dict = field(default_factory=dict)
    sot_per_xg: float = 0.0                        # shots on target per goal of xG, both sides
    shots_per_xg: float = 0.0


@dataclass
class EventModel:
    leagues: dict = field(default_factory=dict)    # name -> League ('*' = all pooled)
    teams: dict = field(default_factory=dict)      # (league, team) -> {event: (for_sum, against_sum, n)}
    names: dict = field(default_factory=dict)      # league -> [team names]

    @classmethod
    def fit(cls, rows: list[dict], before: str | None = None) -> EventModel:
        """Everything known before `before` (an ISO date; None = all)."""
        use = [r for r in rows if before is None or r["date"] < before]
        m = cls()
        by_league = defaultdict(list)
        for r in use:
            by_league[r.get("league") or "?"].append(r)
            by_league["*"].append(r)
        for lg, rs in by_league.items():
            L = League(n=len(rs))
            for ev in EVENTS:
                hv = [r["stats"][ev][0] for r in rs if ev in r["stats"]]
                av = [r["stats"][ev][1] for r in rs if ev in r["stats"]]
                if hv:
                    L.home[ev], L.away[ev] = sum(hv) / len(hv), sum(av) / len(av)
                    L.disp_team[ev] = _disp(hv + av)
                    L.disp_total[ev] = _disp([h + a for h, a in zip(hv, av, strict=True)])
            xs = [(sum(r["stats"]["xg"]), sum(r["stats"]["sot"]), sum(r["stats"]["shots"])) for r in rs
                  if all(k in r["stats"] for k in ("xg", "sot", "shots")) and sum(r["stats"]["xg"]) > 0]
            if xs:
                L.sot_per_xg = sum(x[1] for x in xs) / sum(x[0] for x in xs)
                L.shots_per_xg = sum(x[2] for x in xs) / sum(x[0] for x in xs)
            m.leagues[lg] = L
        for r in use:
            lg = r.get("league") or "?"
            for side, team in ((0, r["home"]), (1, r["away"])):
                rec = m.teams.setdefault((lg, team), {})
                for ev in EVENTS:
                    if ev in r["stats"]:
                        f, a, n = rec.get(ev, (0.0, 0.0, 0))
                        rec[ev] = (f + r["stats"][ev][side], a + r["stats"][ev][1 - side], n + 1)
            m.names.setdefault(lg, [])
            for t in (r["home"], r["away"]):
                if t not in m.names[lg]:
                    m.names[lg].append(t)
        return m

    def league(self, name: str | None) -> League:
        L = self.leagues.get(name or "")
        return L if L and L.n >= MIN_LEAGUE else self.leagues.get("*", League())

    def resolve(self, league: str | None, team: str) -> str | None:
        """The FotMob name of a board team in this league: equal, or the only STRONG pairing."""
        cands = self.names.get(league or "", [])
        if team in cands:
            return team
        # STRONG and the only candidate that matches at all: "Dundee Utd" also half-matches "Dundee United",
        # so it is NOT paired with "Dundee" even though "Dundee" is a clean subset of it.
        near = [c for c in cands if fm.team_score(team, c) >= fm.WEAK]
        if len(near) != 1 or fm.team_score(team, near[0]) < fm.STRONG:
            return None
        c = near[0]
        ct, tt = fm.tokens(c), fm.tokens(team)
        if len(ct) < len(tt) and any(o != c and set(ct) < set(fm.tokens(o)) for o in cands):
            return None          # "Dundee Utd" is not "Dundee" when "Dundee United" is in the league
        return c

    def _rate(self, league: str, team: str | None, ev: str, L: League, side_mean: float, conc_mean: float):
        """(attack, concede) multipliers, shrunk to 1.0 by SHRINK pseudo-matches."""
        rec = self.teams.get((league, team), {}).get(ev) if team else None
        if not rec or side_mean <= 0 or conc_mean <= 0:
            return 1.0, 1.0, 0
        f, a, n = rec
        avg = (L.home.get(ev, 0) + L.away.get(ev, 0)) / 2 or 1e-9
        att = (f + SHRINK * avg) / (n + SHRINK) / avg
        con = (a + SHRINK * avg) / (n + SHRINK) / avg
        return att, con, n

    def predict(self, league: str | None, home: str, away: str, xg: tuple[float, float] | None = None) -> dict:
        lg_key = league if league in self.leagues and self.leagues[league].n >= MIN_LEAGUE else "*"
        L = self.league(league)
        th, ta = self.resolve(league, home), self.resolve(league, away)
        out = {"teams_found": [th, ta], "league_used": lg_key, "events": {}}
        for ev in EVENTS:
            if ev not in L.home:
                continue
            ah, ch, nh = self._rate(league or "", th, ev, L, L.home[ev], L.away[ev])
            aa, ca, na = self._rate(league or "", ta, ev, L, L.away[ev], L.home[ev])
            mh, ma = L.home[ev] * ah * ca, L.away[ev] * aa * ch
            anchored = False
            if ev in ("sot", "shots") and xg and L.sot_per_xg > 0:
                per = L.sot_per_xg if ev == "sot" else L.shots_per_xg
                mh = (1 - ANCHOR) * mh + ANCHOR * per * xg[0]
                ma = (1 - ANCHOR) * ma + ANCHOR * per * xg[1]
                anchored = True
            e = {"label": LABEL[ev], "home": round(mh, 2), "away": round(ma, 2), "total": round(mh + ma, 2),
                 "matches_behind": [nh, na], "anchored_to_xg": anchored}
            if ev == "red":
                e["chance_any"] = round(1 - math.exp(-(mh + ma)), 3)
            else:
                dt, dm = L.disp_total.get(ev, math.inf), L.disp_team.get(ev, math.inf)
                e["over"] = {str(x): round(over(x, mh + ma, dt), 3) for x in LINES.get(ev, ())}
                e["home_over"] = {str(x): round(over(x, mh, dm), 3) for x in TEAM_LINES.get(ev, ())}
                e["away_over"] = {str(x): round(over(x, ma, dm), 3) for x in TEAM_LINES.get(ev, ())}
            out["events"][ev] = e
        return out


def xg_from_grid(grid: list | None) -> tuple[float, float] | None:
    """The framework's expected goals for each side from the board's 0-5 score table (rows = home goals)."""
    if not grid:
        return None
    tot = sum(sum(r) for r in grid) or 1.0
    n = len(grid)
    return (sum(i * sum(grid[i]) for i in range(n)) / tot, sum(j * sum(grid[i][j] for i in range(n)) for j in range(n)) / tot)


# ---------------------------------------------------------------- the season-average baseline (what must be beaten)

def baseline(rows: list[dict], before: str, league: str, home: str, away: str, ev: str) -> tuple[float, float]:
    """The two teams' own averages FOR, before the date (the league mean when a team has none): the number the
    app showed before this model existed."""
    def avg(team, side_idx):
        v = [r["stats"][ev][0] if r["home"] == team else r["stats"][ev][1] for r in rows
             if r["date"] < before and ev in r["stats"] and team in (r["home"], r["away"])]
        return sum(v) / len(v) if v else None
    lg = [r for r in rows if r["date"] < before and r.get("league") == league and ev in r["stats"]] or \
         [r for r in rows if r["date"] < before and ev in r["stats"]]
    lm_h = sum(r["stats"][ev][0] for r in lg) / len(lg) if lg else 0.0
    lm_a = sum(r["stats"][ev][1] for r in lg) / len(lg) if lg else 0.0
    h, a = avg(home, 0), avg(away, 1)
    return (h if h is not None else lm_h, a if a is not None else lm_a)
