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
import json
import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

from data.retry import get_protected
from data import api_football_plan

API_BASE = "https://v3.football.api-sports.io"

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "api_football_fixtures"
# Fixtures are the orchestrator's THIRD fallback (after TheSportsDB and the
# odds feed) and it costs a network round-trip per league per run on days the
# earlier sources find nothing. A fixture schedule is stable within a day, so
# the response is cached for 6h — warm runs pay nothing, a reschedule is caught
# within the window.
FIXTURES_MAX_AGE_SECONDS = 6 * 3600
# The free API-Football plan CANNOT see the current season — the API returns a
# deterministic `{'plan': 'Free plans...'}` error. Retrying that every run is
# ~0.6s of guaranteed-dead network per league (measured ~8s/run). Because the
# restriction is stable for the whole season, the FAILURE is cached for 7 days;
# a plan upgrade surfaces within a week. Transient errors are NOT cached.
PLAN_ERROR_TTL_SECONDS = 7 * 24 * 3600

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
    "La Liga 2": 141,
    "Serie B": 136,
    "Ligue 2": 62,
    "DFB-Pokal": 151,
    "Copa del Rey": 154,
    "Coppa Italia": 152,
    "Coupe de France": 66,
    "FA Cup": 45,
    "KNVB Beker": 97,
    "EFL Cup": 48,
}

# Leagues whose ID401 name differs from API-Football's own name, so a plain
# search on our name finds nothing ("Danish Superliga" is just "Superliga"
# there, under country Denmark). Mapping to (api_name, country) lets
# resolve_league_id() ask for the exact record instead of fuzzy-searching —
# each pair below returns exactly one league from API-Football's directory.
# Extended 2026-08-20 with all whitelisted leagues per error log analysis.
LEAGUE_SEARCH = {
    "Danish Superliga": ("Superliga", "Denmark"),
    "Ekstraklasa": ("Ekstraklasa", "Poland"),
    "HNL": ("HNL", "Croatia"),
    "Primeira Liga": ("Primeira Liga", "Portugal"),
    "Champions League": ("UEFA Champions League", None),
    "Europa League": ("UEFA Europa League", None),
    "Conference League": ("UEFA Europa Conference League", None),
    "Austrian Bundesliga": ("Bundesliga", "Austria"),
    "Armenian Premier League": ("Premier League", "Armenia"),
    "Estonian Meistriliiga": ("Meistriliiga", "Estonia"),
    "Faroe Islands Premier League": ("Premier League", "Faroe Islands"),
    "Finnish Veikkausliiga": ("Veikkausliiga", "Finland"),
    "Georgian Erovnuli Liga": ("Erovnuli Liga", "Georgia"),
    "Greek Super League": ("Super League", "Greece"),
    "Hungarian NB I": ("NB I", "Hungary"),
    "Israeli Premier League": ("Premier League", "Israel"),
    "Kosovan Superliga": ("Superleague", "Kosovo"),
    "Latvian Virsliga": ("Virsliga", "Latvia"),
    "Maltese Premier League": ("Premier League", "Malta"),
    "Northern Irish Premiership": ("Premiership", "Northern Ireland"),
    "Norwegian Eliteserien": ("Eliteserien", "Norway"),
    "Russian Premier League": ("Premier League", "Russia"),
    "Slovenian PrvaLiga": ("PrvaLiga", "Slovenia"),
    "Swedish Allsvenskan": ("Allsvenskan", "Sweden"),
    "Swiss Super League": ("Super League", "Switzerland"),
    "Turkish Super Lig": ("Süper Lig", "Turkey"),
    "Welsh Premier League": ("Premier League", "Wales"),
    "Albanian Superliga": ("Superliga", "Albania"),
    "Andorran Primera División": ("Primera Divisió", "Andorra"),
    "Azerbaijani Premyer Liqa": ("Premyer Liqa", "Azerbaijan"),
    "Belarusian Premier League": ("Premier League", "Belarus"),
    "Bosnian Premier League": ("Premier League", "Bosnia and Herzegovina"),
    "EFL Cup": ("League Cup", "England"),
    "La Liga 2": ("Segunda División", "Spain"),
    "Ligue 2": ("Ligue 2", "France"),
    "Serie B": ("Serie B", "Italy"),
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
    resp = get_protected(f"{API_BASE}/leagues", breaker_name="api_football",
                         headers={"x-apisports-key": key},
                         params=params, timeout=20)
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


def _cache_path(league: str, season: int, days_ahead: int) -> Path:
    return CACHE_DIR / f"{league.replace(' ', '_')}_{season}_{days_ahead}d.json"


def _read_cache(league: str, season: int, days_ahead: int
                ) -> tuple[Optional[list[dict]], Optional[str]]:
    """Returns (items, error) — at most one non-None. Items are fresh for the
    schedule TTL; a cached plan-restriction error for the (longer) plan TTL."""
    p = _cache_path(league, season, days_ahead)
    if not p.exists():
        return None, None
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None
    age = time.time() - blob.get("fetched_at", 0)
    if "items" in blob:
        if age > FIXTURES_MAX_AGE_SECONDS:
            return None, None  # stale fixtures are REJECTED, not served
        return blob.get("items"), None
    if "error" in blob:
        if age > PLAN_ERROR_TTL_SECONDS:
            return None, None  # restriction may have lifted — re-check
        return None, blob.get("error")
    return None, None


def _write_cache(league: str, season: int, days_ahead: int,
                 items: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(league, season, days_ahead).write_text(
        json.dumps({"fetched_at": time.time(), "items": items}), encoding="utf-8")


def _write_error_cache(league: str, season: int, days_ahead: int,
                       error: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(league, season, days_ahead).write_text(
        json.dumps({"fetched_at": time.time(), "error": error}), encoding="utf-8")


def fetch_upcoming(league: str, season: int, days_ahead: int = 14) -> list[UpcomingFixture]:
    """Returns upcoming (not-yet-played) fixtures for a whitelisted league over
    the next `days_ahead` days. Raises on any failure — never returns a guessed
    or partial list silently; caller decides how to surface that.

    The raw response is cached per (league, season, days_ahead) for 6 hours, so
    the orchestrator's third-level fallback stops costing a network round-trip
    for every league on every run (measured ~0.7s x 15 on quiet days). On a
    cache hit no API key is needed."""
    if requests is None:
        raise RuntimeError("requests not installed — cannot fetch live fixtures")

    cached_items, cached_error = _read_cache(league, season, days_ahead)
    if cached_items is not None:
        return _parse_items(league, cached_items)
    # PLAN-GATED (Architect 2026-08-12): a cached plan-restriction error was
    # recorded when the key was FREE. On a PAID key that restriction no longer
    # applies — serving the stale error would hide the paid upgrade for up to
    # 7 days. A paid key ignores cached plan errors and re-fetches. Non-plan
    # errors are served as before (they are real failures, not plan gates).
    if cached_error is not None and not (
            api_football_plan.is_paid_plan()
            and "plan" in str(cached_error).lower()):
        raise RuntimeError(cached_error)

    key = _get_key()
    league_id = resolve_league_id(league)  # raises clearly if unresolvable — never guesses
    today = date.today()
    end = today + timedelta(days=days_ahead)

    resp = get_protected(
        f"{API_BASE}/fixtures",
        breaker_name="api_football",
        headers={"x-apisports-key": key},
        params={
            "league": league_id,
            "season": season,
            "from": today.isoformat(),
            "to": end.isoformat(),
        },
        timeout=20,
    )
    payload = resp.json()

    if payload.get("errors"):
        err = f"API-Football returned errors: {payload['errors']}"
        # A plan restriction is deterministic for the season — cache the FAILURE
        # so it is paid once a week, not every run. Transient errors are not
        # cached (a retry may legitimately succeed). On a PAID key a "plan"
        # error is anomalous, never a deterministic gate — do NOT cache it,
        # or the next run would serve a week-old error that hides the upgrade.
        if "plan" in str(payload["errors"]).lower() \
                and not api_football_plan.is_paid_plan():
            _write_error_cache(league, season, days_ahead, err)
        raise RuntimeError(err)

    items = payload.get("response", [])
    _write_cache(league, season, days_ahead, items)
    return _parse_items(league, items)


def _parse_items(league: str, items: list[dict]) -> list[UpcomingFixture]:
    fixtures = []
    for item in items:
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
