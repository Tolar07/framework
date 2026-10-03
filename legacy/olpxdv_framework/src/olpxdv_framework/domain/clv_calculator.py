"""
CLV Feedback Loop Calculator

This module implements the Closing Line Value (CLV) feedback loop,
which is the core performance measurement system of the OLP XDV framework.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
import statistics
from dataclasses import dataclass, field

from .models import CLVLeg, CLVMetrics, Fixture, Odds, MarketType, BetResult
from .protected_constants import (
    get_clv_min_legs, get_clv_mean_threshold, get_current_phase,
    is_paper_only, is_client_publish_enabled, ProtectedConstants,
    get_max_kelly_fraction
)

logger = logging.getLogger(__name__)


@dataclass
class CLVGateResult:
    """Result of CLV gate evaluation"""
    passed: bool
    reason: str
    metrics: CLVMetrics
    sample_size: int
    mean_clv: Decimal
    clv_percentage: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CLVCalculator:
    """
    Calculates and manages Closing Line Value (CLV) feedback loop.

    The CLV feedback loop measures the performance of the prediction engine
    by comparing opening odds (when bets are placed) vs closing odds
    (just before event start).
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate_clv_for_leg(
        self,
        opening_odds: Decimal,
        closing_odds: Decimal,
        stake: Decimal = Decimal('1.0')
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate CLV for a single leg.

        Returns:
            Tuple of (clv_absolute, clv_percentage)
        """
        if opening_odds <= Decimal('0'):
            raise ValueError("Opening odds must be positive")
        if closing_odds < Decimal('0'):
            raise ValueError("Closing odds cannot be negative")

        clv_absolute = (closing_odds - opening_odds) * stake
        clv_percentage = (clv_absolute / (opening_odds * stake)) * Decimal('100') if opening_odds > Decimal('0') else Decimal('0')

        return clv_absolute, clv_percentage

    def evaluate_clv_gate(self, legs: List[CLVLeg]) -> CLVGateResult:
        """
        Evaluate whether the CLV gate should pass.

        The gate passes when:
        1. Minimum number of legs requirement is met
        2. Mean CLV is positive (above threshold)
        3. Current phase allows evaluation

        Returns:
            CLVGateResult with pass/fail decision and metrics
        """
        # Check if we're in a phase that evaluates CLV gate
        current_phase = get_current_phase()
        if current_phase < 2:  # Phase 1 is paper-only, no CLV gate
            return CLVGateResult(
                passed=False,
                reason=f"Phase {current_phase} does not evaluate CLV gate",
                metrics=CLVMetrics(),
                sample_size=0,
                mean_clv=Decimal('0'),
                clv_percentage=Decimal('0')
            )

        # Filter for valid, closed legs
        valid_closed_legs = [
            leg for leg in legs
            if leg.is_valid and leg.closed_at is not None and leg.closing_odds > Decimal('0')
        ]

        sample_size = len(valid_closed_legs)
        min_legs_required = get_clv_min_legs()

        if sample_size < min_legs_required:
            return CLVGateResult(
                passed=False,
                reason=f"Insufficient sample size: {sample_size} < {min_legs_required}",
                metrics=CLVMetrics(),
                sample_size=sample_size,
                mean_clv=Decimal('0'),
                clv_percentage=Decimal('0')
            )

        # Calculate metrics
        metrics = CLVMetrics()
        metrics.calculate_from_legs(valid_closed_legs)

        mean_clv = metrics.mean_clv
        clv_threshold = get_clv_mean_threshold()

        # Check if mean CLV meets threshold
        clv_gate_passed = mean_clv >= clv_threshold

        # Additional checks for statistical significance
        if sample_size >= ProtectedConstants.get("MIN_SAMPLE_SIZE_FOR_CLV"):
            # Could add more sophisticated statistical tests here
            pass

        reason_parts = []
        if clv_gate_passed:
            reason_parts.append(f"Mean CLV {mean_clv:.4f}% >= threshold {clv_threshold}%")
        else:
            reason_parts.append(f"Mean CLV {mean_clv:.4f}% < threshold {clv_threshold}%")

        reason_parts.append(f"Sample size: {sample_size} legs")

        return CLVGateResult(
            passed=clv_gate_passed,
            reason="; ".join(reason_parts),
            metrics=metrics,
            sample_size=sample_size,
            mean_clv=mean_clv,
            clv_percentage=metrics.clv_percentage
        )

    def calculate_expected_value(
        self,
        probability: Decimal,
        decimal_odds: Decimal,
        stake: Decimal = Decimal('1.0')
    ) -> Decimal:
        """
        Calculate Expected Value (EV) of a bet.

        EV = (probability * decimal_odds * stake) - stake
        """
        if probability < Decimal('0') or probability > Decimal('1'):
            raise ValueError("Probability must be between 0 and 1")
        if decimal_odds <= Decimal('0'):
            raise ValueError("Decimal odds must be positive")

        expected_return = probability * decimal_odds * stake
        ev = expected_return - stake
        return ev

    def calculate_kelly_fraction(
        self,
        probability: Decimal,
        decimal_odds: Decimal,
        fraction: Decimal = Decimal('1.0')
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
            raise ValueError("Probability must be between 0 and 1")
        if decimal_odds <= Decimal('1'):
            raise ValueError("Decimal odds must be greater than 1 for positive EV")

        b = decimal_odds - Decimal('1')
        p = probability
        q = Decimal('1') - probability

        kelly = (b * p - q) / b if b != Decimal('0') else Decimal('0')

        # Apply fraction (e.g., half-Kelly)
        kelly = kelly * fraction

        # Ensure non-negative (no bet if negative EV)
        kelly = max(Decimal('0'), kelly)

        # Apply maximum Kelly fraction from protected constants
        max_kelly = get_max_kelly_fraction()
        kelly = min(kelly, max_kelly)

        return kelly

    def calculate_recommended_stake(
        self,
        probability: Decimal,
        decimal_odds: Decimal,
        bankroll: Decimal,
        use_kelly: bool = True
    ) -> Decimal:
        """
        Calculate recommended stake based on Kelly criterion or flat betting.

        Args:
            probability: Estimated probability of winning
            decimal_odds: Decimal odds being offered
            bankroll: Total bankroll available
            use_kelly: Whether to use Kelly criterion or flat betting

        Returns:
            Recommended stake amount
        """
        if use_kelly:
            kelly_fraction = self.calculate_kelly_fraction(probability, decimal_odds)
            stake = bankroll * kelly_fraction
        else:
            # Flat betting - 1% of bankroll per bet
            stake = bankroll * Decimal('0.01')

        # Apply maximum single bet exposure limit
        max_single_bet = ProtectedConstants.get("MAX_SINGLE_BET_EXPOSURE")
        stake = min(stake, max_single_bet)

        return stake

    def log_clv_leg(
        self,
        fixture_id: str,
        market_type: MarketType,
        selection: str,
        opening_odds: Decimal,
        stake: Decimal = Decimal('1.0')
    ) -> CLVLeg:
        """
        Create and log a new CLV leg (paper bet).

        This represents placing a bet at opening odds for tracking purposes.
        """
        leg = CLVLeg(
            fixture_id=fixture_id,
            market_type=market_type,
            selection=selection,
            opening_odds=opening_odds,
            stake=stake
        )

        logger.info(
            f"Logged CLV leg: {leg.id} - {fixture_id} {market_type.value} {selection} "
            f"@ {opening_odds} (stake: {stake})"
        )

        return leg

    def close_clv_leg(
        self,
        leg: CLVLeg,
        closing_odds: Decimal,
        actual_result: Optional[BetResult] = None
    ) -> CLVLeg:
        """
        Close a CLV leg with actual closing odds and result.

        Args:
            leg: The CLV leg to close
            closing_odds: The actual closing odds
            actual_result: The actual result (if known), otherwise calculated

        Returns:
            Updated CLV leg
        """
        if leg.closed_at is not None:
            raise ValueError("Leg is already closed")

        # Determine actual result if not provided
        if actual_result is None:
            # This would typically come from match results
            # For now, we'll leave it as PENDING and let external systems update it
            actual_result = BetResult.PENDING

        leg.close_leg(closing_odds, actual_result)

        logger.info(
            f"Closed CLV leg: {leg.id} - CLV: {leg.clv_value:.4f} "
            f"({leg.clv_percentage:.2f}%) - Result: {leg.result.value}"
        )

        return leg

    def get_clv_performance_summary(self, legs: List[CLVLeg]) -> dict:
        """
        Get a comprehensive CLV performance summary.

        Returns:
            Dictionary with various performance metrics
        """
        valid_closed_legs = [
            leg for leg in legs
            if leg.is_valid and leg.closed_at is not None
        ]

        if not valid_closed_legs:
            return {
                "total_legs": 0,
                "valid_legs": 0,
                "message": "No valid closed legs available"
            }

        metrics = CLVMetrics()
        metrics.calculate_from_legs(valid_closed_legs)

        # Calculate additional statistics
        clv_values = [float(leg.clv_value) for leg in valid_closed_legs]
        clv_percentages = [float(leg.clv_percentage) for leg in valid_closed_legs]

        summary = {
            "total_legs": len(legs),
            "valid_legs": len(valid_closed_legs),
            "winning_legs": metrics.winning_legs,
            "losing_legs": metrics.valid_legs - metrics.winning_legs,
            "push_legs": sum(1 for leg in valid_closed_legs if leg.result == BetResult.PUSH),
            "total_stake": float(metrics.total_stake),
            "total_return": float(metrics.total_return),
            "total_clv": float(metrics.total_clv),
            "mean_clv": float(metrics.mean_clv),
            "clv_percentage": float(metrics.clv_percentage),
            "yield_percentage": float(metrics.yield_percentage),
            "hit_rate": float(metrics.hit_rate),
            "clv_std_dev": float(statistics.stdev(clv_values)) if len(clv_values) > 1 else 0.0,
            "clv_sharpe": float(metrics.mean_clv / statistics.stdev(clv_values)) if len(clv_values) > 1 and statistics.stdev(clv_values) > 0 else 0.0,
            "best_clv": max(clv_percentages) if clv_percentages else 0.0,
            "worst_clv": min(clv_percentages) if clv_percentages else 0.0,
            "consecutive_wins": self._calculate_consecutive_wins(valid_closed_legs),
            "consecutive_losses": self._calculate_consecutive_losses(valid_closed_legs)
        }

        return summary

    def _calculate_consecutive_wins(self, legs: List[CLVLeg]) -> int:
        """Calculate maximum consecutive wins"""
        max_consecutive = 0
        current_consecutive = 0

        for leg in legs:
            if leg.result == BetResult.WIN:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def _calculate_consecutive_losses(self, legs: List[CLVLeg]) -> int:
        """Calculate maximum consecutive losses"""
        max_consecutive = 0
        current_consecutive = 0

        for leg in legs:
            if leg.result == BetResult.LOSS:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def should_publish_bet(
        self,
        probability: Decimal,
        decimal_odds: Decimal,
        expected_value: Optional[Decimal] = None
    ) -> Tuple[bool, str]:
        """
        Determine whether a bet should be published based on CLV gate and edge requirements.

        Returns:
            Tuple of (should_publish, reason)
        """
        # Check if client publishing is enabled
        if not is_client_publish_enabled():
            return False, "Client publishing is disabled"

        # Check framework phase
        current_phase = get_current_phase()
        if current_phase < 3:  # Phase 3 is live publishing
            return False, f"Phase {current_phase} does not allow live publishing"

        # Calculate expected value if not provided
        if expected_value is None:
            expected_value = self.calculate_expected_value(probability, decimal_odds)

        # Check for positive expected value
        if expected_value <= Decimal('0'):
            return False, f"Non-positive expected value: {expected_value}"

        # Check minimum edge requirement
        min_edge = ProtectedConstants.get("MIN_EDGE_FOR_PUBLISH")
        edge = expected_value  # For unit stake, EV = edge
        if edge < min_edge:
            return False, f"Edge {edge:.4f} below minimum {min_edge:.4f}"

        # Additional checks could go here (model confidence, etc.)

        return True, f"Bet meets publishing criteria: EV={expected_value:.4f}, Edge={edge:.4f}"

    def get_clv_gate_status(self) -> dict:
        """
        Get current CLV gate status for monitoring/display.

        Returns:
            Dictionary with gate status information
        """
        # This would typically be called with actual legs data
        # For now, return structure for frontend consumption
        return {
            "gate_active": get_current_phase() >= 2,
            "min_legs_required": get_clv_min_legs(),
            "mean_clv_threshold": float(get_clv_mean_threshold()),
            "current_phase": get_current_phase(),
            "is_paper_only": is_paper_only(),
            "client_publish_enabled": is_client_publish_enabled(),
            "last_evaluation": datetime.utcnow().isoformat()  # Would be actual timestamp
        }