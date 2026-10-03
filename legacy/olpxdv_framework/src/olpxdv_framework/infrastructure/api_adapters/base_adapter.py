"""
Base API Adapter for external data sources.

This module defines the base class that all API adapters must implement.
"""

from __future__ import annotations
import abc
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from olpxdv_framework.domain.models import Fixture, Odds, MarketType


class APIError(Exception):
    """Base exception for API errors"""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded"""
    pass


class AuthenticationError(APIError):
    """Raised when API authentication fails"""
    pass


class DataNotFoundError(APIError):
    """Raised when requested data is not found"""
    pass


class BaseAPIAdapter(abc.ABC):
    """
    Abstract base class for all API adapters.

    Each adapter must implement methods to fetch fixtures and odds from
    their respective data sources.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._rate_limit_remaining = float('inf')
        self._rate_limit_reset = datetime.utcnow()

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the API is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abc.abstractmethod
    async def get_upcoming_fixtures(
        self,
        look_ahead_days: int = 2,
        leagues: Optional[List[str]] = None
    ) -> List[Fixture]:
        """
        Get upcoming fixtures from the API.

        Args:
            look_ahead_days: How many days ahead to look for fixtures
            leagues: Optional list of leagues to filter by

        Returns:
            List of Fixture objects
        """
        pass

    @abc.abstractmethod
    async def get_odds_for_fixture(
        self,
        fixture_id: str,
        market_types: List[MarketType]
    ) -> List[Odds]:
        """
        Get odds for a specific fixture.

        Args:
            fixture_id: The fixture identifier
            market_types: List of market types to get odds for

        Returns:
            List of Odds objects
        """
        pass

    async def get_latest_odds(
        self,
        fixture_id: str,
        market_type: MarketType
    ) -> Optional[Odds]:
        """
        Get the latest odds for a fixture and market type.

        Args:
            fixture_id: The fixture identifier
            market_type: The market type

        Returns:
            Latest Odds object or None if not available
        """
        odds_list = await self.get_odds_for_fixture(fixture_id, [market_type])
        if odds_list:
            # Return the most recent odds
            return max(odds_list, key=lambda o: o.timestamp)
        return None

    def _is_rate_limited(self) -> bool:
        """
        Check if we're currently rate limited.

        Returns:
            True if rate limited, False otherwise
        """
        return datetime.utcnow() < self._rate_limit_reset

    def _update_rate_limit_info(self, remaining: int, reset_time: datetime):
        """
        Update rate limit information from API response headers.

        Args:
            remaining: Number of requests remaining
            reset_time: When the rate limit resets
        """
        self._rate_limit_remaining = remaining
        self._rate_limit_reset = reset_time

    async def _respect_rate_limit(self):
        """
        Wait if necessary to respect rate limits.
        """
        if self._is_rate_limited():
            wait_time = (self._rate_limit_reset - datetime.utcnow()).total_seconds()
            if wait_time > 0:
                self.logger.info(f"Rate limited, waiting {wait_time:.2f} seconds")
                # In a real implementation, we'd actually wait here
                # For now, we'll just log it
                pass