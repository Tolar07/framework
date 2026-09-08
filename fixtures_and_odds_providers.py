"""
Fixtures and odds provider fallback chain for OLP XDV
Uses enhanced multi-source chain for fixtures with automatic failover.
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

from data.multi_source_concrete import get_fixtures, get_odds
from pipeline.fixture_extraction import StageAOutput, VerifiedFixture

logger = logging.getLogger(__name__)


def get_fixtures_with_fallback(league: str, season: str, date_target: str = None) -> List[FixtureData]:
    """
    Get fixtures using the enhanced multi-source chain.
    Returns list of standardized FixtureData objects.
    """
    try:
        # Use the enhanced multi-source chain for fixtures
        result = get_fixtures(league=league, fixtures_season=season, days_ahead=14)

        # Convert the multi-source result to FixtureData objects
        fixtures = []
        fixture_pairs = result.get("fixtures", [])
        dates_dict = result.get("dates", {})

        for i, (home_team, away_team) in enumerate(fixture_pairs):
            # Generate a fixture ID
            fixture_id = f"{home_team}_{away_team}_{league}_{i}"

            # Get the date for this fixture
            fixture_date = dates_dict.get((home_team, away_team), str(date.today()))

            fixture = FixtureData(
                fixture_id=fixture_id,
                home_team=home_team,
                away_team=away_team,
                date=fixture_date,
                league=league,
                status="SCHEDULED"
            )
            fixtures.append(fixture)

        logger.info(f"Successfully obtained {len(fixtures)} fixtures for {league} from multi-source chain")
        return fixtures

    except Exception as e:
        logger.error(f"All fixture sources failed for {league}: {e}")
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