"""
Current-season results & standings via football-data.org (keyless-ish, free tier).

football-data.org (NOT football-data.co.uk) provides a modern REST API with:
- Current season fixtures & results for 100+ competitions
- Standings, top scorers, team info
- Free tier: 10 req/min, 100 req/day — sufficient for daily steward warm + board
- Registration required for API token (free)

WHY THIS EXISTS
  The api-football paid key is pasted but still resolves to "Free" on their side
  (dashboard lag). The free plan serves only seasons 2022-2024, so promoted clubs
  (Cambuur, Beveren, Lommel, Horsens, Como, Parma, etc.) and any team with zero
  current-season top-flight history have NO results in the fit window. ClubElo
  drops them as shared placeholders (honest NO DATA). This source provides
  CURRENT-SEASON RESULTS as they happen, so a promoted club becomes rateable
  through the existing DC machinery once it has ≥4 matches — WITHOUT waiting
  for api-football activation.

RATIFIED as a supplementary source under HR34 (Architect discretion). It is
keyless-ish (free registration), reliable, and mirrors the football-data.co.uk
schema closely enough to reuse MatchResult.

USAGE
  from data.football_data_org_source import fetch_current_season_results, fetch_standings

  results, flags = fetch_current_season_results("Eredivisie", 2026)
  # returns MatchResult list compatible with football_data_source.py

SETUP
  1. Register free at https://www.football-data.org/client/register
  2. Copy your API token
  3. Add to .env: FOOTBALL_DATA_ORG_KEY=<your-token>
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from data.football_data_source import MatchResult
from data.multi_source import SourceNoData
from data.retry import get

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://api.football-data.org/v4"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "football_data_org"
# Current-season results change daily; 6h TTL matches other fixture/result sources
MAX_AGE_SECONDS = 6 * 3600

# football-data.org competition codes (verified against their /competitions endpoint)
# Only the leagues in OLP XDV's WHITELISTED_LEAGUES are mapped here.
# Codes from: https://www.football-data.org/documentation/quickstart/competitions
COMPETITION_CODES = {
    "Premier League": "PL",
    "Championship": "ELC",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
    # Free tier covers 12 competitions; these are NOT on the free plan and will
    # 404. They stay mapped so a paid upgrade auto-enables them, but fail
    # silently through SourceNoData in the multi-source chain.
    "Scottish Premiership": "SPL",
    "Belgian Pro League": "BE1",  # BSA is Brazilian Serie A, not Belgian
    "Danish Superliga": "DKS",
    "Ekstraklasa": "PL1",
    "Austrian Bundesliga": "AT1",
    "HNL": "HNL",
    # Continental competitions
    "Champions League": "CL",
    # Europa League is NOT on the free tier; the code is "EL" but football-data.org
    # does not serve it at the free level (ELC is Championship, not Europa League).
    "Europa League": "EL",
    "Conference League": "UECL",
    "UEFA Super Cup": "USC",
}


def _get_key() -> str:
    key = os.environ.get("FOOTBALL_DATA_ORG_KEY")
    if not key:
        raise RuntimeError(
            "FOOTBALL_DATA_ORG_KEY not set. Register free at "
            "https://www.football-data.org/client/register and add to .env")
    return key


def _headers() -> dict:
    return {"X-Auth-Token": _get_key()}


def _cache_path(league: str, kind: str, season: int) -> Path:
    return CACHE_DIR / f"{league.replace(' ', '_')}_{kind}_{season}.json"


def _read_cache(path: Path) -> Optional[dict]:
    try:
        mtime = path.stat().st_mtime
        if time.time() - mtime > MAX_AGE_SECONDS:
            return None
    except OSError:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(path: Path, payload: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass  # cache write failure must never fail the fetch


def _parse_match(match: dict, league: str) -> Optional[MatchResult]:
    """football-data.org match object -> MatchResult (football-data.co.uk schema)."""
    try:
        # Only finished matches
        status = match.get("status", "")
        if status != "FINISHED":
            return None

        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        score = match.get("score", {})
        ft = score.get("fullTime", {})
        if ft.get("home") is None or ft.get("away") is None:
            return None

        fthg = int(ft["home"])
        ftag = int(ft["away"])
        ftr = "H" if fthg > ftag else ("A" if ftag > fthg else "D")

        # UTC date from match.utcDate (ISO 8601)
        utc_date = match.get("utcDate", "")
        if utc_date:
            kickoff = datetime.fromisoformat(utc_date.replace("Z", "+00:00")).date()
        else:
            kickoff = date.today()

        return MatchResult(
            league=league,
            date=kickoff.isoformat(),
            home_team=home,
            away_team=away,
            fthg=fthg,
            ftag=ftag,
            ftr=ftr,
            source="football-data.org",
            source_tier="T1",
        )
    except (KeyError, ValueError, TypeError):
        return None


def fetch_current_season_results(league: str, season: int,
                                  use_cache: bool = True,
                                  matchday: Optional[int] = None
                                  ) -> tuple[list[MatchResult], list[str]]:
    """Completed matches for a league in the current season.

    Returns (results, flags). Raises SourceNoData for uncovered leagues.
    `matchday` limits to a specific matchday (1-indexed); None = all played.
    """
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("football_data_org_source: 'requests' library required")
    if league not in COMPETITION_CODES:
        raise SourceNoData(f"'{league}' not mapped in COMPETITION_CODES")

    code = COMPETITION_CODES[league]
    cache_path = _cache_path(league, "results", season)
    payload = None

    if use_cache:
        payload = _read_cache(cache_path)
        if payload is not None:
            flags.append(f"{league}: results from football-data.org cache")

    if payload is None:
        params = {"season": season}
        if matchday is not None:
            params["matchday"] = matchday
        url = f"{API_BASE}/competitions/{code}/matches"
        resp = get(url, headers=_headers(), params=params, timeout=30)
        payload = resp.json()
        _write_cache(cache_path, payload)

    matches = payload.get("matches", [])
    results: list[MatchResult] = []
    for m in matches:
        parsed = _parse_match(m, league)
        if parsed:
            results.append(parsed)

    if results:
        flags.append(f"{league}: {len(results)} results from football-data.org (season {season})")
    else:
        flags.append(f"{league}: no finished matches yet from football-data.org")

    return results, flags


def fetch_standings(league: str, season: int,
                    use_cache: bool = True) -> tuple[dict, list[str]]:
    """Current standings for a league/season.

    Returns (standings_dict, flags). standings_dict maps team_name -> {position, points, played, gf, ga, gd, form}.
    """
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("football_data_org_source: 'requests' library required")
    if league not in COMPETITION_CODES:
        raise SourceNoData(f"'{league}' not mapped in COMPETITION_CODES")

    code = COMPETITION_CODES[league]
    cache_path = _cache_path(league, "standings", season)
    payload = None

    if use_cache:
        payload = _read_cache(cache_path)
        if payload is not None:
            flags.append(f"{league}: standings from football-data.org cache")

    if payload is None:
        url = f"{API_BASE}/competitions/{code}/standings"
        params = {"season": season}
        resp = get(url, headers=_headers(), params=params, timeout=30)
        payload = resp.json()
        _write_cache(cache_path, payload)

    out: dict = {}
    for standing in payload.get("standings", []):
        if standing.get("type") != "TOTAL":
            continue
        for row in standing.get("table", []):
            team_name = row["team"]["name"]
            out[team_name] = {
                "position": row.get("position"),
                "points": row.get("points"),
                "played": row.get("playedGames"),
                "won": row.get("won"),
                "draw": row.get("draw"),
                "lost": row.get("lost"),
                "gf": row.get("goalsFor"),
                "ga": row.get("goalsAgainst"),
                "gd": row.get("goalDifference"),
                "form": row.get("form"),
            }
    flags.append(f"{league}: standings for {len(out)} teams from football-data.org")
    return out, flags


def list_competitions() -> list[dict]:
    """All competitions the API serves (free probe, no quota cost on /competitions)."""
    if requests is None:
        raise RuntimeError("'requests' library required")
    resp = get(f"{API_BASE}/competitions", headers=_headers(), timeout=30)
    return resp.json().get("competitions", [])