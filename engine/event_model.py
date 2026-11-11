"""
Football match stats, predicted (framework #555, widened 2026-11-11). RECORD-ONLY.

Architect 2026-11-11: "I need to see all the predictions ... number of cards, numbers of fouls ... a possible red
card ... shots on target ... it needs to agree with the framework and the models" and then "elaborate on it ...
show me a football match stats ... Flashscore ... all these things". This predicts, for every rated fixture, every
team stat a match-stats page shows (REGISTRY: about 35, grouped as Flashscore and FotMob group them), each team's
number and the total, the first-half share, full distributions and over/under chances for the counts, and the chance
of a red card. It picks nothing, stakes nothing and moves no other number (shadow).

How (backtest/EVENT_MODEL_STUDY.md has the evidence; a stat the walk-forward study does not let through is not
published):
- History: data/match_stats/<month>.jsonl (FotMob post-match stats of every rated fixture; every stat by half since
  #556, backfilled).
- Counts: each team's rate FOR and AGAINST, shrunk to its league's mean with SHRINK pseudo-matches, as multipliers on
  the league's home or away mean: mu_home = league_home_mean * attack(home) * concede(away) — the goals model's
  attack-defence form applied to every other stat. Spread: negative binomial, dispersion from the league's history.
- Shares (possession): the same multipliers, then the two sides scaled to add up to 100.
- **Agrees with the framework's goals model:** every attacking stat that follows chance quality (shots, shots on
  target, shots in the box, big chances, touches in the box, xG on target) is averaged (ANCHOR) with the league's
  ratio of that stat to expected goals times the board's own expected goals for each side (the Dixon-Coles score
  table). Expected goals itself IS the board's number. `tests/event_model_test.py` checks shots on target stay
  consistent with xG.
- Halves: the league's first-half share of each stat (from the saved halves) splits the total.
- Red card: Poisson on both teams' red rates; reported as the chance of at least one.
- Teams: board names are paired with the saved names inside the same league by engine/fixture_match.team_score:
  STRONG, and no other club in the league matches even weakly; an unpaired team falls back to the league mean.
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
SHRINK = 6.0           # pseudo-matches at the league mean behind every team rate
MIN_LEAGUE = 12        # fewer matches than this in a league: use all leagues pooled
ANCHOR = 0.5           # weight of the expected-goals reading in the attacking stats

# short name: (FotMob key, label, group, kind, (match lines), (team lines))
# kind: count (negative binomial), share (two sides add to 100), xg (continuous, from the board's xG)
REGISTRY: dict[str, tuple] = {
    "possession":   ("BallPossesion", "Ball possession %", "Top stats", "share", (), ()),
    "xg":           ("expected_goals", "Expected goals (xG)", "Top stats", "xg", (), ()),
    "xgot":         ("expected_goals_on_target", "xG on target (xGOT)", "Expected goals", "xg", (), ()),
    "xg_open":      ("expected_goals_open_play", "xG open play", "Expected goals", "xg", (), ()),
    "xg_set":       ("expected_goals_set_play", "xG set play", "Expected goals", "xg", (), ()),
    "big_chances":  ("big_chance", "Big chances", "Top stats", "count", (2.5, 3.5, 4.5), (0.5, 1.5, 2.5)),
    "big_missed":   ("big_chance_missed_title", "Big chances missed", "Top stats", "count", (1.5, 2.5), ()),
    "shots":        ("total_shots", "Total shots", "Shots", "count", (20.5, 23.5, 26.5), (9.5, 11.5, 13.5)),
    "sot":          ("ShotsOnTarget", "Shots on target", "Shots", "count", (6.5, 7.5, 8.5, 9.5), (2.5, 3.5, 4.5, 5.5)),
    "shots_off":    ("ShotsOffTarget", "Shots off target", "Shots", "count", (8.5, 10.5), (3.5, 4.5, 5.5)),
    "blocked":      ("blocked_shots", "Blocked shots", "Shots", "count", (5.5, 7.5), (1.5, 2.5, 3.5)),
    "woodwork":     ("shots_woodwork", "Hit woodwork", "Shots", "count", (0.5, 1.5), ()),
    "shots_in_box": ("shots_inside_box", "Shots inside box", "Shots", "count", (14.5, 16.5), (5.5, 7.5)),
    "shots_out_box": ("shots_outside_box", "Shots outside box", "Shots", "count", (8.5, 10.5), (3.5, 4.5)),
    "box_touches":  ("touches_opp_box", "Touches in opposition box", "Attack", "count", (40.5, 50.5), ()),
    "corners":      ("corners", "Corners", "Set pieces", "count", (7.5, 8.5, 9.5, 10.5, 11.5), (3.5, 4.5, 5.5)),
    "offsides":     ("Offsides", "Offsides", "Set pieces", "count", (2.5, 3.5, 4.5), (0.5, 1.5, 2.5)),
    "throws":       ("player_throws", "Throw-ins", "Set pieces", "count", (38.5, 42.5), ()),
    "passes":       ("passes", "Passes", "Passes", "count", (800.5, 900.5), ()),
    "passes_acc":   ("accurate_passes", "Accurate passes", "Passes", "count", (), ()),
    "own_half":     ("own_half_passes", "Passes in own half", "Passes", "count", (), ()),
    "opp_half":     ("opposition_half_passes", "Passes in opposition half", "Passes", "count", (), ()),
    "long_acc":     ("long_balls_accurate", "Accurate long balls", "Passes", "count", (), ()),
    "crosses_acc":  ("accurate_crosses", "Accurate crosses", "Passes", "count", (6.5, 8.5), ()),
    "tackles":      ("tackles", "Tackles", "Defence", "count", (28.5, 32.5, 36.5), (13.5, 15.5, 17.5)),
    "interceptions": ("interceptions", "Interceptions", "Defence", "count", (14.5, 17.5), ()),
    "blocks":       ("shot_blocks", "Blocks", "Defence", "count", (5.5, 7.5), ()),
    "clearances":   ("clearances", "Clearances", "Defence", "count", (40.5, 50.5), ()),
    "saves":        ("keeper_saves", "Goalkeeper saves", "Defence", "count", (4.5, 5.5, 6.5), (1.5, 2.5, 3.5)),
    "duels":        ("duel_won", "Duels won", "Duels", "count", (), ()),
    "ground_duels": ("ground_duels_won", "Ground duels won", "Duels", "count", (), ()),
    "aerials":      ("aerials_won", "Aerial duels won", "Duels", "count", (), ()),
    "dribbles":     ("dribbles_succeeded", "Successful dribbles", "Duels", "count", (), ()),
    "fouls":        ("fouls", "Fouls", "Discipline", "count", (20.5, 22.5, 24.5), (9.5, 11.5, 13.5)),
    "yellow":       ("yellow_cards", "Yellow cards", "Discipline", "count", (2.5, 3.5, 4.5, 5.5), (0.5, 1.5, 2.5)),
    "red":          ("red_cards", "Red card", "Discipline", "count", (), ()),
}
EVENTS = tuple(REGISTRY)
LABEL = {k: v[1] for k, v in REGISTRY.items()}
GROUP = {k: v[2] for k, v in REGISTRY.items()}
KIND = {k: v[3] for k, v in REGISTRY.items()}
LINES = {k: v[4] for k, v in REGISTRY.items() if v[4]}
TEAM_LINES = {k: v[5] for k, v in REGISTRY.items() if v[5]}
FOTMOB = {v[0]: k for k, v in REGISTRY.items()}
# the original 15 keys of data/match_stats.py "stats" -> our short names (lines saved before #556)
OLD = {"possession": "possession", "xg": "xg", "shots": "shots", "sot": "sot", "shots_in_box": "shots_in_box",
       "big_chances": "big_chances", "big_missed": "big_missed", "box_touches": "box_touches", "corners": "corners",
       "passes": "passes", "passes_acc": "passes_acc", "fouls": "fouls", "yellow": "yellow", "red": "red",
       "saves": "saves"}
FOLLOWS_XG = ("shots", "sot", "shots_in_box", "big_chances", "box_touches", "xgot", "xg_open", "xg_set")


def _norm_row(r: dict) -> dict:
    """{short name: [home, away]} for the whole match, and {short name: first-half share} where saved."""
    st = {OLD[k]: v for k, v in (r.get("stats") or {}).items() if k in OLD}
    full = r.get("full") or {}
    for k, v in (full.get("all") or {}).items():
        if k in FOTMOB:
            st[FOTMOB[k]] = v
    h1 = {}
    for k, v in (full.get("h1") or {}).items():
        if k in FOTMOB and FOTMOB[k] in st:
            tot = sum(st[FOTMOB[k]])
            if tot > 0:
                h1[FOTMOB[k]] = sum(v) / tot
    return {**r, "stats": st, "h1_share": h1}


def load_history(paths: Iterable[Path] | None = None) -> list[dict]:
    """Every saved match with its stats, oldest first. A stat missing for a match simply doesn't count for it."""
    rows = []
    for p in sorted(paths if paths is not None else STATS_DIR.glob("*.jsonl")):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("stats") and r.get("home") and r.get("away") and r.get("date"):
                    rows.append(_norm_row(r))
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
    home: dict = field(default_factory=dict)       # stat -> mean for the home side
    away: dict = field(default_factory=dict)
    disp_team: dict = field(default_factory=dict)  # stat -> dispersion of one side's count
    disp_total: dict = field(default_factory=dict)
    per_xg: dict = field(default_factory=dict)     # stat -> both sides' stat per goal of xG
    h1_share: dict = field(default_factory=dict)   # stat -> share of the match total in the first half

    @property
    def sot_per_xg(self) -> float:
        return self.per_xg.get("sot", 0.0)


@dataclass
class EventModel:
    leagues: dict = field(default_factory=dict)    # name -> League ('*' = all pooled)
    teams: dict = field(default_factory=dict)      # (league, team) -> {stat: (for_sum, against_sum, n)}
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
                if len(hv) < 5:
                    continue
                L.home[ev], L.away[ev] = sum(hv) / len(hv), sum(av) / len(av)
                if KIND[ev] == "count":
                    L.disp_team[ev] = _disp(hv + av)
                    L.disp_total[ev] = _disp([h + a for h, a in zip(hv, av, strict=True)])
                sh = [r["h1_share"][ev] for r in rs if ev in r.get("h1_share", {})]
                if len(sh) >= 5:
                    L.h1_share[ev] = sum(sh) / len(sh)
                if ev in FOLLOWS_XG:
                    xs = [(sum(r["stats"]["xg"]), sum(r["stats"][ev])) for r in rs
                          if "xg" in r["stats"] and ev in r["stats"] and sum(r["stats"]["xg"]) > 0]
                    if xs and sum(x[0] for x in xs) > 0:
                        L.per_xg[ev] = sum(x[1] for x in xs) / sum(x[0] for x in xs)
            m.leagues[lg] = L
        for r in use:
            lg = r.get("league") or "?"
            for side, team in ((0, r["home"]), (1, r["away"])):
                rec = m.teams.setdefault((lg, team), {})
                for ev, v in r["stats"].items():
                    f, a, n = rec.get(ev, (0.0, 0.0, 0))
                    rec[ev] = (f + v[side], a + v[1 - side], n + 1)
            m.names.setdefault(lg, [])
            for t in (r["home"], r["away"]):
                if t not in m.names[lg]:
                    m.names[lg].append(t)
        return m

    def league(self, name: str | None) -> League:
        L = self.leagues.get(name or "")
        return L if L and L.n >= MIN_LEAGUE else self.leagues.get("*", League())

    def resolve(self, league: str | None, team: str) -> str | None:
        """The saved name of a board team in this league: equal, or the only STRONG pairing with no near miss."""
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

    def _rate(self, league: str, team: str | None, ev: str, L: League):
        """(attack, concede, matches) multipliers, shrunk to 1.0 by SHRINK pseudo-matches."""
        rec = self.teams.get((league, team), {}).get(ev) if team else None
        avg = (L.home.get(ev, 0) + L.away.get(ev, 0)) / 2
        if not rec or avg <= 0:
            return 1.0, 1.0, 0
        f, a, n = rec
        return (f + SHRINK * avg) / (n + SHRINK) / avg, (a + SHRINK * avg) / (n + SHRINK) / avg, n

    def predict(self, league: str | None, home: str, away: str, xg: tuple[float, float] | None = None) -> dict:
        lg_key = league if league in self.leagues and self.leagues[league].n >= MIN_LEAGUE else "*"
        L = self.league(league)
        th, ta = self.resolve(league, home), self.resolve(league, away)
        out = {"teams_found": [th, ta], "league_used": lg_key, "events": {}}
        for ev in EVENTS:
            if ev not in L.home:
                continue
            kind = KIND[ev]
            ah, ch, nh = self._rate(league or "", th, ev, L)
            aa, ca, na = self._rate(league or "", ta, ev, L)
            mh, ma = L.home[ev] * ah * ca, L.away[ev] * aa * ch
            anchored = False
            if ev == "xg" and xg:
                mh, ma, anchored = xg[0], xg[1], True
            elif ev in FOLLOWS_XG and xg and L.per_xg.get(ev):
                # per_xg is both sides' stat per goal of both sides' xG; split by each side's own xG
                mh = (1 - ANCHOR) * mh + ANCHOR * L.per_xg[ev] * xg[0]
                ma = (1 - ANCHOR) * ma + ANCHOR * L.per_xg[ev] * xg[1]
                anchored = True
            if kind == "share":
                t = (mh + ma) or 1.0
                mh, ma = 100 * mh / t, 100 * ma / t
            e = {"label": LABEL[ev], "group": GROUP[ev], "kind": kind, "home": round(mh, 2), "away": round(ma, 2),
                 "total": round(mh + ma, 2), "matches_behind": [nh, na], "anchored_to_xg": anchored}
            if ev in L.h1_share and kind != "share":
                e["first_half"] = round((mh + ma) * L.h1_share[ev], 2)
            if ev == "red":
                e["chance_any"] = round(1 - math.exp(-(mh + ma)), 3)
            elif kind == "count":
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
    def avg(team):
        v = [r["stats"][ev][0] if r["home"] == team else r["stats"][ev][1] for r in rows
             if r["date"] < before and ev in r["stats"] and team in (r["home"], r["away"])]
        return sum(v) / len(v) if v else None
    lg = [r for r in rows if r["date"] < before and r.get("league") == league and ev in r["stats"]] or \
         [r for r in rows if r["date"] < before and ev in r["stats"]]
    lm_h = sum(r["stats"][ev][0] for r in lg) / len(lg) if lg else 0.0
    lm_a = sum(r["stats"][ev][1] for r in lg) / len(lg) if lg else 0.0
    h, a = avg(home), avg(away)
    return (h if h is not None else lm_h, a if a is not None else lm_a)
