"""
Form & standings context — a brain input derived from data already ingested.

WHY
  The Dixon-Coles engine rates a team from a whole season's goals, weighting a
  September match the same as an April one. It has no notion of league POSITION,
  POINTS, or RECENT FORM — the "what's at stake / who's hot" context a human
  weighs. This module adds that context WITHOUT a new data source and WITHOUT
  touching the calibrated probability model: everything here is computed from
  the same football-data results the model is already fit on.

HONEST SCOPE (HR35)
  - Free, all leagues, no new dependency — it is arithmetic on results.
  - It does NOT invent player form, injuries, lineups or "motivation": there is
    no reliable free source for those in the deploy leagues (Understat's xG
    covers only the big-6, not Eredivisie/Danish/Ekstraklasa; injury feeds are
    unstructured and patchy), so this module deliberately stops at what the
    results actually support — standings, points, position, and recent form.
  - It is a RANKING/CONTEXT signal, not a probability override. It never changes
    an EV or a CLV number; it re-ranks equally-confident picks and flags when the
    model likes a team whose recent form contradicts it, for the Architect to
    weigh. Turning it into a probability input is a separate, backtested step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TeamForm:
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    gf: int
    ga: int
    points: int
    position: int = 0                 # filled by compute_table (1 = top)
    last5_points: int = 0             # points from the most recent <=5 matches
    last5_played: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @property
    def ppg(self) -> float:
        return round(self.points / self.played, 3) if self.played else 0.0

    @property
    def last5_ppg(self) -> float:
        return round(self.last5_points / self.last5_played, 3) if self.last5_played else 0.0


def compute_table(results: list) -> dict[str, TeamForm]:
    """Build the current league table + recent form from played matches.

    `results` are MatchResult-like objects (home_team, away_team, fthg, ftag,
    date). Only decided matches count (goals present). Never guesses a result."""
    agg: dict[str, dict] = {}
    per_team_matches: dict[str, list] = {}

    def _slot(t):
        return agg.setdefault(t, dict(won=0, drawn=0, lost=0, gf=0, ga=0, points=0, played=0))

    played = [r for r in results
              if getattr(r, "fthg", None) is not None and getattr(r, "ftag", None) is not None]
    # Chronological so "last 5" is genuinely the most recent.
    played.sort(key=lambda r: getattr(r, "date", "") or "")

    for r in played:
        h, a, hg, ag = r.home_team, r.away_team, int(r.fthg), int(r.ftag)
        H, A = _slot(h), _slot(a)
        H["gf"] += hg; H["ga"] += ag; A["gf"] += ag; A["ga"] += hg
        H["played"] += 1; A["played"] += 1
        if hg > ag:
            H["won"] += 1; H["points"] += 3; A["lost"] += 1
            hp, ap = 3, 0
        elif ag > hg:
            A["won"] += 1; A["points"] += 3; H["lost"] += 1
            hp, ap = 0, 3
        else:
            H["drawn"] += 1; A["drawn"] += 1; H["points"] += 1; A["points"] += 1
            hp, ap = 1, 1
        per_team_matches.setdefault(h, []).append(hp)
        per_team_matches.setdefault(a, []).append(ap)

    table = {t: TeamForm(team=t, played=v["played"], won=v["won"], drawn=v["drawn"],
                         lost=v["lost"], gf=v["gf"], ga=v["ga"], points=v["points"])
             for t, v in agg.items()}

    for t, pts_seq in per_team_matches.items():
        last5 = pts_seq[-5:]
        table[t].last5_points = sum(last5)
        table[t].last5_played = len(last5)

    # Position: points, then goal difference, then goals for (standard tie-break).
    for pos, t in enumerate(sorted(table.values(),
                                   key=lambda f: (f.points, f.gd, f.gf), reverse=True), 1):
        table[t.team].position = pos
    return table


@dataclass
class FixtureForm:
    home: Optional[TeamForm]
    away: Optional[TeamForm]

    def summary(self) -> str:
        """One honest line for the board. 'NO DATA' where a side isn't in the
        table yet (e.g. a promoted club with no played matches)."""
        def one(f):
            return (f"P{f.position} {f.points}pts, last5 {f.last5_points}/"
                    f"{f.last5_played*3}" if f else "NO DATA")
        return f"form — home: {one(self.home)} | away: {one(self.away)}"


def fixture_form(table: dict[str, TeamForm], home: str, away: str) -> FixtureForm:
    return FixtureForm(home=table.get(home), away=table.get(away))


def form_support(ff: FixtureForm, side: str) -> Optional[float]:
    """A bounded [-1, 1] recent-form tilt toward `side` ('home' or 'away'),
    from the two teams' last-5 PPG gap. Positive = recent form backs the side
    the model likes; negative = form contradicts it (a caution). None when
    either side has no matches yet — never fabricated.

    Ranking/flagging signal ONLY; it is never added to a probability or an EV."""
    if not ff.home or not ff.away or side not in ("home", "away"):
        return None
    if ff.home.last5_played == 0 or ff.away.last5_played == 0:
        return None
    gap = ff.home.last5_ppg - ff.away.last5_ppg      # >0 means home in better form
    if side == "away":
        gap = -gap
    return round(max(-1.0, min(1.0, gap / 3.0)), 3)  # /3 => full 3ppg swing saturates
