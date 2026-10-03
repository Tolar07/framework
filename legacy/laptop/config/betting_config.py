"""
Betting configuration for OLP XDV
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BettingConfig:
    """Betting-related configuration parameters."""

    # Odds thresholds and limits
    max_odds_cap: float = 1.50
    min_odds_floor: float = 1.20
    preferred_odds_ceiling: float = 1.50

    # Betting limits and parameters
    max_accumulator_legs: int = 5
    min_accumulator_legs: int = 3
    max_single_bets: int = 10
    minimum_edge_threshold: float = 0.01
    kelly_fraction: float = 0.5
    max_stake_percentage: float = 0.05

    # Verification and gating
    verify_min_sources: int = 2
    clv_gate_min_legs: int = 12
    clv_gate_threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "max_odds_cap": self.max_odds_cap,
            "min_odds_floor": self.min_odds_floor,
            "preferred_odds_ceiling": self.preferred_odds_ceiling,
            "max_accumulator_legs": self.max_accumulator_legs,
            "min_accumulator_legs": self.min_accumulator_legs,
            "max_single_bets": self.max_single_bets,
            "minimum_edge_threshold": self.minimum_edge_threshold,
            "kelly_fraction": self.kelly_fraction,
            "max_stake_percentage": self.max_stake_percentage,
            "verify_min_sources": self.verify_min_sources,
            "clv_gate_min_legs": self.clv_gate_min_legs,
            "clv_gate_threshold": self.clv_gate_threshold
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BettingConfig":
        """Create configuration from dictionary."""
        return cls(
            max_odds_cap=data.get("max_odds_cap", 1.50),
            min_odds_floor=data.get("min_odds_floor", 1.20),
            preferred_odds_ceiling=data.get("preferred_odds_ceiling", 1.50),
            max_accumulator_legs=data.get("max_accumulator_legs", 5),
            min_accumulator_legs=data.get("min_accumulator_legs", 3),
            max_single_bets=data.get("max_single_bets", 10),
            minimum_edge_threshold=data.get("minimum_edge_threshold", 0.01),
            kelly_fraction=data.get("kelly_fraction", 0.5),
            max_stake_percentage=data.get("max_stake_percentage", 0.05),
            verify_min_sources=data.get("verify_min_sources", 2),
            clv_gate_min_legs=data.get("clv_gate_min_legs", 12),
            clv_gate_threshold=data.get("clv_gate_threshold", 0.0)
        )