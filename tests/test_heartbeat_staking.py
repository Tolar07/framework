"""
Tests for heartbeat_staking module.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.heartbeat_staking import (
    calculate_next_stake,
    update_stake_on_result,
    get_stake_state,
    StakeState,
    DEFAULT_STARTING_BANKROLL,
    DEFAULT_STARTING_STAKE,
    KELLY_FRACTION,
    MIN_STAKE,
    MAX_STAKE_PCT,
)
from output.heartbeat import HeartbeatFixture, save_heartbeat_record, get_heartbeat_stats


class TestHeartbeatStaking:
    """Tests for heartbeat compounding staking logic."""

    def setup_method(self):
        """Ensure clean history file for each test."""
        history_file = Path("data/heartbeat/history.jsonl")
        if history_file.exists():
            history_file.unlink()

    def teardown_method(self):
        """Clean up after tests."""
        history_file = Path("data/heartbeat/history.jsonl")
        if history_file.exists():
            history_file.unlink()

    def test_calculate_next_stake_positive_edge(self):
        """Test Kelly calculation with positive edge."""
        stake = calculate_next_stake(
            current_bankroll=100.0,
            current_stake=1.0,
            edge=0.10,
            probability=0.60,
            price=1.67
        )
        # Should return a positive stake > MIN_STAKE
        assert stake >= MIN_STAKE
        assert stake <= 100.0 * MAX_STAKE_PCT  # Max 5% of bankroll

    def test_calculate_next_stake_negative_edge(self):
        """Test Kelly calculation with negative edge returns min stake."""
        stake = calculate_next_stake(
            current_bankroll=100.0,
            current_stake=1.0,
            edge=-0.05,
            probability=0.45,
            price=1.80
        )
        assert stake == MIN_STAKE

    def test_calculate_next_stake_invalid_price(self):
        """Test invalid price returns min stake."""
        stake = calculate_next_stake(
            current_bankroll=100.0,
            current_stake=1.0,
            edge=0.10,
            probability=0.60,
            price=0.0
        )
        assert stake == MIN_STAKE

    def test_update_stake_on_win(self):
        """Test bankroll update on win."""
        bankroll, stake = update_stake_on_result(
            current_bankroll=100.0,
            current_stake=1.0,
            result='WIN',
            price=2.0
        )
        assert bankroll == 101.0  # 1.0 * (2.0 - 1.0) = 1.0 profit
        assert stake == 1.0

    def test_update_stake_on_loss(self):
        """Test bankroll update on loss."""
        bankroll, stake = update_stake_on_result(
            current_bankroll=100.0,
            current_stake=1.0,
            result='LOSS',
            price=2.0
        )
        assert bankroll == 99.0
        assert stake == 1.0

    def test_update_stake_on_pending(self):
        """Test bankroll unchanged on PENDING/None."""
        bankroll, stake = update_stake_on_result(
            current_bankroll=100.0,
            current_stake=1.0,
            result='PENDING',
            price=2.0
        )
        assert bankroll == 100.0
        assert stake == 1.0

    def test_full_cycle_win_then_loss(self):
        """Test full cycle: win increases bankroll, loss decreases."""
        # Start fresh
        hb = HeartbeatFixture(
            fixture='Team A v Team B',
            kickoff_time='15:00',
            league='Test League',
            pick='BTTS Yes',
            probability=0.60,
            edge=0.10,
            market_type='BTTS',
            bookmaker='Bet365',
            price=1.67,
            verification_passed=False
        )

        # Process WIN
        save_heartbeat_record(hb, result='WIN')
        state = get_stake_state()
        assert state.wins == 1
        assert state.losses == 0
        assert state.bankroll > DEFAULT_STARTING_BANKROLL  # Profit

        # Process LOSS on next heartbeat
        hb2 = HeartbeatFixture(
            fixture='Team C v Team D',
            kickoff_time='16:00',
            league='Test League',
            pick='Over 2.5',
            probability=0.55,
            edge=0.05,
            market_type='O/U',
            bookmaker='Bet365',
            price=1.85,
            verification_passed=False
        )
        save_heartbeat_record(hb2, result='LOSS')
        state = get_stake_state()
        assert state.wins == 1
        assert state.losses == 1
        # Bankroll should be back down (lost the stake)
        assert state.bankroll < DEFAULT_STARTING_BANKROLL + 0.67  # Previous profit lost

    def test_get_stake_state_empty_history(self):
        """Test stake state with no history returns defaults."""
        # Ensure no history file
        history_file = Path("data/heartbeat/history.jsonl")
        if history_file.exists():
            history_file.unlink()

        state = get_stake_state()
        assert state.bankroll == DEFAULT_STARTING_BANKROLL
        assert state.current_stake == DEFAULT_STARTING_STAKE
        assert state.wins == 0
        assert state.losses == 0
        assert state.total == 0
        assert state.win_rate == 0.0

    def test_kelly_fraction_conservative(self):
        """Test that Kelly fraction is conservative (quarter-Kelly)."""
        # With p=0.60, price=1.67: b=0.67, Kelly = (0.67*0.60 - 0.40)/0.67 = 0.0015...
        # Quarter-Kelly ≈ 0.00037... of bankroll = very small
        stake = calculate_next_stake(
            current_bankroll=100.0,
            current_stake=1.0,
            edge=0.10,
            probability=0.60,
            price=1.67,
            kelly_fraction=0.25
        )
        # Should be clamped to MIN_STAKE (0.10) since Kelly is tiny
        assert stake == MIN_STAKE

    def test_max_stake_cap(self):
        """Test max stake is capped at 5% of bankroll."""
        # Use high edge/probability to generate large Kelly
        stake = calculate_next_stake(
            current_bankroll=100.0,
            current_stake=1.0,
            edge=0.50,
            probability=0.90,
            price=2.5,
            kelly_fraction=1.0  # Full Kelly for test
        )
        max_allowed = 100.0 * MAX_STAKE_PCT
        assert stake <= max_allowed + 0.01  # Small rounding tolerance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])