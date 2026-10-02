"""
FotMob team news — predicted / confirmed lineups and unavailable players.

Improvement #2 (Architect 2026-10-02): the model and the board were blind to
team news. FotMob publishes, per match: the lineup (predicted, then confirmed
~1 hour before kickoff) with each starter's market value, and the players
unavailable through injury or suspension with their market value and
expected return. Market value is the weight: a missing EUR 40m striker is not
a missing EUR 0.5m reserve.

Coverage is best for top leagues and national teams; lower leagues often
have no team news until the confirmed XI. No data is reported as such, never
guessed (HR35).
"""
from __future__ import annotations

import json
import urllib.request
from typing import Optional

from data.flashscore_results import _sim, MATCH_MIN

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_MATCHES = "https://www.fotmob.com/api/data/matches?date={ymd}"
_DETAILS = "https://www.fotmob.com/api/data/matchDetails?matchId={mid}"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def matches_on(day: str) -> list[dict]:
    """[{id, home, away, league, kickoff_utc}] for a date (YYYY-MM-DD)."""
    data = _get(_MATCHES.format(ymd=day.replace("-", "")))
    out = []
    for lg in data.get("leagues", []):
        for m in lg.get("matches", []):
            out.append({"id": m.get("id"), "home": (m.get("home") or {}).get("name", ""),
                        "away": (m.get("away") or {}).get("name", ""),
                        "league": lg.get("name", ""),
                        "kickoff_utc": (m.get("status") or {}).get("utcTime", "")})
    return out


def find_match(matches: list[dict], home: str, away: str) -> Optional[dict]:
    """Strict, unambiguous match on BOTH team names (same rules as grading)."""
    scored = sorted(((min(_sim(home, m["home"]), _sim(away, m["away"])), m)
                     for m in matches), key=lambda x: -x[0])
    if not scored or scored[0][0] < MATCH_MIN:
        return None
    if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.02:
        return None
    return scored[0][1]


def _side(team: dict) -> dict:
    starters = team.get("starters") or []
    unavailable = team.get("unavailable") or []
    xi_value = sum(p.get("marketValue") or 0 for p in starters)
    missing = [{"name": p.get("name"), "value": p.get("marketValue") or 0,
                "type": (p.get("unavailability") or {}).get("type"),
                "back": (p.get("unavailability") or {}).get("expectedReturn")}
               for p in unavailable]
    miss_value = sum(m["value"] for m in missing)
    pool = xi_value + miss_value
    return {"name": team.get("name"), "xi_value": xi_value, "starters": len(starters),
            "missing": sorted(missing, key=lambda m: -m["value"]),
            "missing_share": (miss_value / pool) if pool else None}


def team_news(match_id) -> Optional[dict]:
    """{lineup_type: 'predicted'|'confirmed'|None, home: side, away: side}."""
    d = _get(_DETAILS.format(mid=match_id))
    lu = (d.get("content") or {}).get("lineup") or {}
    if not lu.get("homeTeam") and not lu.get("awayTeam"):
        return None
    ltype = lu.get("lineupType")
    return {"lineup_type": "confirmed" if ltype in ("standard", "confirmed") else ltype,
            "home": _side(lu.get("homeTeam") or {}),
            "away": _side(lu.get("awayTeam") or {})}
