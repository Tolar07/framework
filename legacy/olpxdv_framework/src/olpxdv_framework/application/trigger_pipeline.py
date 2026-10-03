"""
TRIGGER Pipeline: Market Selection → Trigger Logic

This module implements the TRIGGER pipeline from OLP XDV:
1. Take EngineConsensus from SCAN pipeline
2. Apply trigger logic (value betting, Kelly criterion, etc.)
3. Generate betting recommendations that pass initial filters
4. Output to PUBLISH pipeline (after CLV gate validation)
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

from olpxdv_framework.domain.models import Fixture, Odds, MarketType, EngineConsensus, BetResult
from olpxdv_framework.domain.clv_calculator import CLVCalculator, CLVGateResult
from olpxdv_framework.domain.protected_constants import (
    get_current_phase,
    get_clv_min_legs,
    get_clv_mean_threshold,
    get_max_kelly_fraction,
    get_max_daily_exposure,
    get_max_single_bet_exposure,
    get_min_edge_for_publish,
    is_client_publish_enabled,
    is_paper_only,
    ProtectedConstants
)
from olpxdv_framework.domain.knowledge_persistence import KnowledgePersistenceService
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class TriggerResult:
    """Result of trigger pipeline processing."""

    def __init__(
        self,
        consensus: EngineConsensus,
        recommended_stake: Decimal = Decimal('0'),
        kelly_fraction: Decimal = Decimal('0'),
        expected_value: Decimal = Decimal('0'),
        edge: Decimal = Decimal('0'),
        trigger_passed: bool = False,
        trigger_reason: str = "",
        clv_gate_result: Optional[CLVGateResult] = None
    ):
        self.consensus = consensus
        self.recommended_stake = recommended_stake
        self.kelly_fraction = kelly_fraction
        self.expected_value = expected_value
        self.edge = edge
        self.trigger_passed = trigger_passed
        self.trigger_reason = trigger_reason
        self.clv_gate_result = clv_gate_result


class TriggerPipeline:
    """
    TRIGGER Pipeline: Apply betting logic to engine consensus.

    Pipeline Steps:
    1. Input Validation: Validate EngineConsensus objects
    2. Value Betting: Calculate expected value and edge
    3. Kelly Criterion: Calculate optimal stake sizing
    4. Risk Management: Apply exposure limits and portfolio constraints
    5. Preliminary Filters: Apply minimum edge, stake limits, etc.
    6. CLV Gate Pre-check: Evaluate if bet would help CLV gate (optional)
    7. Output: TriggerResult objects for PUBLISH pipeline
    """

    def __init__(
        self,
        clv_calculator: Optional[CLVCalculator] = None,
        knowledge_service: Optional[KnowledgePersistenceService] = None
    ):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize components
        self.clv_calculator = clv_calculator or CLVCalculator()
        self.knowledge_service = knowledge_service or KnowledgePersistenceService()

        # Pipeline state (would be persisted in production)
        self.daily_exposure = Decimal('0')
        self.reset_daily_exposure()

    def reset_daily_exposure(self):
        """Reset daily exposure tracking (would be called at midnight)."""
        self.daily_exposure = Decimal('0')
        self.last_reset = datetime.utcnow().date()

    async def run_trigger_cycle(
        self,
        consensus_list: List[EngineConsensus],
        clv_legs: Optional[List] = None  # For CLV gate feedback
    ) -> List[TriggerResult]:
        """
        Execute a full TRIGGER pipeline cycle.

        Args:
            consensus_list: EngineConsensus objects from SCAN pipeline
            clv_legs: Current CLV legs for gate evaluation (optional)

        Returns:
            List of TriggerResult objects that passed trigger logic
        """
        self.logger.info(f"Starting TRIGGER pipeline cycle with {len(consensus_list)} consensus objects")
        start_time = datetime.utcnow()

        try:
            # Reset daily exposure if needed (new day)
            self._check_daily_reset()

            # Step 1: Input Validation
            validated_consensus = await self._validate_consensus(consensus_list)

            # Step 2: Value Betting Analysis
            value_analyzed = await self._analyze_value_betting(validated_consensus)

            # Step 3: Kelly Criterion & Stake Sizing
            stake_sized = await self._calculate_kelly_stakes(value_analyzed)

            # Step 4: Risk Management & Exposure Limits
            risk_managed = await self._apply_risk_management(stake_sized)

            # Step 5: Preliminary Filters (min edge, stake limits, etc.)
            filtered = await self._apply_preliminary_filters(risk_managed)

            # Step 6: CLV Gate Feedback (optional, for informational purposes)
            if clv_legs is not None:
                enhanced_with_clv = await self._enhance_with_clv_feedback(filtered, clv_legs)
            else:
                enhanced_with_clv = filtered

            # Step 7: Final Preparation
            final_results = await self._prepare_final_output(enhanced_with_clv)

            elapsed_time = (datetime.utcnow() - start_time).total_seconds()
            passed_count = sum(1 for r in final_results if r.trigger_passed)

            self.logger.info(
                f"TRIGGER pipeline completed in {elapsed_time:.2f}s: "
                f"{passed_count}/{len(final_results)} triggers passed"
            )

            return final_results

        except Exception as e:
            self.logger.error(f"Error in TRIGGER pipeline: {e}")
            return []

    def _check_daily_reset(self):
        """Check if we need to reset daily exposure (new day)."""
        today = datetime.utcnow().date()
        if today != self.last_reset:
            self.reset_daily_exposure()

    async def _validate_consensus(
        self,
        consensus_list: List[EngineConsensus]
    ) -> List[EngineConsensus]:
        """
        Validate EngineConsensus objects for basic validity.
        """
        validated = []

        for consensus in consensus_list:
            try:
                # Basic validation
                if not consensus.fixture_id:
                    self.logger.warning("Consensus missing fixture_id")
                    continue

                if consensus.probability < Decimal('0') or consensus.probability > Decimal('1'):
                    self.logger.warning(f"Consensus probability out of range: {consensus.probability}")
                    continue

                if consensus.confidence < Decimal('0') or consensus.confidence > Decimal('1'):
                    self.logger.warning(f"Consensus confidence out of range: {consensus.confidence}")
                    continue

                if consensus.expected_value < Decimal('-1'):  # Allow small negative for noise
                    self.logger.warning(f"Consensus expected value suspiciously low: {consensus.expected_value}")
                    # Don't reject outright, but note it

                validated.append(consensus)

            except Exception as e:
                self.logger.warning(f"Error validating consensus: {e}")
                continue

        return validated

    async def _analyze_value_betting(
        self,
        consensus_list: List[EngineConsensus]
    ) -> List[Tuple[EngineConsensus, Decimal, Decimal]]:
        """
        Analyze consensus for value betting opportunities.

        Returns:
            List of tuples (consensus, expected_value, edge)
        """
        analyzed = []

        for consensus in consensus_list:
            try:
                # Expected value is already calculated in consensus
                expected_value = consensus.expected_value

                # Edge calculation: for unit stake, EV = edge
                # In general: edge = (probability * decimal_odds - 1)
                # We need to back-calculate the implied odds from EV and probability
                if consensus.probability > Decimal('0'):
                    implied_odds = (expected_value + Decimal('1')) / consensus.probability
                    edge = expected_value  # For unit stake, EV equals edge
                else:
                    edge = Decimal('0')

                analyzed.append((consensus, expected_value, edge))

            except Exception as e:
                self.logger.warning(f"Error analyzing value betting for consensus: {e}")
                # Still include with zero values
                analyzed.append((consensus, Decimal('0'), Decimal('0')))

        return analyzed

    async def _calculate_kelly_stakes(
        self,
        value_analyzed: List[Tuple[EngineConsensus, Decimal, Decimal]]
    ) -> List[Tuple[EngineConsensus, Decimal, Decimal, Decimal, Decimal]]:
        """
        Calculate Kelly criterion stakes for value bets.

        Returns:
            List of tuples (consensus, expected_value, edge, kelly_fraction, recommended_stake)
        """
        staked = []

        for consensus, expected_value, edge in value_analyzed:
            try:
                # Skip if no edge or negative expected value
                if edge <= Decimal('0') or expected_value <= Decimal('0'):
                    staked.append((consensus, expected_value, edge, Decimal('0'), Decimal('0')))
                    continue

                # Calculate Kelly fraction
                # We need the decimal odds to calculate Kelly properly
                # From edge and probability: edge = probability * decimal_odds - 1
                # So: decimal_odds = (edge + 1) / probability
                if consensus.probability > Decimal('0'):
                    decimal_odds = (edge + Decimal('1')) / consensus.probability
                    kelly_fraction = self._calculate_kelly_fraction(
                        consensus.probability,
                        decimal_odds
                    )
                else:
                    kelly_fraction = Decimal('0')

                # Apply maximum Kelly fraction from protected constants
                max_kelly = get_max_kelly_fraction()
                kelly_fraction = min(kelly_fraction, max_kelly)

                # For now, we'll calculate stake based on a unit bankroll
                # In practice, this would come from configuration/bankroll management
                bankroll = Decimal('1000')  # Example bankroll
                recommended_stake = bankroll * kelly_fraction

                # Apply maximum single bet exposure
                max_single_bet = get_max_single_bet_exposure()
                recommended_stake = min(recommended_stake, max_single_bet)

                staked.append((consensus, expected_value, edge, kelly_fraction, recommended_stake))

            except Exception as e:
                self.logger.warning(f"Error calculating Kelly stake: {e}")
                staked.append((consensus, expected_value, edge, Decimal('0'), Decimal('0')))

        return staked

    def _calculate_kelly_fraction(
        self,
        probability: Decimal,
        decimal_odds: Decimal
    ) -> Decimal:
        """
        Calculate Kelly Criterion for optimal bet sizing.

        f* = (bp - q) / b
        where:
          b = decimal_odds - 1 (net odds)
          p = probability of winning
          q = probability of losing = 1 - p
          f* = fraction of bankroll to bet
        """
        if probability < Decimal('0') or probability > Decimal('1'):
            return Decimal('0')
        if decimal_odds <= Decimal('1'):
            return Decimal('0')

        b = decimal_odds - Decimal('1')
        p = probability
        q = Decimal('1') - probability

        kelly = (b * p - q) / b if b != Decimal('0') else Decimal('0')

        # Ensure non-negative (no bet if negative EV)
        kelly = max(Decimal('0'), kelly)

        return kelly

    async def _apply_risk_management(
        self,
        staked: List[Tuple[EngineConsensus, Decimal, Decimal, Decimal, Decimal]]
    ) -> List[Tuple[EngineConsensus, Decimal, Decimal, Decimal, Decimal, Decimal]]:
        """
        Apply risk management rules including daily exposure limits.

        Returns:
            List of tuples (consensus, ev, edge, kelly, stake, adjusted_stake)
        """
        risk_managed = []

        for consensus, expected_value, edge, kelly_fraction, recommended_stake in staked:
            try:
                # Check daily exposure limit
                max_daily = get_max_daily_exposure()
                remaining_daily = max_daily - self.daily_exposure

                if remaining_daily <= Decimal('0'):
                    self.logger.info("Daily exposure limit reached")
                    adjusted_stake = Decimal('0')
                else:
                    # Stake cannot exceed remaining daily exposure
                    adjusted_stake = min(recommended_stake, remaining_daily)

                # Update daily exposure tracking (optimistic - assumes bet will be placed)
                self.daily_exposure += adjusted_stake

                risk_managed.append((
                    consensus,
                    expected_value,
                    edge,
                    kelly_fraction,
                    recommended_stake,
                    adjusted_stake
                ))

            except Exception as e:
                self.logger.warning(f"Error applying risk management: {e}")
                risk_managed.append((
                    consensus,
                    expected_value,
                    edge,
                    kelly_fraction,
                    recommended_stake,
                    Decimal('0')
                ))

        return risk_managed

    async def _apply_preliminary_filters(
        self,
        risk_managed: List[Tuple[EngineConsensus, Decimal, Decimal, Decimal, Decimal, Decimal]]
    ) -> List[TriggerResult]:
        """
        Apply preliminary filters: minimum edge, stake limits, phase restrictions, etc.

        Returns:
            List of TriggerResult objects
        """
        trigger_results = []

        for consensus, expected_value, edge, kelly_fraction, recommended_stake, adjusted_stake in risk_managed:
            try:
                trigger_passed = False
                trigger_reason = ""

                # Check if client publishing is enabled (for live betting)
                if not is_client_publish_enabled():
                    trigger_reason = "Client publishing disabled"
                # Check phase restrictions
                elif get_current_phase() < 3:  # Phase 3 is live publishing
                    trigger_reason = f"Phase {get_current_phase()} does not allow live publishing"
                # Check minimum edge requirement
                elif edge < get_min_edge_for_publish():
                    trigger_reason = f"Edge {edge:.4f} below minimum {get_min_edge_for_publish():.4f}"
                # Check for zero or negative stake
                elif adjusted_stake <= Decimal('0'):
                    trigger_reason = "Adjusted stake is zero or negative"
                # All checks passed
                else:
                    trigger_passed = True
                    trigger_reason = "All trigger criteria passed"

                trigger_result = TriggerResult(
                    consensus=consensus,
                    recommended_stake=adjusted_stake,
                    kelly_fraction=kelly_fraction,
                    expected_value=expected_value,
                    edge=edge,
                    trigger_passed=trigger_passed,
                    trigger_reason=trigger_reason
                )

                trigger_results.append(trigger_result)

            except Exception as e:
                self.logger.warning(f"Error applying preliminary filters: {e}")
                trigger_results.append(TriggerResult(
                    consensus=consensus,
                    trigger_passed=False,
                    trigger_reason=f"Filter error: {e}"
                ))

        return trigger_results

    async def _enhance_with_clv_feedback(
        self,
        trigger_results: List[TriggerResult],
        clv_legs: List
    ) -> List[TriggerResult]:
        """
        Enhance trigger results with CLV gate feedback (informational).

        This doesn't affect pass/fail but provides context for decision making.
        """
        enhanced = []

        for result in trigger_results:
            try:
                # We could calculate what the CLV impact would be if this bet won/lost
                # For now, we'll just add CLV gate status as information
                if result.trigger_passed:
                    # Get current CLV gate status
                    clv_status = self.clv_calculator.get_clv_gate_status()
                    # In a full implementation, we might add this to the result object
                    pass

                enhanced.append(result)

            except Exception as e:
                self.logger.warning(f"Error enhancing with CLV feedback: {e}")
                enhanced.append(result)

        return enhanced

    async def _prepare_final_output(
        self,
        trigger_results: List[TriggerResult]
    ) -> List[TriggerResult]:
        """
        Prepare final output for the PUBLISH pipeline.
        """
        # Sort by edge (descending) then by confidence (descending)
        def sort_key(result: TriggerResult) -> tuple:
            return (-result.edge, -result.consensus.confidence)

        sorted_results = sorted(trigger_results, key=sort_key)

        # Log summary statistics
        passed = [r for r in sorted_results if r.trigger_passed]
        self.logger.info(
            f"TRIGGER pipeline output: {len(passed)} passed, {len(sorted_results) - len(passed)} failed"
        )

        for result in passed:
            self.logger.debug(
                f"Trigger passed: {result.consensus.fixture_id} "
                f"{result.consensus.market_type.value} {result.consensus.selection} "
                f"EV={result.expected_value:.4f}, Edge={result.edge:.4f}, "
                f"Stake={result.recommended_stake:.2f}"
            )

        return sorted_results

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get current status of the TRIGGER pipeline components.
        """
        self._check_daily_reset()

        status = {
            "pipeline": "TRIGGER",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "current_phase": get_current_phase(),
                "paper_only": is_paper_only(),
                "client_publish_enabled": is_client_publish_enabled(),
                "max_kelly_fraction": float(get_max_kelly_fraction()),
                "max_daily_exposure": float(get_max_daily_exposure()),
                "max_single_bet_exposure": float(get_max_single_bet_exposure()),
                "min_edge_for_publish": float(get_min_edge_for_publish())
            },
            "state": {
                "daily_exposure": float(self.daily_exposure),
                "daily_exposure_remaining": float(get_max_daily_exposure() - self.daily_exposure),
                "last_reset": self.last_reset.isoformat() if hasattr(self, 'last_reset') else None
            },
            "components": {
                "clv_calculator": self.clv_calculator.__class__.__name__,
                "knowledge_service": self.knowledge_service.__class__.__name__
            }
        }

        return status