"""
SportyBet Bridge: Booking code generation and betting interface.

This module implements the SportyBet booking bridge for generating
booking codes and placing bets on SportyBet.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import uuid

from olpxdv_framework.domain.models import MarketType
from olpxdv_framework.domain.protected_constants import (
    get_booking_code_expiry_minutes,
    get_sportybet_max_odds
)
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class SportybetBridge:
    """
    Bridge to SportyBet for booking code generation and bet placement.

    This adapter handles:
    1. Generating booking codes for bet slips
    2. Validating odds against SportyBet limits
    3. Formatting bets for SportyBet's specific requirements
    4. Handling browser automation via Playwright (if needed)
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Configuration
        self.booking_code_expiry = get_booking_code_expiry_minutes()
        self.max_odds = get_sportybet_max_odds()

        # SportyBet specific settings
        self.base_url = "https://www.sportybet.com"
        self.booking_api_endpoint = "/api/v1/booking"

        # Cache for generated booking codes
        self._booking_cache: Dict[str, Dict[str, Any]] = {}

    async def generate_booking_code(
        self,
        fixture_id: str,
        market_type: MarketType,
        selection: str,
        stake: Decimal,
        odds: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Generate a booking code for a bet on SportyBet.

        In a real implementation, this would:
        1. Use Playwright to navigate to SportyBet
        2. Add the selection to the bet slip
        3. Enter the stake amount
        4. Generate the booking code
        5. Return the booking code

        For now, this is a simulated implementation.

        Args:
            fixture_id: The fixture identifier
            market_type: The market type (match_odds, over_under, etc.)
            selection: The selection (Home, Draw, Away, Over 2.5, etc.)
            stake: The stake amount in units
            odds: The decimal odds (optional, for validation)

        Returns:
            Dictionary with success status, booking code, and metadata
        """
        try:
            self.logger.info(
                f"Generating SportyBet booking code: {fixture_id} "
                f"{market_type.value} {selection} @ {odds} (stake: {stake})"
            )

            # Validate inputs
            validation_result = self._validate_booking_request(
                fixture_id, market_type, selection, stake, odds
            )
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['reason'],
                    'booking_code': None
                }

            # In a real implementation, we would use Playwright here:
            # booking_code = await self._generate_booking_via_playwright(...)

            # Simulated booking code generation
            booking_code = self._generate_mock_booking_code(fixture_id, market_type, selection)

            # Store in cache with expiry
            expiry_time = datetime.utcnow() + timedelta(minutes=self.booking_code_expiry)
            self._booking_cache[booking_code] = {
                'fixture_id': fixture_id,
                'market_type': market_type,
                'selection': selection,
                'stake': stake,
                'odds': odds,
                'created_at': datetime.utcnow(),
                'expires_at': expiry_time
            }

            self.logger.info(f"Generated SportyBet booking code: {booking_code}")

            return {
                'success': True,
                'booking_code': booking_code,
                'fixture_id': fixture_id,
                'market_type': market_type.value,
                'selection': selection,
                'stake': float(stake),
                'odds': float(odds) if odds else None,
                'expires_at': expiry_time.isoformat(),
                'booking_url': f"{self.base_url}/booking/{booking_code}"
            }

        except Exception as e:
            self.logger.error(f"Error generating booking code: {e}")
            return {
                'success': False,
                'error': str(e),
                'booking_code': None
            }

    def _validate_booking_request(
        self,
        fixture_id: str,
        market_type: MarketType,
        selection: str,
        stake: Decimal,
        odds: Optional[Decimal]
    ) -> Dict[str, Any]:
        """
        Validate a booking request before generating a code.
        """
        # Check stake is positive
        if stake <= Decimal('0'):
            return {'valid': False, 'reason': 'Stake must be positive'}

        # Check odds are within SportyBet limits
        if odds is not None:
            if odds > self.max_odds:
                return {
                    'valid': False,
                    'reason': f'Odds {odds} exceed SportyBet maximum of {self.max_odds}'
                }
            if odds < Decimal('1.01'):
                return {
                    'valid': False,
                    'reason': f'Odds {odds} below minimum valid odds'
                }

        # Check market type is supported
        supported_markets = [
            MarketType.MATCH_ODDS,
            MarketType.OVER_UNDER,
            MarketType.BTTS,
            MarketType.DOUBLE_CHANCE
        ]
        if market_type not in supported_markets:
            return {
                'valid': False,
                'reason': f'Market type {market_type} not supported by SportyBet bridge'
            }

        # Check selection format
        if not selection or len(selection.strip()) == 0:
            return {'valid': False, 'reason': 'Selection cannot be empty'}

        # Check fixture_id format
        if not fixture_id or len(fixture_id.strip()) == 0:
            return {'valid': False, 'reason': 'Fixture ID cannot be empty'}

        return {'valid': True}

    def _generate_mock_booking_code(
        self,
        fixture_id: str,
        market_type: MarketType,
        selection: str
    ) -> str:
        """
        Generate a mock booking code for testing/development.

        Real booking codes would be generated by SportyBet's system.
        """
        # Generate a realistic-looking booking code
        # Format: SPORTY-XXXX-XXXX-XXXX (16 chars + prefix)
        unique_part = uuid.uuid4().hex[:12].upper()
        booking_code = f"SPORTY-{unique_part[:4]}-{unique_part[4:8]}-{unique_part[8:12]}"
        return booking_code

    async def get_booking_details(
        self,
        booking_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve details for an existing booking code.
        """
        cached = self._booking_cache.get(booking_code)
        if cached:
            # Check if expired
            if datetime.utcnow() > cached['expires_at']:
                # Remove expired entry
                del self._booking_cache[booking_code]
                return None
            return cached
        return None

    async def validate_booking_code(
        self,
        booking_code: str
    ) -> Dict[str, Any]:
        """
        Validate a booking code exists and is not expired.
        """
        details = await self.get_booking_details(booking_code)
        if details:
            return {
                'valid': True,
                'booking_code': booking_code,
                'details': details
            }
        return {
            'valid': False,
            'booking_code': booking_code,
            'error': 'Booking code not found or expired'
        }

    async def place_bet_via_booking_code(
        self,
        booking_code: str,
        stake: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Place a bet using a booking code.

        In a real implementation, this would:
        1. Navigate to SportyBet booking page
        2. Enter the booking code
        3. Confirm the bet
        4. Return confirmation details

        For now, this is simulated.
        """
        try:
            details = await self.get_booking_details(booking_code)
            if not details:
                return {
                    'success': False,
                    'error': 'Invalid or expired booking code',
                    'bet_id': None
                }

            # Use stake from details if not provided
            bet_stake = stake if stake is not None else details['stake']

            # Simulated bet placement
            bet_id = f"BET-{uuid.uuid4().hex[:12].upper()}"

            self.logger.info(f"Placed bet via booking code {booking_code}: {bet_id}")

            return {
                'success': True,
                'bet_id': bet_id,
                'booking_code': booking_code,
                'fixture_id': details['fixture_id'],
                'market_type': details['market_type'].value,
                'selection': details['selection'],
                'stake': float(bet_stake),
                'odds': details['odds'],
                'placed_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error placing bet via booking code: {e}")
            return {
                'success': False,
                'error': str(e),
                'bet_id': None
            }

    async def get_bet_history(
        self,
        limit: int = 50,
        from_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get bet history from SportyBet.

        In a real implementation, this would use Playwright or API
        to fetch the user's bet history.
        """
        # Simulated bet history
        return [
            {
                'bet_id': f"BET-{uuid.uuid4().hex[:12].upper()}",
                'fixture_id': f"FIX-{uuid.uuid4().hex[:8].upper()}",
                'market_type': 'match_odds',
                'selection': 'Home',
                'stake': 10.0,
                'odds': 2.5,
                'potential_return': 25.0,
                'status': 'pending',
                'placed_at': datetime.utcnow().isoformat()
            }
        ]

    async def check_balance(self) -> Dict[str, Any]:
        """
        Check SportyBet account balance.

        In a real implementation, this would use the API or Playwright.
        """
        return {
            'success': True,
            'balance': 1000.0,
            'currency': 'USD',
            'checked_at': datetime.utcnow().isoformat()
        }

    async def health_check(self) -> bool:
        """
        Check if the SportyBet bridge is functional.
        """
        try:
            # In a real implementation, we'd check connectivity to SportyBet
            # For now, we'll just return True if configured
            return True
        except Exception:
            return False


# Playwright-based implementation (would be used in production)
class PlaywrightSportybetBridge(SportybetBridge):
    """
    SportyBet bridge implementation using Playwright for browser automation.

    This would be used in production for actual bet placement.
    """

    def __init__(self):
        super().__init__()
        self._browser = None
        self._page = None

    async def _ensure_browser(self):
        """
        Initialize Playwright browser if not already running.
        """
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                playwright = await async_playwright().start()
                self._browser = await playwright.chromium.launch(headless=True)
                self._page = await self._browser.new_page()
            except ImportError:
                self.logger.error("Playwright not installed")
                raise RuntimeError("Playwright required for browser automation")

    async def _generate_booking_via_playwright(
        self,
        fixture_id: str,
        market_type: MarketType,
        selection: str,
        stake: Decimal,
        odds: Optional[Decimal]
    ) -> str:
        """
        Generate booking code using Playwright browser automation.
        """
        await self._ensure_browser()

        # This is where actual browser automation would happen:
        # 1. Navigate to SportyBet
        # 2. Search for the fixture
        # 3. Select the market and selection
        # 4. Add to bet slip
        # 5. Enter stake
        # 6. Generate booking code
        # 7. Extract and return booking code

        # For now, fall back to mock
        return self._generate_mock_booking_code(fixture_id, market_type, selection)

    async def close(self):
        """
        Close browser and clean up.
        """
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None