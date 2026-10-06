"""
NBA DATA (Architect 2026-10-06: "look at basketball NBA ... adapt the framework").

Free, keyless ESPN endpoints:
  scoreboard   site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD
               -> every game that day: teams, final score, season type
               (1 preseason, 2 regular season, 3 playoffs, 5 play-in)
  odds         sports.core.api.espn.com/v2/.../events/<id>/competitions/<id>/odds
               -> the closing line ESPN BET posted: moneyline, spread, total

Both are cached under data/cache/nba/ (a finished game never changes), so a
study re-runs offline. Nothing is guessed: a game without a final score or a
line simply has none (HR35).
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

CACHE = Path(__file__).parent / "cache" / "nba"
_UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
_SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}"
_ODDS = ("https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{e}"
         "/competitions/{e}/odds")


@dataclass
class Game:
    id: str
    date: str               # ISO date of tip-off (UTC)
    season: int             # ESPN season year (2026 = 2025-26)
    stype: int              # 1 pre, 2 regular, 3 playoffs, 5 play-in
    home: str               # abbreviation
    away: str
    hs: Optional[int] = None
    as_: Optional[int] = None
    completed: bool = False
    ml_home: Optional[float] = None    # closing moneyline, decimal odds
    ml_away: Optional[float] = None
    spread: Optional[float] = None     # home handicap (negative = home favoured)
    total: Optional[float] = None
    home_name: str = ""                # ESPN display name, e.g. "Boston Celtics"
    away_name: str = ""
    tip: str = ""                      # tip-off, ISO UTC ("2026-10-07T00:00Z")


def _get(url: str, tries: int = 3) -> Optional[dict]:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001 — network hiccup: retry, then give up honestly
            time.sleep(1 + i)
    return None


def _american(x) -> Optional[float]:
    try:
        a = float(x)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return round(1 + (a / 100 if a > 0 else 100 / -a), 4)


def scoreboard(d: date, use_cache: bool = True) -> list[Game]:
    key = d.strftime("%Y%m%d")
    path = CACHE / "scoreboard" / f"{key}.json"
    blob = None
    if use_cache and path.exists():
        blob = json.loads(path.read_text(encoding="utf-8"))
    else:
        blob = _get(_SB.format(d=key))
        if blob is None:
            return []
        done = all(e.get("status", {}).get("type", {}).get("completed") for e in blob.get("events", []))
        if done and d < date.today():          # cache only finished days
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(blob), encoding="utf-8")
    out = []
    for e in blob.get("events", []):
        c = e["competitions"][0]
        side = {x["homeAway"]: x for x in c["competitors"]}
        if "home" not in side or "away" not in side:
            continue
        g = Game(id=e["id"], date=e["date"][:10], season=e["season"]["year"],
                 stype=e["season"]["type"], home=side["home"]["team"]["abbreviation"],
                 away=side["away"]["team"]["abbreviation"],
                 completed=bool(e.get("status", {}).get("type", {}).get("completed")),
                 home_name=side["home"]["team"].get("displayName", ""),
                 away_name=side["away"]["team"].get("displayName", ""),
                 tip=e.get("date", ""))
        if g.completed:
            try:
                g.hs, g.as_ = int(side["home"]["score"]), int(side["away"]["score"])
            except (KeyError, TypeError, ValueError):
                g.completed = False
        out.append(g)
    return out


def attach_odds(g: Game, use_cache: bool = True) -> Game:
    path = CACHE / "odds" / f"{g.id}.json"
    if use_cache and path.exists():
        blob = json.loads(path.read_text(encoding="utf-8"))
    else:
        blob = _get(_ODDS.format(e=g.id))
        if blob is None:
            return g
        if g.completed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(blob), encoding="utf-8")
    items = [i for i in blob.get("items", []) if "Live" not in (i.get("provider", {}).get("name") or "")]
    if not items:
        return g
    o = items[0]
    h, a = o.get("homeTeamOdds") or {}, o.get("awayTeamOdds") or {}
    g.ml_home, g.ml_away = _american(h.get("moneyLine")), _american(a.get("moneyLine"))
    try:
        g.spread = float(o["spread"]) if o.get("spread") is not None else None   # home line
    except (TypeError, ValueError):
        g.spread = None
    try:
        g.total = float(o["overUnder"]) if o.get("overUnder") is not None else None
    except (TypeError, ValueError):
        g.total = None
    return g


def season_games(start: date, end: date, with_odds: bool = True, workers: int = 8) -> list[Game]:
    days = [start + timedelta(n) for n in range((end - start).days + 1)]
    with ThreadPoolExecutor(workers) as ex:
        games = [g for day in ex.map(scoreboard, days) for g in day]
    if with_odds:
        with ThreadPoolExecutor(workers) as ex:
            games = list(ex.map(attach_odds, games))
    return sorted(games, key=lambda g: (g.date, g.id))
