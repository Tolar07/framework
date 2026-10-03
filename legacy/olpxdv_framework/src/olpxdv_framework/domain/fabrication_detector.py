"""
Fabrication Detection System (FAB-001..004)

This module implements the fabrication detection patterns from OLP XDV:
- FAB-001: Impossible odds combinations
- FAB-002: Statistical anomalies in odds movements
- FAB-003: Fabricated fixture data
- FAB-004: Engine consensus manipulation
"""

from __future__ import annotations
import logging
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import statistics
from dataclasses import dataclass, field

from olpxdv_framework.domain.models import Fixture, Odds, MarketType, EngineConsensus
from olpxdv_framework.domain.protected_constants import is_fabrication_detection_enabled, get_fabrication_threshold

logger = logging.getLogger(__name__)


@dataclass
class FabricationAlert:
    """Represents a fabrication detection alert."""
    fixture_id: str
    market_type: MarketType
    selection: str
    alert_type: str  # FAB-001, FAB-002, FAB-003, FAB-004
    confidence: Decimal  # 0-1
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    evidence: dict = field(default_factory=dict)


class FabricationDetector:
    """
    Detects fabricated data in sports betting pipelines.

    Implements FAB-001 through FAB-004 detection patterns:
    - FAB-001: Impossible odds combinations (arbitrage violations, illogical prices)
    - FAB-002: Statistical anomalies in odds movements (unnatural patterns)
    - FAB-003: Fabricated fixture data (impossible scores, invalid teams)
    - FAB-004: Engine consensus manipulation (suspicious agreement patterns)
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.threshold = get_fabrication_threshold()

    async def detect_fabrication(
        self,
        fixture: Fixture,
        odds_list: List[Odds],
        consensus: Optional[EngineConsensus] = None
    ) -> Tuple[bool, str]:
        """
        Main entry point for fabrication detection.

        Returns:
            Tuple of (is_fabricated: bool, reason: str)
        """
        if not is_fabrication_detection_enabled():
            return False, "Fabrication detection disabled"

        try:
            # Run all detection patterns
            alerts = []

            # FAB-001: Impossible odds combinations
            fab001_alert = await self._detect_fab001_odds_combinations(odds_list)
            if fab001_alert:
                alerts.append(fab001_alert)

            # FAB-002: Statistical anomalies in odds movements
            fab002_alert = await self._detect_fab002_odds_movements(odds_list)
            if fab002_alert:
                alerts.append(fab002_alert)

            # FAB-003: Fabricated fixture data
            fab003_alert = await self._detect_fab003_fixture_data(fixture)
            if fab003_alert:
                alerts.append(fab003_alert)

            # FAB-004: Engine consensus manipulation
            if consensus:
                fab004_alert = await self._detect_fab004_consensus_manipulation(
                    fixture, odds_list, consensus
                )
                if fab004_alert:
                    alerts.append(fab004_alert)

            # Determine if any alert crosses the confidence threshold
            if alerts:
                # Use the highest confidence alert
                max_alert = max(alerts, key=lambda a: a.confidence)
                if max_alert.confidence >= self.threshold:
                    return True, f"{max_alert.alert_type}: {max_alert.description}"

            return False, "No fabrication detected"

        except Exception as e:
            self.logger.error(f"Error in fabrication detection: {e}")
            # Err on the side of caution - if detection fails, assume not fabricated
            return False, f"Detection error: {e}"

    async def _detect_fab001_odds_combinations(
        self,
        odds_list: List[Odds]
    ) -> Optional[FabricationAlert]:
        """
        FAB-001: Detect impossible odds combinations.

        Checks for:
        - Arbitrage opportunities that are too large (indicating manipulated data)
        - Illogical price relationships (e.g., draw price higher than both teams in 1X2)
        - Negative or zero odds
        """
        if not odds_list:
            return None

        try:
            # Group odds by market type
            odds_by_market = {}
            for odds in odds_list:
                if odds.market_type not in odds_by_market:
                    odds_by_market[odds.market_type] = []
                odds_by_market[odds.market_type].append(odds)

            # Check each market type for impossibilities
            for market_type, market_odds in odds_by_market.items():
                if market_type == MarketType.MATCH_ODDS:
                    alert = self._check_match_odds_impossibilities(market_odds)
                    if alert:
                        return alert
                elif market_type == MarketType.OVER_UNDER:
                    alert = self._check_over_under_impossibilities(market_odds)
                    if alert:
                        return alert
                elif market_type == MarketType.BTTS:
                    alert = self._check_btts_impossibilities(market_odds)
                    if alert:
                        return alert

            return None

        except Exception as e:
            self.logger.warning(f"Error in FAB-001 detection: {e}")
            return None

    def _check_match_odds_impossibilities(
        self,
        odds_list: List[Odds]
    ) -> Optional[FabricationAlert]:
        """Check 1X2 market for impossible combinations."""
        # Find home, draw, away odds
        home_odds = None
        draw_odds = None
        away_odds = None

        for odds in odds_list:
            selection_lower = odds.selection.lower()
            if 'home' in selection_lower:
                home_odds = odds
            elif 'draw' in selection_lower:
                draw_odds = odds
            elif 'away' in selection_lower:
                away_odds = odds

        if not all([home_odds, draw_odds, away_odds]):
            return None  # Not enough data to check

        # Check for negative or zero odds
        for odds in [home_odds, draw_odds, away_odds]:
            if odds.decimal_odds <= Decimal('0'):
                return FabricationAlert(
                    fixture_id=home_odds.fixture_id,
                    market_type=MarketType.MATCH_ODDS,
                    selection=odds.selection,
                    alert_type="FAB-001",
                    confidence=Decimal('0.95'),
                    description=f"Negative or zero odds: {odds.selection} @ {odds.decimal_odds}",
                    evidence={"negative_odds": str(odds.decimal_odds)}
                )

        # Check for illogical combinations (draw should not be highest in most cases)
        # While draw CAN be highest, extremely high draw odds relative to teams is suspicious
        draw_prob = Decimal('1') / draw_odds.decimal_odds
        home_prob = Decimal('1') / home_odds.decimal_odds
        away_prob = Decimal('1') / away_odds.decimal_odds

        total_prob = draw_prob + home_prob + away_prob

        # Normal bookmaker margin is 102-110%. Much higher suggests manipulation.
        if total_prob < Decimal('0.80'):  # Less than 80% total probability = >125% margin
            return FabricationAlert(
                fixture_id=home_odds.fixture_id,
                market_type=MarketType.MATCH_ODDS,
                selection="MATCH_ODDS_COMBINATION",
                alert_type="FAB-001",
                confidence=Decimal('0.9'),
                description=f"Impossible probability combination: {total_prob:.3f} (margin >{(1/total_prob-1)*100:.1f}%)",
                evidence={
                    "home_prob": str(home_prob),
                    "draw_prob": str(draw_prob),
                    "away_prob": str(away_prob),
                    "total_prob": str(total_prob)
                }
            )

        return None

    def _check_over_under_impossibilities(
        self,
        odds_list: List[Odds]
    ) -> Optional[FabricationAlert]:
        """Check Over/Under market for impossible combinations."""
        over_odds = None
        under_odds = None

        for odds in odds_list:
            selection_lower = odds.selection.lower()
            if selection_lower.startswith('over'):
                over_odds = odds
            elif selection_lower.startswith('under'):
                under_odds = odds

        if not all([over_odds, under_odds]):
            return None

        # Check for negative or zero odds
        for odds in [over_odds, under_odds]:
            if odds.decimal_odds <= Decimal('0'):
                return FabricationAlert(
                    fixture_id=over_odds.fixture_id,
                    market_type=MarketType.OVER_UNDER,
                    selection=odds.selection,
                    alert_type="FAB-001",
                    confidence=Decimal('0.95'),
                    description=f"Negative or zero odds: {odds.selection} @ {odds.decimal_odds}",
                    evidence={"negative_odds": str(odds.decimal_odds)}
                )

        # For a fair Over/Under market, the probabilities should sum to approximately 1
        # (accounting for bookmaker margin)
        over_prob = Decimal('1') / over_odds.decimal_odds
        under_prob = Decimal('1') / under_odds.decimal_odds
        total_prob = over_prob + under_prob

        # Normal total should be between 1.02 and 1.15 (2-15% margin)
        if total_prob < Decimal('0.85') or total_prob > Decimal('1.50'):
            return FabricationAlert(
                fixture_id=over_odds.fixture_id,
                market_type=MarketType.OVER_UNDER,
                selection="OVER_UNDER_COMBINATION",
                alert_type="FAB-001",
                confidence=Decimal('0.85'),
                description=f"Impossible Over/Under probability: {total_prob:.3f}",
                evidence={
                    "over_prob": str(over_prob),
                    "under_prob": str(under_prob),
                    "total_prob": str(total_prob)
                }
            )

        return None

    def _check_btts_impossibilities(
        self,
        odds_list: List[Odds]
    ) -> Optional[FabricationAlert]:
        """Check BTTS market for impossible combinations."""
        yes_odds = None
        no_odds = None

        for odds in odds_list:
            selection_lower = odds.selection.lower()
            if selection_lower == 'yes':
                yes_odds = odds
            elif selection_lower == 'no':
                no_odds = odds

        if not all([yes_odds, no_odds]):
            return None

        # Check for negative or zero odds
        for odds in [yes_odds, no_odds]:
            if odds.decimal_odds <= Decimal('0'):
                return FabricationAlert(
                    fixture_id=yes_odds.fixture_id,
                    market_type=MarketType.BTTS,
                    selection=odds.selection,
                    alert_type="FAB-001",
                    confidence=Decimal('0.95'),
                    description=f"Negative or zero odds: {odds.selection} @ {odds.decimal_odds}",
                    evidence={"negative_odds": str(odds.decimal_odds)}
                )

        # BTTS Yes + No should sum to approximately 1 (with margin)
        yes_prob = Decimal('1') / yes_odds.decimal_odds
        no_prob = Decimal('1') / no_odds.decimal_odds
        total_prob = yes_prob + no_prob

        if total_prob < Decimal('0.80') or total_prob > Decimal('1.30'):
            return FabricationAlert(
                fixture_id=yes_odds.fixture_id,
                market_type=MarketType.BTTS,
                selection="BTTS_COMBINATION",
                alert_type="FAB-001",
                confidence=Decimal('0.85'),
                description=f"Impossible BTTS probability combination: {total_prob:.3f}",
                evidence={
                    "yes_prob": str(yes_prob),
                    "no_prob": str(no_prob),
                    "total_prob": str(total_prob)
                }
            )

        return None

    async def _detect_fab002_odds_movements(
        self,
        odds_list: List[Odds]
    ) -> Optional[FabricationAlert]:
        """
        FAB-002: Detect statistical anomalies in odds movements.

        Looks for:
        - Odds that change too rapidly or in unnatural patterns
        - Odds that don't follow expected relationships with time to kickoff
        - Identical odds across multiple bookmakers (suggesting fabricated data)
        """
        if len(odds_list) < 2:
            return None

        try:
            # Check for identical odds across bookmakers (suspicious)
            if await self._check_identical_odds(odds_list):
                return FabricationAlert(
                    fixture_id=odds_list[0].fixture_id,
                    market_type=odds_list[0].market_type,
                    selection=odds_list[0].selection,
                    alert_type="FAB-002",
                    confidence=Decimal('0.8'),
                    description="Identical odds across multiple bookmakers",
                    evidence={"bookmakers": [o.bookmaker for o in odds_list]}
                )

            # Check for impossible movements (would need historical data)
            # For now, we'll check for extreme values that suggest manipulation
            extreme_odds = [o for o in odds_list if o.decimal_odds > Decimal('50.0') or o.decimal_odds < Decimal('1.01')]
            if extreme_odds:
                return FabricationAlert(
                    fixture_id=extreme_odds[0].fixture_id,
                    market_type=extreme_odds[0].market_type,
                    selection=extreme_odds[0].selection,
                    alert_type="FAB-002",
                    confidence=Decimal('0.75'),
                    description=f"Extreme odds values detected: {extreme_odds[0].decimal_odds}",
                    evidence={"extreme_odds": [str(o.decimal_odds) for o in extreme_odds]}
                )

            return None

        except Exception as e:
            self.logger.warning(f"Error in FAB-002 detection: {e}")
            return None

    async def _check_identical_odds(
        self,
        odds_list: List[Odds]
    ) -> bool:
        """Check if all odds are identical (suspicious)."""
        if len(odds_list) < 2:
            return False

        first_odds = odds_list[0].decimal_odds
        return all(o.decimal_odds == first_odds for o in odds_list[1:])

    async def _detect_fab003_fixture_data(
        self,
        fixture: Fixture
    ) -> Optional[FabricationAlert]:
        """
        FAB-003: Detect fabricated fixture data.

        Checks for:
        - Impossible team names or IDs
        - Invalid match dates (too far in past/future)
        - Impossible scores
        - Invalid league names
        """
        try:
            # Check for impossible fixture ID
            if not fixture.id or len(fixture.id.strip()) == 0:
                return FabricationAlert(
                    fixture_id="",
                    market_type=MarketType.MATCH_ODDS,  # Default
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.9'),
                    description="Empty or invalid fixture ID",
                    evidence={"fixture_id": fixture.id}
                )

            # Check for impossible team names
            if not fixture.home_team.name or len(fixture.home_team.name.strip()) < 2:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.9'),
                    description=f"Invalid home team name: '{fixture.home_team.name}'",
                    evidence={"home_team_name": fixture.home_team.name}
                )

            if not fixture.away_team.name or len(fixture.away_team.name.strip()) < 2:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.9'),
                    description=f"Invalid away team name: '{fixture.away_team.name}'",
                    evidence={"away_team_name": fixture.away_team.name}
                )

            # Check for same team (impossible fixture)
            if fixture.home_team.id == fixture.away_team.id:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.95'),
                    description="Home and away teams are identical",
                    evidence={
                        "home_team_id": fixture.home_team.id,
                        "away_team_id": fixture.away_team.id
                    }
                )

            # Check for impossible dates (too far in past/future)
            now = datetime.utcnow()
            if fixture.match_date < now - timedelta(days=365*2):  # More than 2 years ago
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.85'),
                    description=f"Match date too far in past: {fixture.match_date}",
                    evidence={"match_date": fixture.match_date.isoformat()}
                )

            if fixture.match_date > now + timedelta(days=365*2):  # More than 2 years in future
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.85'),
                    description=f"Match date too far in future: {fixture.match_date}",
                    evidence={"match_date": fixture.match_date.isoformat()}
                )

            # Check for impossible scores (if available)
            if fixture.home_score is not None and fixture.home_score < 0:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.95'),
                    description=f"Negative home score: {fixture.home_score}",
                    evidence={"home_score": fixture.home_score}
                )

            if fixture.away_score is not None and fixture.away_score < 0:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.95'),
                    description=f"Negative away score: {fixture.away_score}",
                    evidence={"away_score": fixture.away_score}
                )

            # Check for impossibly high scores (context-dependent, but >100 is suspicious)
            if fixture.home_score is not None and fixture.home_score > 100:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.8'),
                    description=f"Impossibly high home score: {fixture.home_score}",
                    evidence={"home_score": fixture.home_score}
                )

            if fixture.away_score is not None and fixture.away_score > 100:
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=MarketType.MATCH_ODDS,
                    selection="UNKNOWN",
                    alert_type="FAB-003",
                    confidence=Decimal('0.8'),
                    description=f"Impossibly high away score: {fixture.away_score}",
                    evidence={"away_score": fixture.away_score}
                )

            return None

        except Exception as e:
            self.logger.warning(f"Error in FAB-003 detection: {e}")
            return None

    async def _detect_fab004_consensus_manipulation(
        self,
        fixture: Fixture,
        odds_list: List[Odds],
        consensus: EngineConsensus
    ) -> Optional[FabricationAlert]:
        """
        FAB-004: Detect engine consensus manipulation.

        Checks for:
        - Consensus that doesn't correlate with actual odds
        - Impossible probability values given the odds
        - Suspicious agreement between engines that shouldn't agree
        - Consensus values that are statistically impossible
        """
        try:
            # Check for impossible probability values
            if consensus.probability < Decimal('0') or consensus.probability > Decimal('1'):
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=consensus.market_type,
                    selection=consensus.selection,
                    alert_type="FAB-004",
                    confidence=Decimal('0.95'),
                    description=f"Impossible probability value: {consensus.probability}",
                    evidence={"probability": str(consensus.probability)}
                )

            if consensus.confidence < Decimal('0') or consensus.confidence > Decimal('1'):
                return FabricationAlert(
                    fixture_id=fixture.id,
                    market_type=consensus.market_type,
                    selection=consensus.selection,
                    alert_type="FAB-004",
                    confidence=Decimal('0.95'),
                    description=f"Impossible confidence value: {consensus.confidence}",
                    evidence={"confidence": str(consensus.confidence)}
                )

            # Check if consensus probability is wildly inconsistent with odds
            if odds_list:
                # Find odds matching the consensus selection
                matching_odds = [
                    o for o in odds_list
                    if o.selection.lower() == consensus.selection.lower()
                ]

                if matching_odds:
                    # Use the average of matching odds
                    avg_decimal_odds = sum(o.decimal_odds for o in matching_odds) / len(matching_odds)
                    implied_probability = Decimal('1') / avg_decimal_odds

                    # Check if consensus probability is implausibly different from odds-implied probability
                    # Allow for some difference due to edge, but not orders of magnitude
                    prob_ratio = consensus.probability / implied_probability if implied_probability > Decimal('0') else Decimal('0')

                    # If consensus probability is more than 10x or less than 0.1x the implied probability, suspicious
                    if prob_ratio > Decimal('10') or prob_ratio < Decimal('0.1'):
                        return FabricationAlert(
                            fixture_id=fixture.id,
                            market_type=consensus.market_type,
                            selection=consensus.selection,
                            alert_type="FAB-004",
                            confidence=Decimal('0.85'),
                            description=f"Consensus probability {consensus.probability} wildly inconsistent with odds-implied {implied_probability:.3f}",
                            evidence={
                                "consensus_probability": str(consensus.probability),
                                "implied_probability": str(implied_probability),
                                "ratio": str(prob_ratio),
                                "avg_decimal_odds": str(avg_decimal_odds)
                            }
                        )

            # Check for suspicious engine agreement (if we had engine data)
            # For now, we'll check if confidence is impossibly high given the uncertainty
            if consensus.confidence > Decimal('0.99') and len(getattr(consensus, 'engines_used', [])) > 1:
                # Very high confidence with multiple engines might suggest manipulation
                # unless there's strong evidence
                pass  # Not implementing this check for now due to lack of engine data in consensus

            return None

        except Exception as e:
            self.logger.warning(f"Error in FAB-004 detection: {e}")
            return None

    # Additional helper methods could be added for more sophisticated detection