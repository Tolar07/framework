"""
Upcoming-fixtures source via API-Football (api-sports.io).
Football-Data.co.uk's historical CSVs only contain PLAYED matches, so a
separate source is needed for "what's coming up" — this is that source.

Why API-Football: free tier (100 requests/day — plenty for a few leagues,
a few times a week), broad league coverage including Scottish Premiership,
Eredivisie, Belgian Pro League, etc., clean JSON, no scraping.

SETUP (non-technical):
  1. Go to https://dashboard.api-football.com/register and create a free account
  2. Your API key is on your dashboard home page after signing up
  3. Set it as an environment variable before running anything that calls this
     module: in Claude Code, just say "set the API_FOOTBALL_KEY environment
     variable to <paste key>" and it will handle it for the session.

HR35: if the API call fails or a league isn't found, this raises rather than
returning an empty/guessed fixture list — callers must treat that as
NO DATA — PENDING at the league level, same as the results fetcher.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

API_BASE = "https://v3.football.api-sports.io"

# Verified API-Football league IDs (these specific numbers are widely and
# consistently documented — confident in them). For the rest of the ID401
# whitelist, resolve_league_id() below looks the ID up live from API-Football's
# own directory rather than guessing a plausible-looking number — HR35 applies
# to this module too.
LEAGUE_IDS = {
    "Scottish Premiership": 179,
    "Eredivisie": 88,
    "Belgian Pro League": 144,
    "Premier League": 39,
    "Championship": 40,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}

# Leagues whose ID401 name differs from API-Football's own name, so a plain
# search on our name finds nothing ("Danish Superliga" is just "Superliga"
# there, under country Denmark). Mapping to (api_name, country) lets
# resolve_league_id() ask for the exact record instead of fuzzy-searching —
# each pair below returns exactly one league from API-Football's directory.
LEAGUE_SEARCH = {
    "Danish Superliga": ("Superliga", "Denmark"),
    "Ekstraklasa": ("Ekstraklasa", "Poland"),
    "HNL": ("HNL", "Croatia"),
    "Primeira Liga": ("Primeira Liga", "Portugal"),
    "Champions League": ("UEFA Champions League", None),
    "Europa League": ("UEFA Europa League", None),
}

_resolved_cache: dict[str, int] = {}


def resolve_league_id(league: str) -> int:
    """Looks up a league's API-Football ID via their own /leagues endpoint,
    rather than hardcoding a number nobody's verified. Caches the result
    in-process so a scheduled run only pays this cost once per league.

    HR35: raises if the lookup is empty or ambiguous — never picks one of
    several candidates and never falls back to a plausible-looking number."""
    if league in LEAGUE_IDS:
        return LEAGUE_IDS[league]
    if league in _resolved_cache:
        return _resolved_cache[league]
    if requests is None:
        raise RuntimeError("requests not installed — cannot resolve league ID")

    api_name, country = LEAGUE_SEARCH.get(league, (league, None))
    params = {"name": api_name}
    if country:
        params["country"] = country

    key = _get_key()
    resp = requests.get(f"{API_BASE}/leagues", headers={"x-apisports-key": key},
                         params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    results = payload.get("response", [])
    if not results:
        raise ValueError(
            f"API-Football has no league matching '{league}' (looked up as "
            f"name={api_name!r}, country={country!r}) — check the name or "
            f"search manually at api-football.com/documentation-v3#tag/Leagues"
        )
    if len(results) > 1:
        # Don't silently pick one — surface the options so a human decides.
        names = [r["league"]["name"] + f" ({r['country']['name']})" for r in results]
        raise ValueError(
            f"Multiple API-Football leagues match '{league}': {names}. "
            f"Add the correct one to LEAGUE_IDS explicitly by ID."
        )
    league_id = results[0]["league"]["id"]
    _resolved_cache[league] = league_id
    return league_id


@dataclass
class UpcomingFixture:
    league: str
    date: str  # ISO
    home_team: str
    away_team: str
    kickoff_utc: str
    source: str = "api-football.com"
    source_tier: str = "T1"


def _get_key() -> str:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError(
            "API_FOOTBALL_KEY environment variable not set. Sign up free at "
            "https://dashboard.api-football.com/register, grab your key from "
            "the dashboard, and set it as an environment variable before "
            "running this."
        )
    return key


def fetch_upcoming(league: str, season: int, days_ahead: int = 14) -> list[UpcomingFixture]:
    """Returns upcoming (not-yet-played) fixtures for a whitelisted league over
    the next `days_ahead` days. Raises on any failure — never returns a guessed
    or partial list silently; caller decides how to surface that."""
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live fixtures")

    key = _get_key()
    league_id = resolve_league_id(league)  # raises clearly if unresolvable — never guesses
    today = date.today()
    end = today + timedelta(days=days_ahead)

    resp = requests.get(
        f"{API_BASE}/fixtures",
        headers={"x-apisports-key": key},
        params={
            "league": league_id,
            "season": season,
            "from": today.isoformat(),
            "to": end.isoformat(),
        },
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("errors"):
        raise RuntimeError(f"API-Football returned errors: {payload['errors']}")

    fixtures = []
    for item in payload.get("response", []):
        fx = item.get("fixture", {})
        teams = item.get("teams", {})
        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")
        if not home or not away:
            continue  # HR35 — incomplete record, skip rather than guess the team name
        fixtures.append(UpcomingFixture(
            league=league,
            date=fx.get("date", "")[:10],
            home_team=home,
            away_team=away,
            kickoff_utc=fx.get("date", ""),
        ))
    return fixtures


def as_pairs(fixtures: list[UpcomingFixture]) -> list[tuple[str, str]]:
    """Convenience adapter for orchestrator.run()'s upcoming_fixtures argument."""
    return [(f.home_team, f.away_team) for f in fixtures]
