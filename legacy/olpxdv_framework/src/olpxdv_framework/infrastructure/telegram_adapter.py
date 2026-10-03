"""
Telegram Adapter for sending betting recommendations.

This module implements the Telegram bot adapter for outputting
betting recommendations to Telegram channels/chats.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime

from olpxdv_framework.domain.models import EngineConsensus, MarketType
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramAdapter:
    """
    Adapter for sending messages to Telegram.

    Supports:
    - Sending formatted betting recommendations
    - Markdown/HTML formatting
    - Rate limiting
    - Error handling and retries
    """

    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Configuration
        self.bot_token = self.settings.api.telegram_bot_token
        self.chat_id = self.settings.api.telegram_chat_id
        self.base_url = "https://api.telegram.org/bot"

        # Rate limiting
        self._last_message_time = 0
        self._min_message_interval = 1.0  # Minimum seconds between messages

        # Message templates
        self.recommendation_template = self._load_recommendation_template()
        self.rejection_template = self._load_rejection_template()

    def _load_recommendation_template(self) -> str:
        """Load the recommendation message template."""
        return """🎯 <b>OLP XDV Betting Recommendation</b>

📅 <b>Date:</b> {date}
🏆 <b>League:</b> {league}
⚽ <b>Match:</b> {home_team} vs {away_team}
🕐 <b>Kickoff:</b> {kickoff_time} UTC

🎲 <b>Market:</b> {market_name}
🎯 <b>Selection:</b> {selection}

📊 <b>Probability:</b> {probability:.1%}
💰 <b>Odds:</b> {odds:.2f}
📈 <b>Expected Value:</b> {ev:+.4f}
🎯 <b>Edge:</b> {edge:+.2%}
💵 <b>Recommended Stake:</b> {stake:.2f} units
🔑 <b>Kelly Fraction:</b> {kelly:.2%}

🤖 <b>Confidence:</b> {confidence:.1%}
🧠 <b>Engines:</b> {engines}

{booking_code}

⚠️ <i>Paper Trading Only - No Real Money Involved</i>
🔒 <i>Protected Constants Enforced</i>
"""

    def _load_rejection_template(self) -> str:
        """Load the rejection message template."""
        return """❌ <b>OLP XDV Bet Rejection</b>

📅 <b>Date:</b> {date}
⚽ <b>Match:</b> {fixture_id}
🎲 <b>Market:</b> {market_name}
🎯 <b>Selection:</b> {selection}

📈 <b>Expected Value:</b> {ev:+.4f}
🎯 <b>Edge:</b> {edge:+.2%}
💵 <b>Recommended Stake:</b> {stake:.2f} units

🚫 <b>Reason:</b> {reason}

⚠️ <i>Paper Trading Only</i>
"""

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)

    async def send_message(self, message: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """
        Send a message to Telegram.

        Args:
            message: The message text
            parse_mode: "HTML" or "Markdown" or None

        Returns:
            Dictionary with success status and response details
        """
        if not self.is_configured():
            self.logger.warning("Telegram not configured (missing bot token or chat ID)")
            return {
                'success': False,
                'error': 'Telegram not configured',
                'message_id': None
            }

        # Rate limiting
        await self._respect_rate_limit()

        try:
            import httpx

            url = f"{self.base_url}{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get('result', {}).get('message_id')
                    self.logger.debug(f"Telegram message sent successfully: {message_id}")
                    return {
                        'success': True,
                        'message_id': message_id,
                        'response': data
                    }
                else:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('description', f'HTTP {response.status_code}')
                    self.logger.error(f"Telegram API error: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'message_id': None
                    }

        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return {
                'success': False,
                'error': str(e),
                'message_id': None
            }

    async def _respect_rate_limit(self):
        """Respect minimum interval between messages."""
        now = datetime.utcnow().timestamp()
        elapsed = now - self._last_message_time
        if elapsed < self._min_message_interval:
            wait_time = self._min_message_interval - elapsed
            self.logger.debug(f"Rate limiting Telegram: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        self._last_message_time = datetime.utcnow().timestamp()

    async def format_bet_recommendation(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        booking_code: Optional[str] = None
    ) -> str:
        """
        Format a betting recommendation for Telegram.

        Args:
            consensus: The engine consensus
            stake: Recommended stake
            booking_code: Optional SportyBet booking code

        Returns:
            Formatted message string
        """
        try:
            # Extract information from consensus
            # Note: We don't have fixture details in consensus, so we'll use what we have
            # In a full implementation, we'd look up fixture details

            # Calculate derived values
            probability_pct = float(consensus.probability) * 100
            odds = self._extract_odds(consensus)
            ev = float(consensus.expected_value)
            edge = float(consensus.expected_value)  # For unit stake, EV = edge
            kelly_pct = float(consensus.kelly_fraction) * 100 if hasattr(consensus, 'kelly_fraction') else 0
            confidence_pct = float(consensus.confidence) * 100

            # Format booking code section
            booking_section = ""
            if booking_code:
                booking_section = f"🔑 <b>SportyBet Booking Code:</b> <code>{booking_code}</code>"

            # Format engines
            engines_str = ", ".join(consensus.engines_used) if consensus.engines_used else "Unknown"

            # Market name mapping
            market_names = {
                MarketType.MATCH_ODDS: "Match Odds (1X2)",
                MarketType.OVER_UNDER: "Over/Under",
                MarketType.BTTS: "Both Teams To Score (BTTS)",
                MarketType.DOUBLE_CHANCE: "Double Chance",
                MarketType.ASIAN_HANDICAP: "Asian Handicap",
                MarketType.CORRECT_SCORE: "Correct Score"
            }
            market_name = market_names.get(consensus.market_type, consensus.market_type.value)

            # Format message
            message = self.recommendation_template.format(
                date=datetime.utcnow().strftime('%Y-%m-%d'),
                league="Unknown",  # Would come from fixture lookup
                home_team="Home Team",  # Would come from fixture lookup
                away_team="Away Team",  # Would come from fixture lookup
                kickoff_time="TBD",  # Would come from fixture lookup
                market_name=market_name,
                selection=consensus.selection,
                probability=probability_pct / 100,
                odds=odds if odds else 0.0,
                ev=ev,
                edge=edge,
                stake=float(stake),
                kelly=kelly_pct / 100,
                confidence=confidence_pct / 100,
                engines=engines_str,
                booking_code=booking_section
            )

            return message.strip()

        except Exception as e:
            self.logger.error(f"Error formatting bet recommendation: {e}")
            return f"Error formatting recommendation: {e}"

    async def format_rejection_message(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        reason: str
    ) -> str:
        """
        Format a rejection message for Telegram.

        Args:
            consensus: The engine consensus
            stake: Recommended stake (that was rejected)
            reason: Rejection reason

        Returns:
            Formatted message string
        """
        try:
            odds = self._extract_odds(consensus)
            ev = float(consensus.expected_value)
            edge = float(consensus.expected_value)

            market_names = {
                MarketType.MATCH_ODDS: "Match Odds (1X2)",
                MarketType.OVER_UNDER: "Over/Under",
                MarketType.BTTS: "Both Teams To Score (BTTS)",
                MarketType.DOUBLE_CHANCE: "Double Chance",
                MarketType.ASIAN_HANDICAP: "Asian Handicap",
                MarketType.CORRECT_SCORE: "Correct Score"
            }
            market_name = market_names.get(consensus.market_type, consensus.market_type.value)

            message = self.rejection_template.format(
                date=datetime.utcnow().strftime('%Y-%m-%d'),
                fixture_id=consensus.fixture_id,
                market_name=market_name,
                selection=consensus.selection,
                ev=ev,
                edge=edge,
                stake=float(stake),
                reason=reason
            )

            return message.strip()

        except Exception as e:
            self.logger.error(f"Error formatting rejection message: {e}")
            return f"Error formatting rejection: {e}"

    def _extract_odds(self, consensus: EngineConsensus) -> Optional[float]:
        """
        Extract decimal odds from consensus.
        """
        try:
            if consensus.probability > Decimal('0'):
                # expected_value = probability * odds - 1 (for unit stake)
                # odds = (expected_value + 1) / probability
                odds = (float(consensus.expected_value) + 1.0) / float(consensus.probability)
                return odds
            return None
        except Exception:
            return None

    async def send_bet_recommendation(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        booking_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a formatted betting recommendation to Telegram.

        Args:
            consensus: The engine consensus
            stake: Recommended stake
            booking_code: Optional SportyBet booking code

        Returns:
            Dictionary with success status
        """
        message = await self.format_bet_recommendation(consensus, stake, booking_code)
        return await self.send_message(message)

    async def send_rejection(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        reason: str
    ) -> Dict[str, Any]:
        """
        Send a rejection message to Telegram.

        Args:
            consensus: The engine consensus
            stake: Recommended stake that was rejected
            reason: Rejection reason

        Returns:
            Dictionary with success status
        """
        message = await self.format_rejection_message(consensus, stake, reason)
        return await self.send_message(message)

    async def send_summary(
        self,
        published_count: int,
        rejected_count: int,
        clv_gate_status: str
    ) -> Dict[str, Any]:
        """
        Send a summary message at the end of a pipeline cycle.

        Args:
            published_count: Number of bets published
            rejected_count: Number of bets rejected
            clv_gate_status: Current CLV gate status

        Returns:
            Dictionary with success status
        """
        summary = f"""📊 <b>OLP XDV Pipeline Summary</b>

📅 <b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
✅ <b>Published:</b> {published_count}
❌ <b>Rejected:</b> {rejected_count}
📈 <b>CLV Gate:</b> {clv_gate_status}

🔒 <i>Protected Constants Enforced</i>
"""

        return await self.send_message(summary)

    async def health_check(self) -> bool:
        """
        Check if the Telegram adapter is functional.
        """
        if not self.is_configured():
            return False

        try:
            import httpx

            url = f"{self.base_url}{self.bot_token}/getMe"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return response.status_code == 200

        except Exception as e:
            self.logger.error(f"Telegram health check failed: {e}")
            return False


# Mock adapter for development/testing
class MockTelegramAdapter(TelegramAdapter):
    """
    Mock Telegram adapter for development without a real bot token.
    """

    def __init__(self):
        # Don't call super().__init__() as it requires config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sent_messages = []

    def is_configured(self) -> bool:
        return True  # Always "configured" for testing

    async def send_message(self, message: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """Mock send message - just logs and stores."""
        self.sent_messages.append({
            'message': message,
            'parse_mode': parse_mode,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.logger.info(f"MOCK TELEGRAM: {message[:100]}...")
        return {
            'success': True,
            'message_id': len(self.sent_messages),
            'response': {'ok': True, 'result': {'message_id': len(self.sent_messages)}}
        }

    async def format_bet_recommendation(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        booking_code: Optional[str] = None
    ) -> str:
        """Format recommendation (uses parent implementation)."""
        return await super().format_bet_recommendation(consensus, stake, booking_code)

    async def format_rejection_message(
        self,
        consensus: EngineConsensus,
        stake: Decimal,
        reason: str
    ) -> str:
        """Format rejection (uses parent implementation)."""
        return await super().format_rejection_message(consensus, stake, reason)

    async def health_check(self) -> bool:
        return True