"""
API-Football adapter for fetching sports data and odds.
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


class APIFootballAdapter(BaseAPIAdapter):
    """
    Adapter for API-Football (https://www.api-football.com/)
    """

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.api_key = self.settings.api.api_football_key
        self.base_url = self.settings.api.api_football_base_url
        self.timeout = self.settings.api.api_football_timeout
        self.rate_limit = self.settings.api.api_football_rate_limit

        # Request tracking for rate limiting
        self.request_count = 0
        self.last_reset = datetime.utcnow()

        # League ID mapping (simplified - in practice would be more comprehensive)
        self.league_mapping = {
            'Premier League': 39,
            'Championship': 40,
            'Bundesliga': 78,
            'Serie A': 135,
            'Ligue 1': 61,
            'La Liga': 140,
            'Primeira Liga': 94,
            'Eredivisie': 88,
            'Scottish Premiership': 47,
            'Belgian Pro League': 8,
            'Turkish Super Lig': 101,
            'Swiss Super League': 74,
            'Russian Premier League': 203,
            'Serie B': 136,
            'La Liga 2': 141,
            'Ligue 2': 62,
        }

        # Reverse mapping for lookup
        self.id_to_league = {v: k for k, v in self.league_mapping.items()}

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make a rate-limited request to API-Football.
        """
        # Rate limiting check
        now = datetime.utcnow()
        if (now - self.last_reset).seconds >= 60:
            self.request_count = 0
            self.last_reset = now

        if self.request_count >= self.rate_limit:
            raise RateLimitError(f"API-Football rate limit exceeded: {self.rate_limit} requests/minute")

        # Make request
        url = f"{self.base_url}/{endpoint}"
        headers = {
            'x-apisports-key': self.api_key
        } if self.api_key else {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params, headers=headers)
                self.request_count += 1

                if response.status_code == 401:
                    raise AuthenticationError("API-Football authentication failed")
                elif response.status_code == 429:
                    raise RateLimitError("API-Football rate limit exceeded")
                elif response.status_code == 404:
                    raise DataNotFoundError("API-Football data not found")
                elif response.status_code >= 400:
                    raise APIError(f"API-Football error: {response.status_code}")

                data = response.json()
                if data.get('errors'):
                    raise APIError(f"API-Football API error: {data['errors']}")

                return data.get('response', [])

            except httpx.TimeoutException:
                raise APIError("API-Football request timeout")
            except httpx.RequestError as e:
                raise APIError(f"API-Football request failed: {e}")

    async def get_upcoming_fixtures(
        self,
        days_ahead: int = 7,
        leagues: Optional[List[str]] = None
    ) -> List[Fixture]:
        """
        Get upcoming fixtures from API-Football.
        """
        if not self.api_key:
            self.logger.warning("API-Football key not configured")
            return []

        try:
            # Determine which league IDs to fetch
            league_ids = []
            if leagues is None:
                # Fetch all configured leagues
                league_ids = list(self.league_mapping.values())
            else:
                # Fetch only specified leagues
                for league in leagues:
                    if league in self.league_mapping:
                        league_ids.append(self.league_mapping[league])

            if not league_ids:
                self.logger.warning("No valid leagues specified for API-Football")
                return []

            all_fixtures = []

            # Fetch fixtures for each league
            for league_id in league_ids:
                try:
                    # Get fixtures for next 'days_ahead' days
                    today = datetime.utcnow()
                    end_date = today + timedelta(days=days_ahead)

                    params = {
                        'league': league_id,
                        'from': today.strftime('%Y-%m-%d'),
                        'to': end_date.strftime('%Y-%m-%d'),
                        'status': 'NS'  # Not Started (scheduled)
                    }

                    data = await self._make_request('fixtures', params)

                    for fixture_data in data:
                        fixture = self._parse_fixture_from_data(fixture_data)
                        if fixture:
                            all_fixtures.append(fixture)

                except Exception as e:
                    self.logger.warning(f"Failed to fetch fixtures for league ID {league_id}: {e}")
                    continue

            return all_fixtures

        except Exception as e:
            self.logger.error(f"Error fetching upcoming fixtures from API-Football: {e}")
            return []

    def _parse_fixture_from_data(self, data: dict) -> Optional[Fixture]:
        """
        Parse a fixture from API-Football data.
        """
        try:
            fixture_info = data.get('fixture', {})
            league_info = data.get('league', {})
            teams_info = data.get('teams', {})
            goals_info = data.get('goals', {})

            # Parse fixture ID
            fixture_id = str(fixture_info.get('id'))
            if not fixture_id:
                return None

            # Parse teams
            home_team_info = teams_info.get('home', {})
            away_team_info = teams_info.get('away', {})

            home_team = Team(
                id=f"home_{home_team_info.get('id', 'unknown')}",
                name=home_team_info.get('name', 'Unknown'),
                short_name=home_team_info.get('name', 'Unknown')[:3].upper()
            )

            away_team = Team(
                id=f"away_{away_team_info.get('id', 'unknown')}",
                name=away_team_info.get('name', 'Unknown'),
                short_name=away_team_info.get('name', 'Unknown')[:3].upper()
            )

            # Parse league
            league_name = league_info.get('name', 'Unknown')
            league_id = league_info.get('id')
            league_tier = self._get_league_tier(league_id) if league_id else LeagueTier.TIER_C

            # Parse match date
            timestamp_str = fixture_info.get('timestamp')
            if not timestamp_str:
                return None
            match_date = datetime.fromtimestamp(int(timestamp_str))

            # Parse status
            status_short = fixture_info.get('status', {}).get('short', 'NS')
            status_map = {
                'NS': FixtureStatus.SCHEDULED,
                '1H': FixtureStatus.LIVE,
                '2H': FixtureStatus.LIVE,
                'HT': FixtureStatus.LIVE,
                'FT': FixtureStatus.FINISHED,
                'AET': FixtureStatus.FINISHED,
                'PEN': FixtureStatus.FINISHED,
                'POST': FixtureStatus.POSTPONED,
                'CANC': FixtureStatus.CANCELLED,
                'ABD': FixtureStatus.CANCELLED,
                'INT': FixtureStatus.LIVE,
                'Delay': FixtureStatus.LIVE,
                'RV': FixtureStatus.SCHEDULED,
                'WO': FixtureStatus.FINISHED,
                'LIVE': FixtureStatus.LIVE
            }
            status = status_map.get(status_short, FixtureStatus.SCHEDULED)

            # Parse scores
            home_score = goals_info.get('home')
            away_score = goals_info.get('away')

            # Create fixture
            fixture = Fixture(
                id=fixture_id,
                home_team=home_team,
                away_team=away_team,
                league=league_name,
                league_tier=league_tier,
                match_date=match_date,
                status=status,
                home_score=home_score,
                away_score=away_score
            )

            return fixture

        except Exception as e:
            self.logger.warning(f"Error parsing fixture from API-Football data: {e}")
            return None

    def _get_league_tier(self, league_id: int) -> LeagueTier:
        """
        Determine league tier from league ID.
        This is a simplified mapping - in practice would be more sophisticated.
        """
        # Tier 1: Top European leagues
        tier_1_leagues = {39, 78, 135, 61, 140}  # EPL, Bundesliga, Serie A, Ligue 1, La Liga
        # Tier 2: Second tier
        tier_2_leagues = {40, 94, 88, 47, 8, 101, 74}  # Championship, Primeira Liga, Eredivisie, Scottish Premiership, Belgian Pro League, Turkish Super Lig, Swiss Super League

        if league_id in tier_1_leagues:
            return LeagueTier.TIER_A
        elif league_id in tier_2_leagues:
            return LeagueTier.TIER_B
        else:
            return LeagueTier.TIER_C

    async def get_odds_for_fixture(
        self,
        fixture_id: str,
        market_types: List[MarketType]
    ) -> List[Odds]:
        """
        Get odds for a specific fixture from API-Football.
        Note: API-Football's free tier has limited odds data.
        For production, you'd need the odds endpoint or use a different provider.
        """
        if not self.api_key:
            self.logger.warning("API-Football key not configured")
            return []

        try:
            # API-Football odds endpoint (requires premium plan)
            # For now, we'll return empty list as the free tier doesn't include odds
            # In a real implementation with proper subscription, this would call:
            # endpoint = f"fixtures/odds"
            # params = {'fixture': fixture_id}

            self.logger.info(f"API-Football odds requested for fixture {fixture_id} - returning empty (free tier limitation)")
            return []

        except Exception as e:
            self.logger.error(f"Error fetching odds for fixture {fixture_id} from API-Football: {e}")
            return []

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


# Mock adapter for development/testing when no API keys are available
class MockAPIFootballAdapter(BaseAPIAdapter):
    """
    Mock adapter for API-Football - returns sample data for development.
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_upcoming_fixtures(
        self,
        days_ahead: int = 7,
        leagues: Optional[List[str]] = None
    ) -> List[Fixture]:
        """
        Return mock fixtures for development.
        """
        from ...domain.models import Team, LeagueTier, FixtureStatus
        import uuid

        # Create sample teams
        teams_data = [
            ("Arsenal", "ARS"),
            ("Chelsea", "CHE"),
            ("Liverpool", "LIV"),
            ("Manchester City", "MCI"),
            ("Manchester United", "MUN"),
            ("Tottenham", "TOT"),
            ("Newcastle", "NEW"),
            ("Brighton", "BHA")
        ]

        teams = []
        for name, short in teams_data:
            team = Team(
                id=str(uuid.uuid4()),
                name=name,
                short_name=short
            )
            teams.append(team)

        # Create sample fixtures
        fixtures = []
        base_time = datetime.utcnow()

        for i in range(min(5, len(teams) // 2)):
            home_team = teams[i * 2]
            away_team = teams[i * 2 + 1]
            match_date = base_time + timedelta(days=i+1, hours=15)

            fixture = Fixture(
                id=str(uuid.uuid4()),
                home_team=home_team,
                away_team=away_team,
                league="Premier League",
                league_tier=LeagueTier.TIER_A,
                match_date=match_date,
                status=FixtureStatus.SCHEDULED
            )
            fixtures.append(fixture)

        return fixtures

    async def get_odds_for_fixture(
        self,
        fixture_id: str,
        market_types: List[MarketType]
    ) -> List[Odds]:
        """
        Return mock odds for development.
        """
        from decimal import Decimal
        import uuid

        # Create sample odds
        odds_list = []
        for market_type in market_types[:2]:  # Limit to 2 market types
            odds = Odds(
                id=str(uuid.uuid4()),
                fixture_id=fixture_id,
                market_type=market_type,
                selection="Home" if market_type == MarketType.MATCH_ODDS else "Over 2.5",
                decimal_odds=Decimal('2.5'),
                timestamp=datetime.utcnow(),
                bookmaker="MockBookmaker"
            )
            odds_list.append(odds)

        return odds_list

    async def get_latest_odds(
        self,
        fixture_id: str,
        market_type: MarketType
    ) -> Optional[Odds]:
        """
        Return mock latest odds for development.
        """
        odds_list = await self.get_odds_for_fixture(fixture_id, [market_type])
        return odds_list[0] if odds_list else None