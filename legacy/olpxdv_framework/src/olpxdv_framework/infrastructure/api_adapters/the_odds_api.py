"""
The Odds API adapter for fetching sports data and odds.
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

import httpx

from olpxdv_framework.infrastructure.api_adapters.base_adapter import BaseAPIAdapter, APIError, RateLimitError, AuthenticationError, DataNotFoundError
from olpxdv_framework.domain.models import Fixture, Odds, MarketType, Team, LeagueTier, FixtureStatus
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class TheOddsAPIAdapter(BaseAPIAdapter):
    """
    Adapter for The Odds API (https://the-odds-api.com/)
    """

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.api_key = self.settings.api.odds_api_key
        self.base_url = self.settings.api.odds_api_base_url
        self.timeout = self.settings.api.odds_api_timeout
        self.rate_limit = self.settings.api.odds_api_rate_limit

        # Request tracking for rate limiting
        self.request_count = 0
        self.last_reset = datetime.utcnow()

        # Sport to league mapping (simplified)
        self.sport_mapping = {
            'soccer_epl': ('Premier League', LeagueTier.TIER_A),
            'soccer_championship': ('Championship', LeagueTier.TIER_B),
            'soccer_bundesliga': ('Bundesliga', LeagueTier.TIER_A),
            'soccer_serie_a': ('Serie A', LeagueTier.TIER_A),
            'soccer_ligue_1': ('Ligue 1', LeagueTier.TIER_A),
            'soccer_laliga': ('La Liga', LeagueTier.TIER_A),
            'soccer_primeira_liga': ('Primeira Liga', LeagueTier.TIER_B),
            'soccer_eredivisie': ('Eredivisie', LeagueTier.TIER_B),
            'soccer_scottish_premiership': ('Scottish Premiership', LeagueTier.TIER_B),
            'soccer_belgian_pro_league': ('Belgian Pro League', LeagueTier.TIER_B),
            'soccer_turkish_super_lig': ('Turkish Super Lig', LeagueTier.TIER_B),
            'soccer_swiss_super_league': ('Swiss Super League', LeagueTier.TIER_B),
            'soccer_russian_premier_league': ('Russian Premier League', LeagueTier.TIER_B),
        }

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make a rate-limited request to The Odds API.
        """
        # Rate limiting check
        now = datetime.utcnow()
        if (now - self.last_reset).seconds >= 60:
            self.request_count = 0
            self.last_reset = now

        if self.request_count >= self.rate_limit:
            raise RateLimitError(f"The Odds API rate limit exceeded: {self.rate_limit} requests/minute")

        # Make request
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        if self.api_key:
            params = params or {}
            params['apiKey'] = self.api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params, headers=headers)
                self.request_count += 1

                if response.status_code == 401:
                    raise AuthenticationError("The Odds API authentication failed")
                elif response.status_code == 429:
                    raise RateLimitError("The Odds API rate limit exceeded")
                elif response.status_code == 404:
                    raise DataNotFoundError("The Odds API data not found")
                elif response.status_code >= 400:
                    raise APIError(f"The Odds API error: {response.status_code}")

                return response.json()
            except httpx.TimeoutException:
                raise APIError("The Odds API request timeout")
            except httpx.RequestError as e:
                raise APIError(f"The Odds API request failed: {e}")

    async def get_upcoming_fixtures(
        self,
        days_ahead: int = 7,
        leagues: Optional[List[str]] = None
    ) -> List[Fixture]:
        """
        Get upcoming soccer fixtures from The Odds API.
        """
        if not self.api_key:
            self.logger.warning("The Odds API key not configured")
            return []

        try:
            # The Odds API uses sport keys instead of league names directly
            # We'll fetch for multiple sports and filter
            sports_to_check = list(self.sport_mapping.keys())

            all_fixtures = []

            for sport in sports_to_check:
                try:
                    endpoint = f"sports/{sport}/odds"
                    params = {
                        'regions': 'uk',  # UK bookmakers
                        'markets': 'h2h,over_under,btts',  # Head-to-head, Over/Under, BTTS
                        'oddsFormat': 'decimal',
                        'dateFormat': 'iso'
                    }

                    data = await self._make_request(endpoint, params)

                    for event in data:
                        fixture = self._parse_fixture_from_event(event, sport)
                        if fixture:
                            # Filter by leagues if specified
                            if leagues is None or fixture.league in leagues:
                                all_fixtures.append(fixture)

                except Exception as e:
                    self.logger.warning(f"Failed to fetch fixtures for sport {sport}: {e}")
                    continue

            # Filter by date range
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            filtered_fixtures = [
                f for f in all_fixtures
                if f.match_date <= cutoff_date
            ]

            return filtered_fixtures

        except Exception as e:
            self.logger.error(f"Error fetching upcoming fixtures from The Odds API: {e}")
            return []

    def _parse_fixture_from_event(self, event: dict, sport_key: str) -> Optional[Fixture]:
        """
        Parse a fixture from The Odds API event data.
        """
        try:
            # Get league info from sport mapping
            league_name, league_tier = self.sport_mapping.get(sport_key, (sport_key, LeagueTier.TIER_C))

            # Parse teams
            home_team = Team(
                id=f"{event['home_team']}_{event['sport_key']}",
                name=event['home_team'],
                short_name=event['home_team'][:3].upper() if len(event['home_team']) >= 3 else event['home_team']
            )

            away_team = Team(
                id=f"{event['away_team']}_{event['sport_key']}",
                name=event['away_team'],
                short_name=event['away_team'][:3].upper() if len(event['away_team']) >= 3 else event['away_team']
            )

            # Parse match date
            match_date = datetime.fromisoformat(event['commence_time'].replace('Z', '+00:00'))

            # Create fixture
            fixture = Fixture(
                id=event['id'],
                home_team=home_team,
                away_team=away_team,
                league=league_name,
                league_tier=league_tier,
                match_date=match_date,
                status=FixtureStatus.SCHEDULED
            )

            return fixture

        except KeyError as e:
            self.logger.warning(f"Missing required field in The Odds API event: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Error parsing fixture from The Odds API event: {e}")
            return None

    async def get_odds_for_fixture(
        self,
        fixture_id: str,
        market_types: List[MarketType]
    ) -> List[Odds]:
        """
        Get odds for a specific fixture from The Odds API.
        """
        if not self.api_key:
            self.logger.warning("The Odds API key not configured")
            return []

        try:
            endpoint = f"sports/soccer_epl/odds"  # We need to find the right sport
            # In a real implementation, we'd first lookup the sport for this fixture
            # For now, we'll use a simplified approach

            params = {
                'regions': 'uk',
                'markets': self._market_types_to_odds_api(market_types),
                'oddsFormat': 'decimal',
                'dateFormat': 'iso'
            }

            # Note: The Odds API doesn't have a direct endpoint for a single fixture by ID
            # We would need to get all odds and filter, or use a different approach
            # This is a limitation of the simplified implementation

            data = await self._make_request(endpoint, params)

            odds_list = []
            for event in data:
                if event['id'] == fixture_id:
                    odds_list.extend(self._parse_odds_from_event(event))
                    break

            return odds_list

        except Exception as e:
            self.logger.error(f"Error fetching odds for fixture {fixture_id} from The Odds API: {e}")
            return []

    def _market_types_to_odds_api(self, market_types: List[MarketType]) -> str:
        """
        Convert MarketType enum to The Odds API market string.
        """
        market_mapping = {
            MarketType.MATCH_ODDS: 'h2h',
            MarketType.OVER_UNDER: 'over_under',
            MarketType.BTTS: 'btts',
            MarketType.DOUBLE_CHANCE: 'double_chance',
            MarketType.ASIAN_HANDICAP: 'asian_handicap',
            MarketType.CORRECT_SCORE: 'correct_score'
        }

        markets = [market_mapping.get(mt, 'h2h') for mt in market_types]
        return ','.join(markets)

    def _parse_odds_from_event(self, event: dict) -> List[Odds]:
        """
        Parse odds from The Odds API event data.
        """
        odds_list = []

        try:
            # The Odds API returns odds per bookmaker
            for bookmaker in event.get('bookmakers', []):
                bookmaker_name = bookmaker.get('title', 'unknown')

                for market in bookmaker.get('markets', []):
                    market_key = market.get('key')

                    # Map market key to our MarketType
                    market_type = self._odds_api_to_market_type(market_key)
                    if not market_type:
                        continue

                    for outcome in market.get('outcomes', []):
                        # The Odds API uses different outcome names
                        selection = self._map_outcome_to_selection(outcome.get('name', ''), market_type)
                        if not selection:
                            continue

                        odds = Odds(
                            id=f"{event['id']}_{bookmaker_name}_{market_key}_{outcome['name']}",
                            fixture_id=event['id'],
                            market_type=market_type,
                            selection=selection,
                            decimal_odds=Decimal(str(outcome['price'])),
                            timestamp=datetime.fromisoformat(event['last_update'].replace('Z', '+00:00')),
                            bookmaker=bookmaker_name
                        )

                        odds_list.append(odds)

        except Exception as e:
            self.logger.warning(f"Error parsing odds from The Odds API event: {e}")

        return odds_list

    def _odds_api_to_market_type(self, market_key: str) -> Optional[MarketType]:
        """
        Map The Odds API market key to MarketType enum.
        """
        mapping = {
            'h2h': MarketType.MATCH_ODDS,
            'over_under': MarketType.OVER_UNDER,
            'btts': MarketType.BTTS,
            'double_chance': MarketType.DOUBLE_CHANCE,
            'asian_handicap': MarketType.ASIAN_HANDICAP,
            'correct_score': MarketType.CORRECT_SCORE
        }
        return mapping.get(market_key)

    def _map_outcome_to_selection(self, outcome_name: str, market_type: MarketType) -> Optional[str]:
        """
        Map The Odds API outcome name to our selection string.
        """
        if market_type == MarketType.MATCH_ODDS:
            # h2h market: outcomes are team names or "Draw"
            if outcome_name.lower() == "draw":
                return "Draw"
            return outcome_name  # Team name

        elif market_type == MarketType.OVER_UNDER:
            # over_under market: outcomes are like "Over 2.5", "Under 2.5"
            return outcome_name

        elif market_type == MarketType.BTTS:
            # btts market: outcomes are "Yes", "No"
            return outcome_name

        # For other markets, return as-is (simplified)
        return outcome_name

    async def get_latest_odds(
        self,
        fixture_id: str,
        market_type: MarketType
    ) -> Optional[Odds]:
        """
        Get the latest odds for a fixture and market type.
        """
        odds_list = await self.get_odds_for_fixture(fixture_id, [market_type])
        if not odds_list:
            return None

        # Return the most recent odds
        return max(odds_list, key=lambda o: o.timestamp)