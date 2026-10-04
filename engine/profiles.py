"""
TEAM TACTICAL PROFILES (Architect 2026-10-04).

A short, factual style profile per team from free data — no paid API:

  club teams   football-data.co.uk results (+ shots / shots on target where
               the file carries them: HS, AS, HST, AST)
  national     martj42 international results (every men's international)

For each team, over its last N matches before a date (home and away):
  gf, ga          goals scored / conceded per game
  draw            share of games drawn
  btts            share where both teams scored
  o25             share with 3+ goals
  cs              share with a clean sheet
  fts             share where the team failed to score
  sot_f, sot_a    shots on target for / against per game (clubs, if present)
  n               games used

`match_profile(home, away)` combines the two into the match picture the
selection uses: expected tempo, the draw tendency of the pairing, and a
one-line summary for the board. Profiles describe; they never invent a
probability on their own (the market + model still price every pick).
"""
from __future__ import annotations

import csv
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

CACHE = Path(__file__).parent.parent / "data" / "cache"
LAST_N = 20


@dataclass
class Row:
    date: str
    home: str
    away: str
    hg: int
    ag: int
    hst: Optional[float] = None
    ast: Optional[float] = None


@dataclass
class Profile:
    team: str
    n: int = 0
    gf: float = 0.0
    ga: float = 0.0
    draw: float = 0.0
    btts: float = 0.0
    o25: float = 0.0
    cs: float = 0.0
    fts: float = 0.0
    sot_f: Optional[float] = None
    sot_a: Optional[float] = None

    def line(self) -> str:
        s = (f"{self.team}: {self.gf:.1f} scored / {self.ga:.1f} conceded per game, "
             f"draws {self.draw:.0%}, BTTS {self.btts:.0%}, 3+ goals {self.o25:.0%}, "
             f"clean sheets {self.cs:.0%}")
        if self.sot_f is not None:
            s += f", shots on target {self.sot_f:.1f}–{self.sot_a:.1f}"
        return s + f" (last {self.n})"


def _f(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def club_rows(paths: Iterable[Path]) -> list[Row]:
    out = []
    for p in paths:
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                try:
                    hg, ag = int(r["FTHG"]), int(r["FTAG"])
                except (KeyError, TypeError, ValueError):
                    continue
                d = r.get("Date", "")
                if "/" in d:                                   # dd/mm/yy(yy)
                    dd, mm, yy = d.split("/")
                    yy = ("20" + yy) if len(yy) == 2 else yy
                    d = f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
                out.append(Row(d, r.get("HomeTeam", ""), r.get("AwayTeam", ""), hg, ag,
                               _f(r.get("HST")), _f(r.get("AST"))))
    return sorted(out, key=lambda x: x.date)


def national_rows(since: str = "2010-01-01") -> list[Row]:
    out = []
    path = CACHE / "international_results.csv"
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r["date"] < since:
                continue
            try:
                out.append(Row(r["date"], r["home_team"], r["away_team"],
                               int(r["home_score"]), int(r["away_score"])))
            except (TypeError, ValueError):
                continue
    return sorted(out, key=lambda x: x.date)


class ProfileBook:
    """Rolling per-team history; `profile(team, before)` uses only games
    strictly before `before` (so a backtest never sees the future)."""

    def __init__(self, rows: list[Row], last_n: int = LAST_N):
        self.rows = rows
        self.last_n = last_n
        self.by_team: dict[str, list[tuple]] = defaultdict(list)
        for r in rows:
            self.by_team[r.home].append((r.date, r.hg, r.ag, r.hst, r.ast))
            self.by_team[r.away].append((r.date, r.ag, r.hg, r.ast, r.hst))

    def profile(self, team: str, before: Optional[str] = None) -> Optional[Profile]:
        games = [g for g in self.by_team.get(team, []) if before is None or g[0] < before]
        games = games[-self.last_n:]
        if len(games) < 6:
            return None
        n = len(games)
        p = Profile(team, n,
                    gf=sum(g[1] for g in games) / n, ga=sum(g[2] for g in games) / n,
                    draw=sum(g[1] == g[2] for g in games) / n,
                    btts=sum(g[1] > 0 and g[2] > 0 for g in games) / n,
                    o25=sum(g[1] + g[2] >= 3 for g in games) / n,
                    cs=sum(g[2] == 0 for g in games) / n,
                    fts=sum(g[1] == 0 for g in games) / n)
        sf = [g[3] for g in games if g[3] is not None]
        sa = [g[4] for g in games if g[4] is not None]
        if len(sf) >= n // 2 and sa:
            p.sot_f, p.sot_a = sum(sf) / len(sf), sum(sa) / len(sa)
        return p


@dataclass
class MatchProfile:
    home: Optional[Profile]
    away: Optional[Profile]
    draw_tendency: Optional[float] = None    # mean of the two teams' draw shares
    tempo: Optional[float] = None            # expected goals from the two profiles
    notes: list = field(default_factory=list)

    def line(self) -> str:
        if not (self.home and self.away):
            return "profile: not enough history"
        def t(p):
            s = (f"{p.team} {p.gf:.1f}-{p.ga:.1f} a game, draws {p.draw:.0%}, "
                 f"BTTS {p.btts:.0%}, clean sheets {p.cs:.0%}")
            return s + (f", SoT {p.sot_f:.1f}-{p.sot_a:.1f}" if p.sot_f is not None else "")
        head = (f"tempo {self.tempo:.1f} goals/game · draw tendency {self.draw_tendency:.0%}"
                + "".join(f" · {n}" for n in self.notes))
        return f"{head} | {t(self.home)} | {t(self.away)}"


def match_profile(book: ProfileBook, home: str, away: str,
                  before: Optional[str] = None) -> MatchProfile:
    h, a = book.profile(home, before), book.profile(away, before)
    mp = MatchProfile(h, a)
    if h and a:
        mp.draw_tendency = (h.draw + a.draw) / 2
        mp.tempo = (h.gf + a.ga) / 2 + (a.gf + h.ga) / 2
        if mp.draw_tendency >= 0.32:
            mp.notes.append("both draw-prone")
        if mp.tempo <= 2.1:
            mp.notes.append("low-scoring pairing")
        elif mp.tempo >= 3.1:
            mp.notes.append("open, high-scoring pairing")
        if h.fts >= 0.35 or a.fts >= 0.35:
            mp.notes.append("a side often fails to score")
    return mp
