"""
Fixtures and odds provider fallback chain for OLP XDV
Priority: API-Football (primary, structured JSON) ->
TheSportsDB (fallback) -> SportyBet (last resort)
Implements provider fallback with graceful degradation per HR35.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests

from data.multi_source_concrete import get_odds as multi_get_odds
from data.thesportsdb_fixtures import fetch_upcoming as tsdb_get_fixtures
from booking.bridge import load_all_sportybet_fixtures
from pipeline.fixture_extraction import StageAOutput, VerifiedFixture

logger = logging.getLogger(__name__)


@dataclass
class FixtureData:
    """Standardized fixture data structure across providers."""
    fixture_id: str
    home_team: str
    away_team: str
    date: str  # ISO format
    league: str
    status: str = "SCHEDULED"
    odds: Optional[Dict[str, Any]] = None


@dataclass
class ProviderResult:
    """Result from a provider attempt."""
    success: bool
    data: List[FixtureData] = None
    error: Optional[str] = None
    provider_name: str = ""


class ProviderChain:
    """Generic provider chain with fallback logic and retry mechanism."""

    def __init__(self, providers: List[tuple], max_retries: int = 2, retry_delay: float = 1.0):
        """
        Initialize provider chain.

        Args:
            providers: List of (provider_name, provider_func) tuples in priority order
            max_retries: Max retries per provider before falling back
            retry_delay: Delay between retries in seconds
        """
        self.providers = providers
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def execute(self, *args, **kwargs) -> ProviderResult:
        """Execute provider chain with fallback."""
        last_error = None

        for provider_name, provider_func in self.providers:
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(f"Trying provider '{provider_name}' (attempt {attempt + 1})")
                    result = provider_func(*args, **kwargs)

                    if result and len(result) > 0:
                        logger.info(f"Provider '{provider_name}' succeeded with {len(result)} fixtures")
                        return ProviderResult(
                            success=True,
                            data=result,
                            provider_name=provider_name
                        )
                    else:
                        logger.warning(f"Provider '{provider_name}' returned empty data")

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Provider '{provider_name}' failed (attempt {attempt + 1}): {e}")

                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                    else:
                        break  # Move to next provider

        # All providers failed
        return ProviderResult(
            success=False,
            error=last_error or "All providers failed",
            provider_name="chain"
        )


def get_api_football_fixtures(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Fetch fixtures from API-Football (primary source).
    Returns structured JSON data.
    """
    try:
        # This would integrate with the actual API-Football client
        # For now, we'll use the existing multi-source concrete as placeholder
        # which already implements API-Football -> Odds API UK -> Odds API EU
        fixtures_data = multi_get_odds(league)

        fixtures = []
        for fx in fixtures_data:
            fixture = FixtureData(
                fixture_id=getattr(fx, 'fixture_id', str(hash(fx.home_team + fx.away_team + fx.date))),
                home_team=getattr(fx, 'home_team', 'Unknown'),
                away_team=getattr(fx, 'away_team', 'Unknown'),
                date=getattr(fx, 'date', date_target or str(date.today())),
                league=league,
                status=getattr(fx, 'status', 'SCHEDULED'),
                odds={
                    'home_win': getattr(fx, 'home_win', None),
                    'draw': getattr(fx, 'draw', None),
                    'away_win': getattr(fx, 'away_win', None),
                    'over_2_5': getattr(fx, 'over_2_5', None),
                    'under_2_5': getattr(fx, 'under_2_5', None),
                    'btts_yes': getattr(fx, 'btts_yes', None),
                    'btts_no': getattr(fx, 'btts_no', None)
                }
            )
            fixtures.append(fixture)

        return fixtures

    except Exception as e:
        logger.error(f"API-Football fixtures failed: {e}")
        raise


def get_the_sports_db_fixtures(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Fetch fixtures from TheSportsDB (fallback source).
    """
    try:
        fixtures_data, skipped = tsdb_get_fixtures(league, season, date_target)

        fixtures = []
        for fix in fixtures_data:
            fixture = FixtureData(
                fixture_id=str(fix.id if hasattr(fix, 'id') else hash(fix.home_team + fix.away_team + fix.date)),
                home_team=getattr(fix, 'home_team', 'Unknown'),
                away_team=getattr(fix, 'away_team', 'Unknown'),
                date=getattr(fix, 'date', date_target or str(date.today())),
                league=league,
                status=getattr(fix, 'status', 'SCHEDULED')
            )
            fixtures.append(fixture)

        if skipped:
            logger.warning(f"TheSportsDB skipped {len(skipped)} fixtures for {league}")

        return fixtures

    except Exception as e:
        logger.error(f"TheSportsDB fixtures failed: {e}")
        raise


def get_sportybet_fixtures(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Fetch fixtures from SportyBet (last resort).
    Uses headless Chromium pass as backup.
    """
    try:
        # This uses the existing SportyBet bridge with caching
        sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=1, leagues=[league])
        fixtures_data = sb_fixtures_by_league.get(league, [])

        fixtures = []
        for fix in fixtures_data:
            fixture = FixtureData(
                fixture_id=str(getattr(fix, 'fixture_id', hash(fix.home_team + fix.away_team + fix.date))),
                home_team=getattr(fix, 'home_team', 'Unknown'),
                away_team=getattr(fix, 'away_team', 'Unknown'),
                date=getattr(fix, 'date', date_target or str(date.today())),
                league=league,
                status=getattr(fix, 'status', 'SCHEDULED'),
                odds={
                    'home_win': getattr(fix, 'home_price', None),
                    'draw': getattr(fix, 'draw_price', None),
                    'away_win': getattr(fix, 'away_price', None)
                } if hasattr(fix, 'home_price') else None
            )
            fixtures.append(fixture)

        return fixtures

    except Exception as e:
        logger.error(f"SportyBet fixtures failed: {e}")
        raise


# Provider chain instances
FIXTURES_PROVIDER_CHAIN = ProviderChain([
    ("API-Football", get_api_football_fixtures),
    ("TheSportsDB", get_the_sports_db_fixtures),
    ("SportyBet", get_sportybet_fixtures)
])

ODDS_PROVIDER_CHAIN = ProviderChain([
    ("API-Football", lambda league, season, date=None: multi_get_odds(league)),  # Already includes fallback
    ("TheSportsDB", lambda league, season, date=None: []),  # Placeholder - TSDB doesn't provide odds
    ("SportyBet", lambda league, season, date=None: [])   # Placeholder - would need odds extraction
])


def get_fixtures_with_fallback(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Get fixtures using the provider fallback chain.
    Returns list of standardized FixtureData objects.
    """
    result = FIXTURES_PROVIDER_CHAIN.execute(league, season, date_target)

    if result.success:
        logger.info(f"Successfully obtained {len(result.data)} fixtures from {result.provider_name}")
        return result.data
    else:
        logger.error(f"All fixture providers failed: {result.error}")
        # Return empty list per HR35 - never fail the run, degrade gracefully
        return []


def get_odds_with_fallback(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Get odds using the provider fallback chain.
    Returns list of standardized FixtureData objects with odds.
    """
    result = ODDS_PROVIDER_CHAIN.execute(league, season, date_target)

    if result.success:
        logger.info(f"Successfully obtained odds for {len(result.data)} fixtures from {result.provider_name}")
        return result.data
    else:
        logger.error(f"All odds providers failed: {result.error}")
        # Return empty list per HR35 - never fail the run, degrade gracefully
        return []


def get_fixtures_for_run_daily(leagues: List[str], season: str, fixtures_season: str = None,
                              date_target: str = None, days_ahead: int = 0) -> Dict[str, List[FixtureData]]:
    """
    Get fixtures for multiple leagues, used by run_daily.py
    Returns dictionary mapping league -> fixtures list
    """
    all_fixtures = {}

    for league in leagues:
        try:
            fixtures = get_fixtures_with_fallback(league, season, date_target)
            all_fixtures[league] = fixtures
            logger.info(f"League {league}: {len(fixtures)} fixtures obtained")
        except Exception as e:
            logger.error(f"Failed to get fixtures for league {league}: {e}")
            all_fixtures[league] = []  # Graceful degradation

    return all_fixtures


if __name__ == "__main__":
    # Test the provider chain
    logging.basicConfig(level=logging.INFO)

    # Test with a sample league
    test_leagues = ["Bundesliga"]
    test_season = "2026"

    fixtures = get_fixtures_for_run_daily(test_leagues, test_season, days_ahead=1)

    for league, fix_list in fixtures.items():
        print(f"{league}: {len(fix_list)} fixtures")
        for fix in fix_list[:3]:  # Show first 3
            print(f"  {fix.home_team} vs {fix.away_team} on {fix.date}")