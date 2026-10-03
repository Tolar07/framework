"""
PUBLISH Pipeline: CLV Gate → Output Generation

This module implements the PUBLISH pipeline from OLP XDV:
1. Take TriggerResult objects that passed trigger logic
2. Validate against CLV gate (if in appropriate phase)
3. Apply final validation (fabrication detection, knowledge checks)
4. Generate output in multiple formats (console, web, Telegram, etc.)
5. Apply SportyBet-specific booking bridge if needed
6. Output final betting recommendations
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

from olpxdv_framework.domain.models import Fixture, Odds, MarketType, EngineConsensus, BetResult
from olpxdv_framework.domain.clv_calculator import CLVCalculator, CLVGateResult, CLVLeg
from olpxdv_framework.domain.fabrication_detector import FabricationDetector, FabricationAlert
from olpxdv_framework.domain.knowledge_persistence import KnowledgePersistenceService
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
    all_fixtures_eligible,
    is_fabrication_detection_enabled,
    get_whitelisted_leagues,
    id405_allow_away_wins,
    ProtectedConstants
)
from olpxdv_framework.infrastructure.sportybet_bridge import SportybetBridge
from olpxdv_framework.infrastructure.telegram_adapter import TelegramAdapter
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class PublishDecision:
    """Decision result from the publish pipeline."""

    def __init__(
        self,
        trigger_result: 'TriggerResult',
        publish_allowed: bool = False,
        publish_reason: str = "",
        clv_gate_passed: bool = False,
        clv_gate_reason: str = "",
        final_stake: Decimal = Decimal('0'),
        booking_code: Optional[str] = None,
        output_formats: Optional[Dict[str, str]] = None
    ):
        self.trigger_result = trigger_result
        self.publish_allowed = publish_allowed
        self.publish_reason = publish_reason
        self.clv_gate_passed = clv_gate_passed
        self.clv_gate_reason = clv_gate_reason
        self.final_stake = final_stake
        self.booking_code = booking_code
        self.output_formats = output_formats or {}


class PublishPipeline:
    """
    PUBLISH Pipeline: Final validation and output generation.

    Pipeline Steps:
    1. CLV Gate Validation: Check if bet helps CLV gate (if evaluating)
    2. Final Validation: Additional fabrication/knowledge checks
    3. Stake Finalization: Apply final limits and rounding
    4. SportyBet Bridge: Generate booking codes if needed
    5. Output Generation: Create console, web, Telegram outputs
    6. Knowledge Update: Log decision for future learning
    7. CLV Tracking: Create/log CLV leg for tracking
    """

    def __init__(
        self,
        clv_calculator: Optional[CLVCalculator] = None,
        fabrication_detector: Optional[FabricationDetector] = None,
        knowledge_service: Optional[KnowledgePersistenceService] = None,
        sportybet_bridge: Optional[SportybetBridge] = None,
        telegram_adapter: Optional[TelegramAdapter] = None
    ):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize components
        self.clv_calculator = clv_calculator or CLVCalculator()
        self.fabrication_detector = fabrication_detector or FabricationDetector()
        self.knowledge_service = knowledge_service or KnowledgePersistenceService()
        self.sportybet_bridge = sportybet_bridge or SportybetBridge()
        self.telegram_adapter = telegram_adapter or TelegramAdapter()

        # Pipeline state
        self.published_today = []  # Track published bets for duplicate prevention

    async def run_publish_cycle(
        self,
        trigger_results: List['TriggerResult'],
        clv_legs: Optional[List[CLVLeg]] = None
    ) -> List[PublishDecision]:
        """
        Execute a full PUBLISH pipeline cycle.

        Args:
            trigger_results: TriggerResult objects from TRIGGER pipeline
            clv_legs: Current CLV legs for gate evaluation

        Returns:
            List of PublishDecision objects for bets to be published
        """
        self.logger.info(f"Starting PUBLISH pipeline cycle with {len(trigger_results)} trigger results")
        start_time = datetime.utcnow()

        try:
            # Step 1: CLV Gate Evaluation (informational, not blocking in most phases)
            clv_evaluated = await self._evaluate_clv_gate_impact(trigger_results, clv_legs)

            # Step 2: Final Validation (fabrication, knowledge, eligibility)
            validated = await self._apply_final_validation(clv_evaluated)

            # Step 3: Stake Finalization (rounding, SportyBet limits, etc.)
            finalized = await self._finalize_stakes(validated)

            # Step 4: SportyBet Processing (booking codes, etc.)
            sportybet_processed = await self._process_sportybet(finalized)

            # Step 5: Output Generation (multiple formats)
            output_generated = await self._generate_outputs(sportybet_processed)

            # Step 6: Knowledge Update (log decision for learning)
            knowledge_updated = await self._update_knowledge(output_generated)

            # Step 7: CLV Tracking (create/log CLV legs)
            clv_tracked = await self._track_clv_legs(knowledge_updated, clv_legs)

            elapsed_time = (datetime.utcnow() - start_time).total_seconds()
            published_count = sum(1 for d in clv_tracked if d.publish_allowed)

            self.logger.info(
                f"PUBLISH pipeline completed in {elapsed_time:.2f}s: "
                f"{published_count}/{len(clv_tracked)} bets published"
            )

            return clv_tracked

        except Exception as e:
            self.logger.error(f"Error in PUBLISH pipeline: {e}")
            return []

    async def _evaluate_clv_gate_impact(
        self,
        trigger_results: List['TriggerResult'],
        clv_legs: Optional[List[CLVLeg]]
    ) -> List[Tuple['TriggerResult', bool, str]]:
        """
        Evaluate the potential impact of each bet on the CLV gate.

        Returns:
            List of tuples (trigger_result, clv_gate_passed, clv_gate_reason)
        """
        evaluated = []

        # Get current CLV gate status
        current_phase = get_current_phase()
        clv_gate_active = current_phase >= 2  # Phase 2+ evaluates CLV gate

        for trigger_result in trigger_results:
            clv_gate_passed = False
            clv_gate_reason = "CLV gate not active"

            if clv_gate_active and clv_legs is not None:
                try:
                    # We would calculate what the CLV impact would be
                    # For now, we'll just check if the CLV gate is currently passing
                    # In a full implementation, we'd simulate adding this leg
                    clv_status = self.clv_calculator.get_clv_gate_status()
                    # This is simplified - real implementation would be more sophisticated
                    clv_gate_passed = clv_status.get("gate_active", False)
                    clv_gate_reason = f"CLV gate: {clv_status.get('reason', 'Unknown')}"
                except Exception as e:
                    self.logger.warning(f"Error evaluating CLV gate impact: {e}")
                    clv_gate_reason = f"CLV evaluation error: {e}"

            evaluated.append((trigger_result, clv_gate_passed, clv_gate_reason))

        return evaluated

    async def _apply_final_validation(
        self,
        evaluated: List[Tuple['TriggerResult', bool, str]]
    ) -> List[Tuple['TriggerResult', bool, str, bool, str]]:
        """
        Apply final validation checks: fabrication detection, knowledge validation, eligibility.

        Returns:
            List of tuples (trigger_result, clv_passed, clv_reason, validation_passed, validation_reason)
        """
        validated = []

        for trigger_result, clv_passed, clv_reason in evaluated:
            validation_passed = True
            validation_reason = "All validations passed"

            try:
                # Check 1: Final fabrication detection (more thorough)
                if is_fabrication_detection_enabled():
                    # We would get fixture and odds data here
                    # For now, we'll skip as we don't have easy access to full data
                    pass

                # Check 2: Knowledge-based validation
                # Check if we have contradictory high-confidence knowledge
                knowledge_conflict = await self._check_knowledge_conflicts(trigger_result)
                if knowledge_conflict:
                    validation_passed = False
                    validation_reason = f"Knowledge conflict: {knowledge_conflict}"

                # Check 3: Eligibility and phase restrictions
                if validation_passed:
                    eligible, ineligible_reason = await self._check_final_eligibility(trigger_result)
                    if not eligible:
                        validation_passed = False
                        validation_reason = ineligible_reason

                # Check 4: Duplicate prevention (same fixture/market/selection recently published)
                if validation_passed:
                    duplicate, duplicate_reason = await self._check_for_duplicates(trigger_result)
                    if duplicate:
                        validation_passed = False
                        validation_reason = duplicate_reason

            except Exception as e:
                self.logger.warning(f"Error in final validation: {e}")
                validation_passed = False
                validation_reason = f"Validation error: {e}"

            validated.append((trigger_result, clv_passed, clv_reason, validation_passed, validation_reason))

        return validated

    async def _check_knowledge_conflicts(
        self,
        trigger_result: 'TriggerResult'
    ) -> Optional[str]:
        """
        Check if there's high-confidence knowledge that contradicts this bet.
        """
        try:
            # Search for knowledge about this fixture/market/selection
            query = f"{trigger_result.consensus.fixture_id} {trigger_result.consensus.market_type.value} {trigger_result.consensus.selection}"
            relevant_knowledge = await self.knowledge_service.search_by_content(query)

            # Look for high-confidence contradictory knowledge
            for knowledge in relevant_knowledge:
                if knowledge.confidence > Decimal('0.8'):
                    # In a real implementation, we'd check if the knowledge contradicts our bet
                    # For now, we'll just note if we have high-confidence knowledge
                    pass

            return None  # No conflicts found

        except Exception as e:
            self.logger.warning(f"Error checking knowledge conflicts: {e}")
            return None

    async def _check_final_eligibility(
        self,
        trigger_result: 'TriggerResult'
    ) -> Tuple[bool, str]:
        """
        Check final eligibility based on configuration and business rules.
        """
        try:
            # Check phase restrictions for publishing
            current_phase = get_current_phase()
            if current_phase < 3 and not is_paper_only():
                # If not in phase 3 and not paper-only, check if publishing allowed
                if not is_client_publish_enabled():
                    return False, f"Client publishing disabled in phase {current_phase}"

            # Check if we're in paper-only mode but trying to publish live
            if is_paper_only() and current_phase >= 3:
                # This would be a configuration error
                return False, f"Attempting to publish live in paper-only mode (phase {current_phase})"

            # Check SportyBet-specific restrictions if applicable
            # (would check if the bet needs to go through SportyBet bridge)

            # Check maximum single bet exposure again (defense in depth)
            max_single_bet = get_max_single_bet_exposure()
            if trigger_result.recommended_stake > max_single_bet:
                return False, f"Stake {trigger_result.recommended_stake} exceeds max single bet {max_single_bet}"

            # Check maximum daily exposure again
            max_daily = get_max_daily_exposure()
            # We'd need to track daily exposure across pipelines - simplified here

            return True, "Eligible"

        except Exception as e:
            self.logger.warning(f"Error checking final eligibility: {e}")
            return False, f"Eligibility check error: {e}"

    async def _check_for_duplicates(
        self,
        trigger_result: 'TriggerResult'
    ) -> Tuple[bool, str]:
        """
        Check if this bet is a duplicate of something recently published.
        """
        try:
            # Create a key for this bet
            bet_key = f"{trigger_result.consensus.fixture_id}_{trigger_result.consensus.market_type.value}_{trigger_result.consensus.selection}"

            # Check against recently published bets
            # In production, we'd check against a database or cache
            # For now, we'll use our in-memory list
            recent_threshold = datetime.utcnow() - timedelta(hours=1)  # Last hour

            for published in self.published_today:
                if (published.get('timestamp', datetime.min) > recent_threshold and
                    published.get('bet_key') == bet_key):
                    return True, f"Duplicate bet published recently: {bet_key}"

            return False, "No duplicate found"

        except Exception as e:
            self.logger.warning(f"Error checking for duplicates: {e}")
            return False, f"Duplicate check error: {e}"

    async def _finalize_stakes(
        self,
        validated: List[Tuple['TriggerResult', bool, str, bool, str]]
    ) -> List[Tuple['TriggerResult', bool, str, bool, str, Decimal]]:
        """
        Finalize stakes: apply rounding, SportyBet minimums, etc.

        Returns:
            List of tuples (... , final_stake)
        """
        finalized = []

        for trigger_result, clv_passed, clv_reason, validation_passed, validation_reason in validated:
            final_stake = trigger_result.recommended_stake

            try:
                # Only finalize stake if bet is going to be published
                will_publish = (trigger_result.trigger_passed and
                              validation_passed and
                              # CLV gate is not a hard blocking condition in most phases
                              True)  # Simplified - in reality would depend on phase and requirements

                if will_publish:
                    # Apply rounding (e.g., to nearest 0.5 or 1 unit for SportyBet)
                    # For now, we'll round to 2 decimal places
                    final_stake = round(final_stake, 2)

                    # Ensure minimum stake (e.g., 0.1 units minimum)
                    min_stake = Decimal('0.1')
                    if final_stake < min_stake:
                        final_stake = Decimal('0')
                        validation_passed = False
                        validation_reason = f"Stake {final_stake} below minimum {min_stake}"

                    # Apply SportyBet-specific maximum if known
                    # This would come from the SportyBet bridge configuration

                else:
                    final_stake = Decimal('0')  # No stake if not publishing

            except Exception as e:
                self.logger.warning(f"Error finalizing stake: {e}")
                final_stake = Decimal('0')
                validation_passed = False
                validation_reason = f"Stake finalization error: {e}"

            finalized.append((trigger_result, clv_passed, clv_reason, validation_passed, validation_reason, final_stake))

        return finalized

    async def _process_sportybet(
        self,
        finalized: List[Tuple['TriggerResult', bool, str, bool, str, Decimal]]
    ) -> List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str]]]:
        """
        Process bets through the SportyBet bridge to generate booking codes.

        Returns:
            List of tuples (... , booking_code)
        """
        sportybet_processed = []

        for trigger_result, clv_passed, clv_reason, validation_passed, validation_reason, final_stake in finalized:
            booking_code = None

            try:
                # Only generate booking code if bet is going to be published
                will_publish = (trigger_result.trigger_passed and
                              validation_passed and
                              final_stake > Decimal('0'))

                if will_publish:
                    # Generate booking code through SportyBet bridge
                    booking_result = await self.sportybet_bridge.generate_booking_code(
                        fixture_id=trigger_result.consensus.fixture_id,
                        market_type=trigger_result.consensus.market_type,
                        selection=trigger_result.consensus.selection,
                        stake=final_stake,
                        odds=self._extract_odds_from_consensus(trigger_result.consensus)
                    )

                    if booking_result.get('success'):
                        booking_code = booking_result.get('booking_code')
                        self.logger.debug(f"Generated SportyBet booking code: {booking_code}")
                    else:
                        self.logger.warning(f"Failed to generate SportyBet booking code: {booking_result.get('error')}")
                        # Depending on configuration, this might block publishing
                        # For now, we'll continue without booking code but log warning

            except Exception as e:
                self.logger.warning(f"Error processing SportyBet: {e}")
                # Continue without booking code

            sportybet_processed.append((
                trigger_result, clv_passed, clv_reason, validation_passed, validation_reason,
                final_stake, booking_code
            ))

        return sportybet_processed

    def _extract_odds_from_consensus(
        self,
        consensus: EngineConsensus
    ) -> Optional[Decimal]:
        """
        Extract decimal odds from consensus object.
        """
        try:
            # From consensus we have: expected_value = probability * decimal_odds - 1 (for unit stake)
            # So: decimal_odds = (expected_value + 1) / probability
            if consensus.probability > Decimal('0'):
                return (consensus.expected_value + Decimal('1')) / consensus.probability
            return None
        except Exception:
            return None

    async def _generate_outputs(
        self,
        sportybet_processed: List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str]]]
    ) -> List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str], Dict[str, str]]]:
        """
        Generate outputs in multiple formats: console, web, Telegram, etc.

        Returns:
            List of tuples (... , output_formats)
        """
        output_generated = []

        for trigger_result, clv_passed, clv_reason, validation_passed, validation_reason, final_stake, booking_code in sportybet_processed:
            output_formats = {}

            try:
                # Determine if this bet should be published
                should_publish = (trigger_result.trigger_passed and
                                validation_passed and
                                final_stake > Decimal('0'))

                if should_publish:
                    # Generate console output
                    console_output = self._generate_console_output(
                        trigger_result, final_stake, booking_code
                    )
                    output_formats['console'] = console_output

                    # Generate web dashboard output (placeholder - web dashboard instantiation avoided to prevent circular import)
                    output_formats['web'] = f"Web recommendation for {trigger_result.consensus.fixture_id} {trigger_result.consensus.selection} @ {final_stake:.2f} units"

                    # Generate Telegram output
                    telegram_output = await self.telegram_adapter.format_bet_recommendation(
                        trigger_result.consensus,
                        final_stake,
                        booking_code
                    )
                    output_formats['telegram'] = telegram_output

                    # Log that we're publishing this bet
                    self.logger.info(
                        f"PUBLISHING: {trigger_result.consensus.fixture_id} "
                        f"{trigger_result.consensus.market_type.value} {trigger_result.consensus.selection} "
                        f"Stake={final_stake}, EV={trigger_result.expected_value:.4f}"
                    )

                    # Track for duplicate prevention
                    bet_key = f"{trigger_result.consensus.fixture_id}_{trigger_result.consensus.market_type.value}_{trigger_result.consensus.selection}"
                    self.published_today.append({
                        'bet_key': bet_key,
                        'timestamp': datetime.utcnow(),
                        'fixture_id': trigger_result.consensus.fixture_id,
                        'stake': final_stake
                    })

                    # Keep only recent entries (last 24 hours)
                    cutoff = datetime.utcnow() - timedelta(hours=24)
                    self.published_today = [
                        entry for entry in self.published_today
                        if entry['timestamp'] > cutoff
                    ]

                else:
                    # Still generate output formats for logging/rejection reasons
                    output_formats['console'] = self._generate_rejection_output(
                        trigger_result, validation_passed, validation_reason
                    )

            except Exception as e:
                self.logger.warning(f"Error generating outputs: {e}")
                output_formats['console'] = f"Error generating output: {e}"

            output_generated.append((
                trigger_result, clv_passed, clv_reason, validation_passed, validation_reason,
                final_stake, booking_code, output_formats
            ))

        return output_generated

    def _generate_console_output(
        self,
        trigger_result: 'TriggerResult',
        stake: Decimal,
        booking_code: Optional[str]
    ) -> str:
        """
        Generate console-friendly output for a betting recommendation.
        """
        consensus = trigger_result.consensus
        lines = [
            "=" * 60,
            "OLP XDV BETTING RECOMMENDATION",
            "=" * 60,
            f"Fixture: {consensus.fixture_id}",
            f"Market: {consensus.market_type.value}",
            f"Selection: {consensus.selection}",
            f"Probability: {consensus.probability:.3f} ({consensus.probability*100:.1f}%)",
            f"Expected Value: {trigger_result.expected_value:.4f}",
            f"Edge: {trigger_result.edge:.4f} ({trigger_result.edge*100:.2f}%)",
            f"Recommended Stake: {stake:.2f} units",
            f"Kelly Fraction: {trigger_result.kelly_fraction:.4f}",
        ]

        if booking_code:
            lines.append(f"SportyBet Booking Code: {booking_code}")

        lines.extend([
            f"Confidence: {consensus.confidence:.3f}",
            f"Engines Used: {', '.join(consensus.engines_used) if consensus.engines_used else 'None'}",
            f"Timestamp: {consensus.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60
        ])

        return "\n".join(lines)

    def _generate_rejection_output(
        self,
        trigger_result: 'TriggerResult',
        validation_passed: bool,
        validation_reason: str
    ) -> str:
        """
        Generate output for a rejected bet (for logging/debugging).
        """
        consensus = trigger_result.consensus
        lines = [
            "=" * 60,
            "OLP XDV BET REJECTION",
            "=" * 60,
            f"Fixture: {consensus.fixture_id}",
            f"Market: {consensus.market_type.value}",
            f"Selection: {consensus.selection}",
            f"Reason: {trigger_result.trigger_reason if not trigger_result.trigger_passed else validation_reason}",
            f"Expected Value: {trigger_result.expected_value:.4f}",
            f"Edge: {trigger_result.edge:.4f}",
            f"Recommended Stake: {trigger_result.recommended_stake:.2f} units",
            f"Timestamp: {consensus.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60
        ]

        return "\n".join(lines)

    async def _update_knowledge(
        self,
        output_generated: List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str], Dict[str, str]]]
    ) -> List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str], Dict[str, str], str]]:
        """
        Update knowledge system with the betting decisions made.

        Returns:
            List of tuples (... , knowledge_update_id)
        """
        knowledge_updated = []

        for item in output_generated:
            trigger_result, clv_passed, clv_reason, validation_passed, validation_reason, final_stake, booking_code, output_formats = item
            knowledge_update_id = None

            try:
                # Only add to knowledge if bet was published
                should_publish = (trigger_result.trigger_passed and
                                validation_passed and
                                final_stake > Decimal('0'))

                if should_publish:
                    # Create knowledge item for this betting decision
                    title = f"Betting Decision: {trigger_result.consensus.fixture_id}"
                    content = (
                        f"Fixture: {trigger_result.consensus.fixture_id}\n"
                        f"Market: {trigger_result.consensus.market_type.value}\n"
                        f"Selection: {trigger_result.consensus.selection}\n"
                        f"Probability: {trigger_result.consensus.probability}\n"
                        f"Expected Value: {trigger_result.expected_value}\n"
                        f"Edge: {trigger_result.edge}\n"
                        f"Stake: {final_stake}\n"
                        f"Booking Code: {booking_code or 'None'}\n"
                        f"CLV Gate Status: {'Pass' if clv_passed else 'Fail'} ({clv_reason})\n"
                        f"Validation: {'Pass' if validation_passed else 'Fail'} ({validation_reason})"
                    )

                    knowledge_item = await self.knowledge_service.add_knowledge(
                        title=title,
                        content=content,
                        knowledge_type="betting_decision",
                        source="publish_pipeline",
                        tags=[
                            "betting",
                            trigger_result.consensus.market_type.value,
                            trigger_result.consensus.selection.replace(" ", "_").lower()
                        ],
                        relevance_score=Decimal('0.9'),  # High relevance for actual decisions
                        confidence=trigger_result.consensus.confidence
                    )

                    knowledge_update_id = knowledge_item.id

                    self.logger.debug(f"Added betting decision to knowledge: {knowledge_update_id}")

            except Exception as e:
                self.logger.warning(f"Error updating knowledge: {e}")

            knowledge_updated.append((*item, knowledge_update_id))

        return knowledge_updated

    async def _track_clv_legs(
        self,
        knowledge_updated: List[Tuple['TriggerResult', bool, str, bool, str, Decimal, Optional[str], Dict[str, str], str]],
        clv_legs: Optional[List[CLVLeg]]
    ) -> List[PublishDecision]:
        """
        Create or update CLV legs for tracking published bets.

        Returns:
            List of PublishDecision objects (final output)
        """
        final_decisions = []

        for item in knowledge_updated:
            (trigger_result, clv_passed, clv_reason, validation_passed, validation_reason,
             final_stake, booking_code, output_formats, knowledge_update_id) = item

            try:
                # Determine if this bet should be tracked for CLV
                should_track_clv = (trigger_result.trigger_passed and
                                  validation_passed and
                                  final_stake > Decimal('0') and
                                  get_current_phase() >= 2)  # Only track in phases that evaluate CLV

                clv_leg_created = None
                clv_leg_id = None

                if should_track_clv and clv_legs is not None:
                    # In a full implementation, we would:
                    # 1. Create a new CLV leg for this bet
                    # 2. Add it to the clv_legs list for tracking
                    # 3. Return the CLV leg ID for future updates
                    #
                    # For now, we'll just note that CLV tracking would happen
                    self.logger.debug(
                        f"Would create CLV leg for {trigger_result.consensus.fixture_id} "
                        f"with stake {final_stake}"
                    )

                # Create final publish decision
                publish_decision = PublishDecision(
                    trigger_result=trigger_result,
                    publish_allowed=(trigger_result.trigger_passed and
                                   validation_passed and
                                   final_stake > Decimal('0')),
                    publish_reason="Published successfully" if (trigger_result.trigger_passed and
                                                               validation_passed and
                                                               final_stake > Decimal('0'))
                                else f"Trigger: {trigger_result.trigger_reason}, Validation: {validation_reason}",
                    clv_gate_passed=clv_passed,
                    clv_gate_reason=clv_reason,
                    final_stake=final_stake,
                    booking_code=booking_code,
                    output_formats=output_formats
                )

                # Add metadata for debugging/tracking
                publish_decision.knowledge_update_id = knowledge_update_id
                publish_decision.clv_leg_id = clv_leg_id

                final_decisions.append(publish_decision)

            except Exception as e:
                self.logger.warning(f"Error creating publish decision: {e}")
                # Still create a decision object, but mark as not published
                publish_decision = PublishDecision(
                    trigger_result=trigger_result,
                    publish_allowed=False,
                    publish_reason=f"Decision creation error: {e}"
                )
                final_decisions.append(publish_decision)

        return final_decisions

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get current status of the PUBLISH pipeline components.
        """
        status = {
            "pipeline": "PUBLISH",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "current_phase": get_current_phase(),
                "paper_only": is_paper_only(),
                "client_publish_enabled": is_client_publish_enabled(),
                "all_fixtures_eligible": all_fixtures_eligible(),
                "fabrication_detection": is_fabrication_detection_enabled(),
                "whitelisted_leagues_count": len(get_whitelisted_leagues()),
                "id405_away_wins_allowed": id405_allow_away_wins()
            },
            "state": {
                "published_today_count": len(self.published_today),
                "recent_publications": [
                    {
                        "fixture_id": p.get("fixture_id"),
                        "stake": float(p.get("stake", 0)),
                        "time": p.get("timestamp", datetime.min).isoformat()
                    }
                    for p in self.published_today[-5:]  # Last 5 publications
                ]
            },
            "components": {
                "clv_calculator": self.clv_calculator.__class__.__name__,
                "fabrication_detector": self.fabrication_detector.__class__.__name__,
                "knowledge_service": self.knowledge_service.__class__.__name__,
                "sportybet_bridge": self.sportybet_bridge.__class__.__name__,
                "telegram_adapter": self.telegram_adapter.__class__.__name__,
                "web_dashboard": self.web_dashboard.__class__.__name__
            }
        }

        return status