"""
Final integrated fixtures agent with live SportyBet odds.

This agent:
1. Fetches fixtures from FlashScore (PRIMARY), BBC Sport, LiveScore, Sporting Life
2. Adds live fixtures from SportyBet API
3. Enhances fixtures with live odds from SportyBet when available
4. Applies the same verification logic (>=2 sources) as the original
6. Filters by deploy-eligible whitelist and league calendar
7. Stamps provenance on all fixtures
8. Displays clean output with odds when available

Based on the proven fixtures_agent.py with verified date filtering and verification.
"""
from __future__ import annotations

import sys
import json
import re
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
import os

# Load environment variables from .env file
from config import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Add project root

# Import ALL existing fixtures agent functions - we reuse the proven logic
from fixtures_agent_extended import (
    LEAGUE_SEASON_START,
    load_whitelist,
    _parse_date,
    check_league_calendar,
    verify_league_fixture,
    _flashscore_line_to_date,
    _find_flashscore_feed,
    fetch_flashscore,
    fetch_livescore,
    fetch_sportinglife,
    fetch_bbc,
    fetch_sportybet_cache,
    _apply_verification,
    print_fixtures,
    main as original_main
)

# Import new components for enhanced verification and data sources
try:
    from verification.fixture_matcher import match_fixtures, SourceFixture, unmatched_report
    FIXTURE_MATCHER_AVAILABLE = True
except Exception as e:
    print(f"[INFO] Fixture matcher not available: {e}")
    FIXTURE_MATCHER_AVAILABLE = False

try:
    from data.apifootball_client import APIFootballClient
    API_FOOTBALL_AVAILABLE = True
except Exception as e:
    print(f"[INFO] API-Football client not available: {e}")
    API_FOOTBALL_AVAILABLE = False
    APIFootballClient = None
    LEAGUE_ID_MAP = {}

# Import SportyBet live components with error handling
try:
    from booking.sportybet_client import SportyBetClient
    from booking.league_map import SPORTYBET_LEAGUES
    SPORTYBET_AVAILABLE = True
except Exception as e:
    print(f"[INFO] SportyBet live integration not available: {e}")
    SPORTYBET_AVAILABLE = False
    SportyBetClient = None
    SPORTYBET_LEAGUES = {}

# Import API-Football client for structured data
try:
    from data.apifootball_client import APIFootballClient, LEAGUE_ID_MAP
    API_FOOTBALL_AVAILABLE = True
except Exception as e:
    print(f"[INFO] API-Football client not available: {e}")
    API_FOOTBALL_AVAILABLE = False
    APIFootballClient = None
    LEAGUE_ID_MAP = {}

def fetch_sportybet_live_fixtures(today: str) -> List[Dict]:
    """
    Fetch live fixtures from SportyBet API for today.

    Returns fixtures in the same format as other sources.
    """
    if not SPORTYBET_AVAILABLE:
        return []

    rows: List[Dict] = []
    client = None

    try:
        # Conservative settings to prevent hanging
        client = SportyBetClient(timeout=8, delay=0.5)

        # Focus on priority leagues to limit API calls
        priority_leagues = [
            "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
            "Eredivisie", "Primeira Liga", "Belgian Pro League",
            "Scottish Premiership", "Swiss Super League", "Turkish Super Lig"
        ]

        for league_name in priority_leagues:
            if league_name not in SPORTYBET_LEAGUES:
                continue

            try:
                mapping = SPORTYBET_LEAGUES[league_name]
                rows.extend(client.get_fixtures_by_league(mapping, days_ahead=1))

            except Exception as e:
                print(f"[ERROR] Failed to fetch live fixtures for {league_name}: {e}")

    except Exception as e:
        print(f"[ERROR] SportyBet live integration failed: {e}")

    return rows