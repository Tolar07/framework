"""
Concrete multi-source implementations for all pipeline data types.

Each data type gets multiple redundant providers with automatic failover.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from data.multi_source import (
    DataSource, MultiSource, build_multi_source, registry, as_source,
    SourceNoData,
)
from data.football_data_source import load_league as fd_load_league
from data import thesportsdb_fixtures as tsdb
from data import espn_source
from data import api_football_results as apif
from data import football_data_org_source as fdo
from data import xg_source
from data import live_scores as ls
from pipeline.odds import fetch_odds as odds_fetch_odds, fixtures_from_odds as odds_fixtures_from_odds

log = logging.getLogger("multi_source.concrete")

# =============================================================================
# FIXTURES MULTI-SOURCE
# =============================================================================

class TheSportsDBFixturesSource(DataSource):
    """TheSportsDB fixtures (season feed + eventsday fallback)."""

    def __init__(self):
        super().__init__("thesportsdb", priority=10, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        fixtures_season = kwargs.get("fixtures_season") or kwargs.get("season")
        days_ahead = kwargs.get("days_ahead", 14)
        from datetime import date
        # Try season feed first
        fixtures, skipped = tsdb.fetch_upcoming(league, fixtures_season, days_ahead=days_ahead)
        if fixtures:
            pairs = tsdb.as_pairs(fixtures)
            dates = {(f.home_team, f.away_team): f.date for f in fixtures}
            return {"fixtures": pairs, "dates": dates, "skipped": skipped, "source": "thesportsdb_season"}

        # If today is within the window and season feed is empty/lagging,
        # try eventsday for continental qualifiers (season feed lags weeks behind).
        # This catches CL/EL/ConfL qualifiers that the season feed hasn't indexed yet.
        from datetime import date
        today = str(date.today())
        day_fixtures = tsdb.fetch_today(league, today)
        if day_fixtures:
            pairs = tsdb.as_pairs(day_fixtures)
            dates = {(f.home_team, f.away_team): f.date for f in day_fixtures}
            return {"fixtures": pairs, "dates": dates, "skipped": 0, "source": "thesportsdb_eventsday"}

        # A legitimately-empty window is a valid answer for this league — fall
        # through to the next source WITHOUT tripping the shared circuit breaker.
        raise SourceNoData(f"thesportsdb: no fixtures for {league} (season={fixtures_season}, days={days_ahead})")


class OddsAPIFixturesSource(DataSource):
    """Fixtures derived from odds feed (last resort)."""

    def __init__(self):
        super().__init__("odds_api_fixtures", priority=20, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        days_ahead = kwargs.get("days_ahead", 14)
        pairs, dates, flags = odds_fixtures_from_odds(league, days_ahead=days_ahead)
        if not pairs:
            raise SourceNoData(f"odds_api: no fixtures for {league}")
        return {"fixtures": pairs, "dates": dates, "flags": flags, "source": "odds_api"}


class APIFootballFixturesSource(DataSource):
    """API-Football fixtures (paid plan only; free tier can't see current season)."""

    def __init__(self):
        super().__init__("api_football_fixtures", priority=15, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        # API-Football fixtures. The free tier CANNOT see the current season
        # (deterministic {'plan': ...} error, cached 7 days by the caller), so
        # this source honestly raises — it only becomes a real provider on a
        # paid plan. Wiring it here means the failover chain is complete: when
        # thesportsdb and the odds feed both fail, the paid-plan fallback is
        # already in place instead of a dead stub.
        league = kwargs["league"]
        season = kwargs.get("season") or kwargs.get("fixtures_season")
        season_year = kwargs.get("season_year") or kwargs.get("api_football_season")
        from data.fixtures_source import fetch_upcoming, as_pairs
        if season_year is None:
            try:
                season_year = (int(season[:2]) + 2000
                               if isinstance(season, str) and season.isdigit() else season)
            except Exception:
                season_year = None
        if season_year is None:
            raise SourceNoData(f"api_football: cannot resolve season {season!r} for {league}")
        fixtures = fetch_upcoming(league, season_year, days_ahead=kwargs.get("days_ahead", 14))
        if not fixtures:
            raise SourceNoData(f"api_football: no fixtures for {league} season {season_year}")
        pairs = as_pairs(fixtures)
        dates = {(f.home_team, f.away_team): f.date for f in fixtures}
        return {"fixtures": pairs, "dates": dates, "skipped": 0, "source": "api_football"}


class ESPNFixturesSource(DataSource):
    """ESPN scoreboard fixtures — key-free, covers continental comps + the
    no-TSDB-ID leagues (Austrian Bundesliga, HNL). Slice 1 of the ESPN
    redundancy layer (Architect order 2026-08-07)."""

    def __init__(self):
        super().__init__("espn", priority=15, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        fixtures_season = kwargs.get("fixtures_season") or kwargs.get("season")
        days_ahead = kwargs.get("days_ahead", 14)
        fixtures, skipped = espn_source.fetch_upcoming(
            league, fixtures_season, days_ahead=days_ahead)
        if not fixtures:
            raise SourceNoData(
                f"espn: no fixtures for {league} "
                f"(days={days_ahead}, skipped={len(skipped)})")
        pairs = espn_source.as_pairs(fixtures)
        dates = {(f.home_team, f.away_team): f.date for f in fixtures}
        return {"fixtures": pairs, "dates": dates, "skipped": skipped,
                "source": "espn"}


def build_fixtures_multi_source() -> MultiSource:
    """Build the fixtures multi-source with automatic failover.

    Order: API-Football (paid Pro primary; current season, widest window) ->
    TheSportsDB (season feed + eventsday fallback) -> ESPN scoreboard
    (key-free; covers continental + no-ID leagues) -> odds-derived fixtures.
    Each source's fetch is kwargs-tolerant so the shared MultiSource.fetch
    kwargs (league, season/fixtures_season, days_ahead) work for all of them.
    """
    return build_multi_source(
        "fixtures",
        [
            (APIFootballFixturesSource().fetch, "api_football_fixtures", 10),
            (TheSportsDBFixturesSource().fetch, "thesportsdb", 15),
            (ESPNFixturesSource().fetch, "espn", 20),
            (OddsAPIFixturesSource().fetch, "odds_api_fixtures", 30),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# HISTORICAL RESULTS MULTI-SOURCE
# =============================================================================

class FootballDataResultsSource(DataSource):
    """football-data.co.uk historical results (primary)."""

    def __init__(self):
        super().__init__("football_data", priority=10, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        season = kwargs.get("season") or kwargs.get("fixtures_season")
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise SourceNoData(f"football_data: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data"}


class FootballDataOrgResultsSource(DataSource):
    """football-data.org CURRENT-SEASON results — the P0 fix for promoted clubs.

    football-data.co.uk CSVs are end-of-season only; football-data.org serves
    live current-season results (updated daily). A promoted club (Cambuur,
    Beveren, Lommel, Horsens, etc.) becomes rateable through the existing DC
    machinery once it has ≥4 current-season matches — WITHOUT waiting for
    api-football paid activation. This source is keyless-ish (free registration),
    10 req/min, 100 req/day. Added 2026-08-12 as P0 gap fix."""

    def __init__(self):
        super().__init__("football_data_org", priority=12, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        # football-data.org provides CURRENT-SEASON results. The fit season
        # (e.g. '2526') is last season's data; the fixtures season ('2627')
        # is the current season with promoted clubs. Prefer fixtures_season.
        fixtures_season = kwargs.get("fixtures_season")
        season = kwargs.get("season")
        if fixtures_season and isinstance(fixtures_season, str) and len(fixtures_season) == 4 and fixtures_season.isdigit():
            # '2627' -> 2026 (football-data.org uses the start year)
            season_year = int(fixtures_season[:2]) + 2000
        elif isinstance(season, str) and len(season) == 4 and season.isdigit():
            # fallback: fit season '2526' -> 2025
            season_year = int(season[:2]) + 2000
        elif isinstance(season, int):
            season_year = season
        else:
            raise SourceNoData(f"football_data_org: cannot resolve season {season!r} for {league}")
        results, flags = fdo.fetch_current_season_results(league, season_year)
        if not results:
            raise SourceNoData(f"football_data_org: no results for {league} {season_year}")
        return {"results": results, "flags": flags, "source": "football_data_org"}


class APIFootballResultsSource(DataSource):
    """API-Football historical results (fallback for uncovered leagues)."""

    def __init__(self):
        super().__init__("api_football_results", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise SourceNoData(f"api_football_results: no results for {league} {season}")
        return {"results": results, "flags": flags, "source": "api_football_results"}


class TheSportsDBResultsSource(DataSource):
    """TheSportsDB historical results — last-resort history for leagues neither
    football-data nor API-Football can serve (HNL, Champions League, Europa
    League). Real current-season scores from the same feed that supplies the
    fixtures, so a rated fixture and its fit always agree on club names.

    Trust: this is SINGLE-SOURCE T2 reference data (ID404), never an
    F2-quorum VERIFIED second source — a model fitted here is usable for the
    board's reference scan, not calibration-grade."""

    def __init__(self):
        super().__init__("thesportsdb_results", priority=20, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        season = str(kwargs.get("season") or "")
        # The framework's season code is a two-year span ('2526' = 2025/26).
        # A bare year like '2025' would pass a length check but query the WRONG
        # TheSportsDB season (football-data and API-Football conventions differ),
        # so it is a contract error here, not something to guess — the caller
        # passes the framework code ('2526') explicitly.
        if len(season) != 4 or not season.isdigit():
            raise SourceNoData(
                f"thesportsdb_results: season {season!r} is not a '2526' code")
        if int(season[2:4]) != (int(season[:2]) + 1) % 100:
            raise SourceNoData(
                f"thesportsdb_results: season {season!r} is not a two-year span "
                f"code like '2526'")
        from data import thesportsdb_fixtures as tsdb
        results, skipped = tsdb.load_results(league, season)
        if not results:
            raise SourceNoData(f"thesportsdb_results: no results for {league} {season}")
        return {"results": results, "skipped": skipped,
                "source": "thesportsdb_results"}


def build_results_multi_source() -> MultiSource:
    """Build the historical results multi-source."""
    return build_multi_source(
        "historical_results",
        [
            (FootballDataResultsSource().fetch, "football_data", 10),
            (FootballDataOrgResultsSource().fetch, "football_data_org", 12),
            (APIFootballResultsSource().fetch, "api_football_results", 15),
            (TheSportsDBResultsSource().fetch, "thesportsdb_results", 20),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# ODDS MULTI-SOURCE (multi-region, multi-market)
# =============================================================================

class OddsAPISource(DataSource):
    """The-Odds-API live prices."""

    def __init__(self, regions: str = "uk", markets: str = "h2h,totals"):
        super().__init__(f"odds_api_{regions}_{markets}", priority=10, timeout=30.0)
        self.regions = regions
        self.markets = markets

    def fetch(self, league: str) -> list:
        fixtures, flags = odds_fetch_odds(league, regions=self.regions, markets=self.markets)
        if not fixtures:
            raise SourceNoData(f"odds_api({self.regions}): no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": f"odds_api_{self.regions}"}


class APIFootballOddsSource(DataSource):
    """API-Football free-plan odds — the fallback when The Odds API quota is
    spent (same bookmakers, 1X2 + totals, 100 req/day)."""

    def __init__(self):
        super().__init__("api_football_odds", priority=20, timeout=60.0)

    def fetch(self, league: str) -> list:
        from data.api_football_odds import fetch_odds as af_fetch
        fixtures, flags = af_fetch(league)
        if not fixtures:
            raise SourceNoData(f"api_football_odds: no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": "api_football_odds"}


def build_odds_multi_source(league: str) -> MultiSource:
    """Build odds multi-source for a specific league.

    Priority order:
    - If API-Football is on a PAID plan: API-Football (primary) -> Odds API UK -> Odds API EU
    - If API-Football is FREE: Odds API UK -> Odds API EU -> API-Football free (fallback)
    """
    from data import api_football_plan
    paid = api_football_plan.is_paid_plan()

    if paid:
        # PAID API-Football is primary (current season, wider date window, same bookmakers)
        sources = [
            (APIFootballOddsSource().fetch, "api_football_odds", 10),
            (OddsAPISource(regions="uk", markets="h2h,totals").fetch, "odds_api_uk", 15),
            (OddsAPISource(regions="eu", markets="h2h,totals").fetch, "odds_api_eu", 20),
        ]
    else:
        # FREE API-Football is last resort (today±1 window, 100 req/day)
        sources = [
            (OddsAPISource(regions="uk", markets="h2h,totals").fetch, "odds_api_uk", 10),
            (OddsAPISource(regions="eu", markets="h2h,totals").fetch, "odds_api_eu", 15),
            (APIFootballOddsSource().fetch, "api_football_odds", 20),
        ]

    return build_multi_source(
        f"odds_{league}",
        sources,
        max_retries_per_source=1,
    )


# =============================================================================
# xG MULTI-SOURCE
# =============================================================================

class UnderstatXGSource(DataSource):
    """Understat expected goals data."""

    def __init__(self):
        super().__init__("understat", priority=10, timeout=30.0)

    def fetch(self, league: str, season: str) -> dict:
        if not xg_source.is_covered(league):
            raise SourceNoData(f"understat: league {league} not covered")
        ratings = xg_source.fit_xg(league, season)
        if not ratings:
            raise SourceNoData(f"understat: no xG ratings for {league} {season}")
        return {"ratings": ratings, "source": "understat"}


# Alternative xG sources could be added here (e.g., StatsBomb open data, etc.)


def build_xg_multi_source() -> MultiSource:
    return build_multi_source(
        "xg",
        [
            (UnderstatXGSource().fetch, "understat", 10),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# CURRENT SEASON RESULTS (for settling legs)
# =============================================================================

class FootballDataLiveSource(DataSource):
    """football-data.co.uk current season (updated ~daily during season)."""

    def __init__(self):
        super().__init__("football_data_live", priority=10, timeout=30.0)

    def fetch(self, league: str, season: str | int) -> list:
        # The current_results MultiSource is shared by the web live-scores feed
        # (server.py passes season as int) and the daily pipeline (str like
        # "2626"). load_league subscripts season[:2]/season[2:], so coerce here
        # rather than letting an int crash the whole source.
        season = str(season)
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise SourceNoData(f"football_data_live: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data_live"}


class APIFootballLiveSource(DataSource):
    """API-Football current season results."""

    def __init__(self):
        super().__init__("api_football_live", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise SourceNoData(f"api_football_live: no results for {league} {season}")
        return {"results": results, "flags": flags, "source": "api_football_live"}


def build_current_results_multi_source() -> MultiSource:
    return build_multi_source(
        "current_results",
        [
            (FootballDataLiveSource().fetch, "football_data_live", 10),
            (APIFootballLiveSource().fetch, "api_football_live", 15),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# LIVE SCORES MULTI-SOURCE (in-play real-time scores for client dashboard)
# =============================================================================

class ESPNLiveScoresSource(DataSource):
    """ESPN scoreboard live scores (key-free, covers all WHITELISTED_LEAGUES)."""

    def __init__(self):
        super().__init__("espn_live_scores", priority=10, timeout=15.0)

    def fetch(self, league: str, day: str | None = None) -> dict:
        scores = ls.fetch_espn_live_scores(league, day)
        if not scores:
            raise SourceNoData(f"espn_live_scores: no scores for {league}")
        return {
            "scores": scores,
            "source": "espn",
        }


class APIFootballLiveScoresSource(DataSource):
    """API-Football live scores (paid plan fallback)."""

    def __init__(self):
        super().__init__("api_football_live_scores", priority=15, timeout=30.0)

    def fetch(self, league: str, day: str | None = None) -> dict:
        scores = ls.fetch_apif_live_scores(league, day)
        if not scores:
            raise SourceNoData(f"api_football_live_scores: no scores for {league}")
        return {
            "scores": scores,
            "source": "api_football",
        }


def build_live_scores_multi_source() -> MultiSource:
    return build_multi_source(
        "live_scores",
        [
            (ESPNLiveScoresSource().fetch, "espn_live_scores", 10),
            (APIFootballLiveScoresSource().fetch, "api_football_live_scores", 15),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# INITIALIZATION - register all multi-sources with global registry
# =============================================================================

def initialize_multi_sources():
    """Initialize and register all multi-sources with the global registry."""
    registry.register(build_fixtures_multi_source())
    registry.register(build_results_multi_source())
    registry.register(build_xg_multi_source())
    registry.register(build_current_results_multi_source())
    registry.register(build_live_scores_multi_source())
    # Odds sources are per-league, created on demand
    log.info("Multi-source registry initialized")


# Convenience accessors for orchestrator integration

def get_fixtures(league: str, fixtures_season: str, days_ahead: int = 14,
                 api_football_season: int | None = None) -> dict:
    """Fetch fixtures with automatic failover."""
    ms = registry.get_source("fixtures")
    if ms is None:
        ms = build_fixtures_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, fixtures_season=fixtures_season,
                      days_ahead=days_ahead, api_football_season=api_football_season)
    return result.data


def get_historical_results(league: str, season: str) -> list:
    """Fetch historical results with automatic failover."""
    ms = registry.get_source("historical_results")
    if ms is None:
        ms = build_results_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["results"]


def get_current_results(league: str, season: str) -> list:
    """Fetch current season results with automatic failover."""
    ms = registry.get_source("current_results")
    if ms is None:
        ms = build_current_results_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["results"]


def get_xg_ratings(league: str, season: str) -> dict:
    """Fetch xG ratings with automatic failover."""
    ms = registry.get_source("xg")
    if ms is None:
        ms = build_xg_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["ratings"]


def get_odds(league: str) -> list:
    """Fetch odds with automatic failover (per-league multi-source)."""
    # Build per-league odds source on demand
    return build_odds_multi_source(league).fetch(league=league).data["fixtures"]


def get_live_scores(league: str, day: str | None = None) -> dict:
    """Fetch live scores with automatic failover."""
    ms = registry.get_source("live_scores")
    if ms is None:
        ms = build_live_scores_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, day=day)
    return result.data


def get_all_health() -> dict:
    """Get health report for all registered sources."""
    return registry.get_health_report()