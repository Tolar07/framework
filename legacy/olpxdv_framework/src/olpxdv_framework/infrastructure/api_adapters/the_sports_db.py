"""
TheSportsDB adapter for fetching sports data.
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta

import httpx

from .base_adapter import BaseAPIAdapter, APIError, RateLimitError, AuthenticationError, DataNotFoundError
from ...domain.models import Fixture, Team, LeagueTier, FixtureStatus
from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class TheSportsDBAdapter(BaseAPIAdapter):
    """
    Adapter for TheSportsDB (https://www.thesportsdb.com/)
    """

    async def health_check(self) -> bool:
        """
        Check if TheSportsDB API is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try a simple request to check connectivity
            # We'll use a simple endpoint that should always work
            data = await self._make_request("search_leagues.php", {"l": "Premier%20League"})
            return "leagues" in data
        except Exception as e:
            self.logger.warning(f"TheSportsDB health check failed: {e}")
            return False
    """
    Adapter for TheSportsDB (https://www.thesportsdb.com/)
    """

    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.base_url = self.settings.api.sportsdb_base_url
        self.timeout = self.settings.api.sportsdb_timeout

        # Request tracking (TheSportsDB is generally rate limit friendly for basic usage)
        self.request_count = 0
        self.last_reset = datetime.utcnow()

    async def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make a request to TheSportsDB.
        """
        url = f"{self.base_url}/{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)

                if response.status_code == 404:
                    raise DataNotFoundError("TheSportsDB data not found")
                elif response.status_code >= 400:
                    raise APIError(f"TheSportsDB error: {response.status_code}")

                return response.json()
            except httpx.TimeoutException:
                raise APIError("TheSportsDB request timeout")
            except httpx.RequestError as e:
                raise APIError(f"TheSportsDB request failed: {e}")

    async def get_upcoming_fixtures(
        self,
        days_ahead: int = 7,
        leagues: Optional[List[str]] = None
    ) -> List[Fixture]:
        """
        Get upcoming fixtures from TheSportsDB.
        Note: TheSportsDB structure is different - we search by league/team names.
        """
        try:
            # TheSportsDB requires searching by league name first to get league ID
            # Then we can get events for that league
            # This is a simplified implementation

            all_fixtures = []

            # If no leagues specified, use a default list
            target_leagues = leagues if leagues else ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]

            for league_name in target_leagues:
                try:
                    # Search for league
                    search_endpoint = "search_leagues.php"
                    params = {"l": league_name.replace(" ", "%20")}

                    data = await self._make_request(search_endpoint, params)

                    leagues_data = data.get('leagues', [])
                    if not leagues_data:
                        continue

                    league_id = leagues_data[0]['idLeague']

                    # Get events for this league
                    events_endpoint = "eventsseason.php"
                    params = {"id": league_id}

                    events_data = await self._make_request(events_endpoint, params)

                    events = events_data.get('events', [])
                    for event in events:
                        fixture = self._parse_fixture_from_event(event, league_name)
                        if fixture:
                            # Filter by date range
                            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
                            if fixture.match_date <= cutoff_date:
                                all_fixtures.append(fixture)

                except Exception as e:
                    self.logger.warning(f"Failed to fetch fixtures for league {league_name} from TheSportsDB: {e}")
                    continue

            return all_fixtures

        except Exception as e:
            self.logger.error(f"Error fetching upcoming fixtures from TheSportsDB: {e}")
            return []

    def _parse_fixture_from_event(self, event: dict, league_name: str) -> Optional[Fixture]:
        """
        Parse a fixture from TheSportsDB event data.
        """
        try:
            # Parse teams
            home_team_name = event.get('strHomeTeam')
            away_team_name = event.get('strAwayTeam')

            if not home_team_name or not away_team_name:
                return None

            home_team = Team(
                id=f"thesportsdb_home_{hash(home_team_name)}",
                name=home_team_name,
                short_name=home_team_name[:3].upper() if len(home_team_name) >= 3 else home_team_name
            )

            away_team = Team(
                id=f"thesportsdb_away_{hash(away_team_name)}",
                name=away_team_name,
                short_name=away_team_name[:3].upper() if len(away_team_name) >= 3 else away_team_name
            )

            # Parse match date
            date_str = event.get('dateEvent')
            time_str = event.get('strTime')

            if not date_str:
                return None

            # Combine date and time
            datetime_str = f"{date_str} {time_str}" if time_str else f"{date_str} 00:00:00"
            match_date = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

            # Parse status
            status_str = event.get('strStatus', 'Not Started')
            status_map = {
                'Not Started': FixtureStatus.SCHEDULED,
                'In Progress': FixtureStatus.LIVE,
                'Finished': FixtureStatus.FINISHED,
                'Postponed': FixtureStatus.POSTPONED,
                'Cancelled': FixtureStatus.CANCELLED
            }
            status = status_map.get(status_str, FixtureStatus.SCHEDULED)

            # Parse scores
            home_score = None
            away_score = None

            try:
                if event.get('intHomeScore') is not None:
                    home_score = int(event['intHomeScore'])
                if event.get('intAwayScore') is not None:
                    away_score = int(event['intAwayScore'])
            except (ValueError, TypeError):
                pass

            # Determine league tier (simplified)
            league_tier = self._get_league_tier(league_name)

            # Create fixture
            fixture = Fixture(
                id=event.get('idEvent', f"thesportsdb_{hash(str(event))}"),
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
            self.logger.warning(f"Error parsing fixture from TheSportsDB event: {e}")
            return None

    def _get_league_tier(self, league_name: str) -> LeagueTier:
        """
        Determine league tier from league name.
        """
        tier_1_leagues = {
            'Premier League', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1',
            'Primeira Liga', 'Eredivisie', 'Scottish Premiership'
        }

        tier_2_leagues = {
            'Championship', 'La Liga 2', 'Ligue 2', 'Serie B', 'Bundesliga 2',
            'Eredivisie 2', 'Primeira Liga 2'
        }

        if league_name in tier_1_leagues:
            return LeagueTier.TIER_A
        elif league_name in tier_2_leagues:
            return LeagueTier.TIER_B
        else:
            return LeagueTier.TIER_C

    async def get_odds_for_fixture(
        self,
        fixture_id: str,
        market_types: List[MarketType]
    ) -> List[Odds]:
        """
        Get odds for a specific fixture from TheSportsDB.
        Note: TheSportsDB doesn't provide betting odds in its free API.
        """
        # TheSportsDB free tier doesn't include odds data
        # Would need to use a different source for odds or their premium service
        self.logger.info("TheSportsDB does not provide odds data in free tier")
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
        return odds_list[0] if odds_list else None