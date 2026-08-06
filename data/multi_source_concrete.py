"""
Concrete multi-source implementations for all pipeline data types.

Each data type gets multiple redundant providers with automatic failover.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from data.multi_source import (
    DataSource, MultiSource, build_multi_source, registry, as_source
)
from data.football_data_source import load_league as fd_load_league
from data import thesportsdb_fixtures as tsdb
from data import api_football_results as apif
from data import xg_source
from pipeline.odds import fetch_odds as odds_fetch_odds, fixtures_from_odds as odds_fixtures_from_odds

log = logging.getLogger("multi_source.concrete")

# =============================================================================
# FIXTURES MULTI-SOURCE
# =============================================================================

class TheSportsDBFixturesSource(DataSource):
    """TheSportsDB fixtures (season feed + eventsday fallback)."""

    def __init__(self):
        super().__init__("thesportsdb", priority=10, timeout=25.0)

    def fetch(self, league: str, fixtures_season: str, days_ahead: int = 14) -> list:
        from datetime import date
        # Try season feed first
        fixtures, skipped = tsdb.fetch_upcoming(league, fixtures_season, days_ahead=days_ahead)
        if fixtures:
            pairs = tsdb.as_pairs(fixtures)
            dates = {(f.home_team, f.away_team): f.date for f in fixtures}
            return {"fixtures": pairs, "dates": dates, "skipped": skipped, "source": "thesportsdb_season"}

        # If today-only and season feed empty, try eventsday
        if days_ahead == 0:
            day = str(date.today())
            day_fixtures = tsdb.fetch_today(league, day)
            if day_fixtures:
                pairs = tsdb.as_pairs(day_fixtures)
                dates = {(f.home_team, f.away_team): f.date for f in day_fixtures}
                return {"fixtures": pairs, "dates": dates, "skipped": 0, "source": "thesportsdb_eventsday"}

        raise RuntimeError(f"thesportsdb: no fixtures for {league} (season={fixtures_season}, days={days_ahead})")


class OddsAPIFixturesSource(DataSource):
    """Fixtures derived from odds feed (last resort)."""

    def __init__(self):
        super().__init__("odds_api_fixtures", priority=20, timeout=30.0)

    def fetch(self, league: str, days_ahead: int = 14) -> list:
        pairs, dates, flags = odds_fixtures_from_odds(league, days_ahead=days_ahead)
        if not pairs:
            raise RuntimeError(f"odds_api: no fixtures for {league}")
        return {"fixtures": pairs, "dates": dates, "flags": flags, "source": "odds_api"}


class APIFootballFixturesSource(DataSource):
    """API-Football fixtures (paid plan only; free tier can't see current season)."""

    def __init__(self):
        super().__init__("api_football_fixtures", priority=15, timeout=25.0)

    def fetch(self, league: str, season: int, days_ahead: int = 14) -> list:
        # API-Football fixtures would go here - for now this documents the source
        # Free tier returns deterministic {'plan': ...} error which is cached for 7 days
        raise RuntimeError(f"api_football: not implemented for free tier (league={league}, season={season})")


def build_fixtures_multi_source() -> MultiSource:
    """Build the fixtures multi-source with automatic failover."""
    return build_multi_source(
        "fixtures",
        [
            (TheSportsDBFixturesSource().fetch, "thesportsdb_season", 10),
            (TheSportsDBFixturesSource().fetch, "thesportsdb_eventsday", 11),  # only used when days_ahead=0
            (OddsAPIFixturesSource().fetch, "odds_api_fixtures", 20),
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

    def fetch(self, league: str, season: str) -> list:
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise RuntimeError(f"football_data: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data"}


class APIFootballResultsSource(DataSource):
    """API-Football historical results (fallback for uncovered leagues)."""

    def __init__(self):
        super().__init__("api_football_results", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise RuntimeError(f"api_football_results: no results for {league} {season}")
        return {"results": results, "flags": flags, "source": "api_football_results"}


def build_results_multi_source() -> MultiSource:
    """Build the historical results multi-source."""
    return build_multi_source(
        "historical_results",
        [
            (FootballDataResultsSource().fetch, "football_data", 10),
            (APIFootballResultsSource().fetch, "api_football_results", 15),
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
            raise RuntimeError(f"odds_api({self.regions}): no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": f"odds_api_{self.regions}"}


def build_odds_multi_source(league: str) -> MultiSource:
    """Build odds multi-source for a specific league."""
    # UK + EU regions for redundancy
    return build_multi_source(
        f"odds_{league}",
        [
            (OddsAPISource(regions="uk", markets="h2h,totals").fetch, "odds_api_uk", 10),
            (OddsAPISource(regions="eu", markets="h2h,totals").fetch, "odds_api_eu", 15),
        ],
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
            raise RuntimeError(f"understat: league {league} not covered")
        ratings = xg_source.fit_xg(league, season)
        if not ratings:
            raise RuntimeError(f"understat: no xG ratings for {league} {season}")
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

    def fetch(self, league: str, season: str) -> list:
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise RuntimeError(f"football_data_live: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data_live"}


class APIFootballLiveSource(DataSource):
    """API-Football current season results."""

    def __init__(self):
        super().__init__("api_football_live", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise RuntimeError(f"api_football_live: no results for {league} {season}")
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
# INITIALIZATION - register all multi-sources with global registry
# =============================================================================

def initialize_multi_sources():
    """Initialize and register all multi-sources with the global registry."""
    registry.register(build_fixtures_multi_source())
    registry.register(build_results_multi_source())
    registry.register(build_xg_multi_source())
    registry.register(build_current_results_multi_source())
    # Odds sources are per-league, created on demand
    log.info("Multi-source registry initialized")


# Convenience accessors for orchestrator integration

def get_fixtures(league: str, fixtures_season: str, days_ahead: int = 14) -> dict:
    """Fetch fixtures with automatic failover."""
    ms = registry.get_source("fixtures")
    if ms is None:
        ms = build_fixtures_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, fixtures_season=fixtures_season, days_ahead=days_ahead)
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


def get_all_health() -> dict:
    """Get health report for all registered sources."""
    return registry.get_health_report()