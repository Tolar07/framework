"""
CANDIDATE MODEL INPUTS (Architect 2026-10-28: "the model was missing
head-to-head, form, last matches as real inputs").

Pure feature functions over a list of past matches — each reads ONLY matches
strictly before the day asked about, so a walk-forward test can't leak. They
are CANDIDATES: backtest/inputs_study.py tests each beyond the model's own
chance on unseen matches (engine/walkforward); one goes live only if it
improves out of sample, through the existing retrain / promotion path.

A match here is any object / dict with date, home, away, hg, ag (football-data
MatchResult is adapted by `from_results`); xG rows come from data/match_study.

  h2h(...)        last meetings of the two clubs: venue-aware (a meeting at
                  the same ground counts 1, the reverse fixture SAME_VENUE_W),
                  time-decayed (half-life H2H_HALF_LIFE days), within
                  H2H_MAX_YEARS, at most H2H_MAX meetings. Goal difference and
                  total goals from today's home side's view.
  form(...)       last FORM_N matches of one club: points and goal difference
                  per game, overall and venue-only (home games for the home
                  side, away games for the away side).
  xg_form(...)    last XG_N studied matches of one club: xG for / against.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Optional

H2H_HALF_LIFE = 730
H2H_MAX_YEARS = 6
H2H_MAX = 8
SAME_VENUE_W = 0.5      # the reverse fixture's weight
FORM_N = 6
XG_N = 5


def from_results(results: Iterable[Any]) -> list[dict]:
    return [{"date": r.date, "home": r.home_team, "away": r.away_team, "hg": r.fthg, "ag": r.ftag}
            for r in results]


class History:
    """Past matches indexed by club and by pair, for fast 'before day' reads."""

    def __init__(self, matches: Iterable[dict]):
        self.by_team: dict[str, list[dict]] = defaultdict(list)
        self.by_pair: dict[frozenset, list[dict]] = defaultdict(list)
        seen = set()
        for m in sorted(matches, key=lambda x: x["date"]):
            k = (m["date"], m["home"], m["away"])
            if k in seen:
                continue
            seen.add(k)
            self.by_team[m["home"]].append(m)
            self.by_team[m["away"]].append(m)
            self.by_pair[frozenset((m["home"], m["away"]))].append(m)


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days


def h2h(hist: History, home: str, away: str, day: str) -> Optional[dict]:
    meets = [m for m in hist.by_pair.get(frozenset((home, away)), [])
             if m["date"] < day and _days(m["date"], day) <= 365 * H2H_MAX_YEARS][-H2H_MAX:]
    if not meets:
        return None
    wsum = gd = tot = 0.0
    for m in meets:
        w = 0.5 ** (_days(m["date"], day) / H2H_HALF_LIFE) * (1.0 if m["home"] == home else SAME_VENUE_W)
        d = (m["hg"] - m["ag"]) if m["home"] == home else (m["ag"] - m["hg"])
        wsum += w
        gd += w * d
        tot += w * (m["hg"] + m["ag"])
    return {"n": len(meets), "gd": gd / wsum, "goals": tot / wsum, "weight": round(wsum, 3)}


def _pts(m: dict, team: str) -> tuple[int, int, int]:
    gf, ga = (m["hg"], m["ag"]) if m["home"] == team else (m["ag"], m["hg"])
    return (3 if gf > ga else 1 if gf == ga else 0), gf - ga, gf + ga


def form(hist: History, team: str, day: str, venue: Optional[str] = None, n: int = FORM_N) -> Optional[dict]:
    ms = [m for m in hist.by_team.get(team, []) if m["date"] < day
          and (venue is None or (venue == "home") == (m["home"] == team))][-n:]
    if len(ms) < 3:
        return None
    p = [_pts(m, team) for m in ms]
    return {"n": len(ms), "ppg": sum(x[0] for x in p) / len(p), "gd": sum(x[1] for x in p) / len(p),
            "goals": sum(x[2] for x in p) / len(p)}


def fixture_features(hist: History, home: str, away: str, day: str) -> dict[str, Optional[float]]:
    """The candidate inputs for one fixture (None = not enough history)."""
    out: dict[str, Optional[float]] = {}
    h = h2h(hist, home, away, day)
    out["h2h_gd"] = h["gd"] if h else None
    out["h2h_goals"] = h["goals"] if h else None
    fh, fa = form(hist, home, day), form(hist, away, day)
    vh, va = form(hist, home, day, "home"), form(hist, away, day, "away")
    out["form_ppg"] = fh["ppg"] - fa["ppg"] if fh and fa else None
    out["form_gd"] = fh["gd"] - fa["gd"] if fh and fa else None
    out["form_venue_ppg"] = vh["ppg"] - va["ppg"] if vh and va else None
    out["form_goals"] = (fh["goals"] + fa["goals"]) / 2 if fh and fa else None
    return out


def xg_form(rows: list[dict], team_id: str, day: str, n: int = XG_N) -> Optional[dict]:
    """rows: data/match_study records sorted by ko."""
    got = []
    for r in rows:
        if r["ko"][:10] >= day:
            break
        for s, o in (("home", "away"), ("away", "home")):
            if str(r[s]["id"]) == str(team_id) and r[s].get("xg") is not None and r[o].get("xg") is not None:
                got.append((r[s]["xg"], r[o]["xg"]))
    got = got[-n:]
    if len(got) < 3:
        return None
    return {"n": len(got), "xgf": sum(x for x, _ in got) / len(got), "xga": sum(y for _, y in got) / len(got)}


def log_loss(p: float, y: int) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if y else 1 - p)
