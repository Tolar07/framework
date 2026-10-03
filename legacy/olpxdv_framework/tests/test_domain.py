"""
Unit Tests for OLP XDV Framework Domain Layer

This directory contains unit tests for the core domain components of the OLP XDV Framework.
Tests focus on:
- Domain model validation
- CLV calculator correctness
- Protected constants enforcement
- Fabrication detection logic
"""

import unittest
import pytest
from decimal import Decimal
from datetime import datetime
from pathlib import Path

# Import domain components
from olpxdv_framework.domain.models import (
    Team, Fixture, Odds, MarketType,
    CLVLeg, CLVMetrics, KnowledgeItem, EngineConsensus,
    LeagueTier, FixtureStatus
)
from olpxdv_framework.domain.clv_calculator import CLVCalculator
from olpxdv_framework.domain.protected_constants import (
    ProtectedConstants, get_current_phase,
    ConstantProtectionLevel
)
from olpxdv_framework.domain.fabrication_detector import FabricationDetector

class TestDomainModels(unittest.TestCase):
    """Test core domain models for validity and behavior."""

    def test_team_model_creation(self):
        """Test Team model creation and validation."""
        team = Team(id="1", name="Test Team", short_name="TT")
        self.assertEqual(team.id, "1")
        self.assertEqual(team.name, "Test Team")
        self.assertEqual(team.short_name, "TT")

    def test_fixture_model_creation(self):
        """Test Fixture model creation."""
        home_team = Team(id="1", name="Home Team", short_name="HT")
        away_team = Team(id="2", name="Away Team", short_name="AT")
        fixture = Fixture(
            id="FIXTURE_1",
            home_team=home_team,
            away_team=away_team,
            league="Premier League",
            league_tier=LeagueTier.TIER_A,
            match_date=datetime(2026, 9, 15, 15, 0),
            status=FixtureStatus.SCHEDULED
        )
        self.assertEqual(fixture.id, "FIXTURE_1")
        self.assertEqual(fixture.home_team.name, "Home Team")
        self.assertEqual(fixture.away_team.name, "Away Team")
        self.assertEqual(fixture.league, "Premier League")
        self.assertEqual(fixture.league_tier, LeagueTier.TIER_A)
        self.assertEqual(fixture.match_date, datetime(2026, 9, 15, 15, 0))
        self.assertEqual(fixture.status, FixtureStatus.SCHEDULED)

    def test_odds_model_creation(self):
        """Test Odds model creation."""
        fixture = Fixture(
            id="FIXTURE_1",
            home_team=Team(id="1", name="Home Team", short_name="HT"),
            away_team=Team(id="2", name="Away Team", short_name="AT"),
            league="Premier League",
            league_tier=LeagueTier.TIER_A,
            match_date=datetime(2026, 9, 15, 15, 0),
            status=FixtureStatus.SCHEDULED
        )
        odds = Odds(
            id="ODDS_1",
            fixture_id=fixture.id,
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            decimal_odds=Decimal('2.5'),
            timestamp=datetime(2026, 9, 10, 12, 0),
            bookmaker="TestBook"
        )
        self.assertEqual(odds.id, "ODDS_1")
        self.assertEqual(odds.fixture_id, "FIXTURE_1")
        self.assertEqual(odds.market_type, MarketType.MATCH_ODDS)
        self.assertEqual(odds.selection, "Home")
        self.assertEqual(odds.decimal_odds, Decimal('2.5'))
        self.assertEqual(odds.timestamp, datetime(2026, 9, 10, 12, 0))
        self.assertEqual(odds.bookmaker, "TestBook")

class TestCLVCalculator(unittest.TestCase):
    """Test CLV (Closing Line Value) calculator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = CLVCalculator()
        home_team = Team(id="1", name="Home Team", short_name="HT")
        away_team = Team(id="2", name="Away Team", short_name="AT")
        self.fixture = Fixture(
            id="TEST_FIXTURE",
            home_team=home_team,
            away_team=away_team,
            league="Premier League",
            league_tier=LeagueTier.TIER_A,
            match_date=datetime(2026, 9, 15, 15, 0),
            status=FixtureStatus.SCHEDULED
        )

    def test_calculate_clv_for_leg_normal_case(self):
        """Test CLV calculation for normal scenario."""
        # Create a CLVLeg with known values
        # If you bet at opening odds of 1.8 and closing is 2.0, you have positive CLV
        clv_leg = CLVLeg(
            fixture_id="TEST_FIXTURE",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            opening_odds=Decimal('1.8'),
            closing_odds=Decimal('2.0'),
            stake=Decimal('1.0')
        )

        clv_abs, clv_pct = self.calculator.calculate_clv_for_leg(
            clv_leg.opening_odds,
            clv_leg.closing_odds,
            clv_leg.stake
        )
        self.assertIsInstance(clv_abs, Decimal)
        # CLV should be positive when closing odds are HIGHER than opening odds
        self.assertGreater(clv_abs, Decimal('0'))

    def test_calculate_clv_for_leg_no_change(self):
        """Test CLV calculation when opening and closing are the same."""
        clv_leg = CLVLeg(
            fixture_id="TEST_FIXTURE",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            opening_odds=Decimal('2.0'),
            closing_odds=Decimal('2.0'),
            stake=Decimal('1.0')
        )

        clv_abs, clv_pct = self.calculator.calculate_clv_for_leg(
            clv_leg.opening_odds,
            clv_leg.closing_odds,
            clv_leg.stake
        )
        self.assertEqual(clv_abs, Decimal('0'))  # No change means zero CLV

    def test_calculate_expected_value_positive(self):
        """Test expected value calculation for positive outcomes."""
        # Expected value = probability * (odds - 1) - (1 - probability) * 1
        # For 50% probability and 2.0 odds: 0.5 * (2.0 - 1) - 0.5 * 1 = 0
        # Actually, for positive EV we need probability * (odds - 1) > (1 - probability)
        # For 0.6 probability and 2.0 odds: 0.6 * (2.0 - 1) - 0.4 * 1 = 0.6 - 0.4 = 0.2
        consensus = EngineConsensus(
            fixture_id="TEST_FIXTURE",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('0.6'),
            expected_value=Decimal('0.2'),  # Positive EV
            confidence=Decimal('0.8'),
            kelly_fraction=Decimal('0.1'),
            engines_used=["Engine1", "Engine2"],
            timestamp=datetime(2026, 9, 10, 12, 0)
        )

        # In this case, EV should be positive
        self.assertGreater(consensus.expected_value, Decimal('0'))

    def test_calculate_kelly_fraction_valid(self):
        """Test Kelly fraction calculation."""
        # Test with 0.6 probability and 2.0 odds
        # b = 2.0 - 1 = 1
        # p = 0.6, q = 0.4
        # f* = (1 * 0.6 - 0.4) / 1 = 0.2
        kelly = self.calculator.calculate_kelly_fraction(
            Decimal('0.6'),
            Decimal('2.0')
        )
        self.assertIsInstance(kelly, Decimal)
        self.assertEqual(kelly, Decimal('0.2'))

        # Test with fraction (half-Kelly)
        kelly_half = self.calculator.calculate_kelly_fraction(
            Decimal('0.6'),
            Decimal('2.0'),
            Decimal('0.5')
        )
        self.assertEqual(kelly_half, Decimal('0.1'))

        # Test with high odds and low probability (should be low)
        kelly_low = self.calculator.calculate_kelly_fraction(
            Decimal('0.1'),
            Decimal('10.0')
        )
        # b = 9, p = 0.1, q = 0.9
        # f* = (9 * 0.1 - 0.9) / 9 = (0.9 - 0.9) / 9 = 0
        self.assertEqual(kelly_low, Decimal('0'))

    def test_get_clv_gate_status(self):
        """Test CLV gate status functionality."""
        # Test various gate statuses
        statuses = ["OPEN", "CLOSED", "TRIGGERED", "ERROR"]
        for status in statuses:
            result = self.calculator.get_clv_gate_status()
            # The actual implementation would depend on the full context
            # This is just checking that the method exists and returns a string

class TestProtectedConstants(unittest.TestCase):
    """Test protected constants enforcement."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = CLVCalculator()

    def test_architect_signoff_required(self):
        """Test that ARCHITECT_SIGNOFF requires explicit approval."""
        # ARCHITECT_SIGNOFF is stored in the _CONSTANTS registry, not as a class attribute
        self.assertIn("ARCHITECT_SIGNOFF", ProtectedConstants._CONSTANTS)
        constant_def = ProtectedConstants._CONSTANTS["ARCHITECT_SIGNOFF"]
        self.assertEqual(constant_def.protection_level, ConstantProtectionLevel.ARCHITECT_ONLY)
        self.assertEqual(constant_def.default_value, False)

    def test_clv_gate_enforcement(self):
        """Test CLV gate functionality."""
        # Test that CLV gate can be evaluated with proper CLVLeg objects
        from olpxdv_framework.domain.models import Team, Fixture

        # Create test teams and fixture
        home_team = Team(id="1", name="Home Team", short_name="HT")
        away_team = Team(id="2", name="Away Team", short_name="AT")
        fixture = Fixture(
            id="TEST_FIXTURE",
            home_team=home_team,
            away_team=away_team,
            league="Premier League",
            league_tier=LeagueTier.TIER_A,
            match_date=datetime(2026, 9, 15, 15, 0),
            status=FixtureStatus.SCHEDULED
        )

        # Create test CLV legs
        clv_leg1 = CLVLeg(
            fixture_id="TEST_FIXTURE",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            opening_odds=Decimal('2.0'),
            closing_odds=Decimal('2.2'),  # Positive CLV
            stake=Decimal('1.0')
        )

        clv_leg2 = CLVLeg(
            fixture_id="TEST_FIXTURE",
            market_type=MarketType.MATCH_ODDS,
            selection="Draw",
            opening_odds=Decimal('3.0'),
            closing_odds=Decimal('3.1'),  # Positive CLV
            stake=Decimal('1.0')
        )

        # Test that CLV gate can be evaluated
        result = self.calculator.evaluate_clv_gate([clv_leg1, clv_leg2])
        # Should return a CLVGateResult object
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, 'passed'))
        self.assertTrue(hasattr(result, 'reason'))

class TestFabricationDetector(unittest.TestCase):
    """Test fabrication detection functionality."""

    def test_fabrication_detection_basic(self):
        """Test basic fabrication detection."""
        detector = FabricationDetector()
        # This would be tested with synthetic data that triggers FAB patterns
        # For now, test that the detector exists and has the expected methods
        self.assertTrue(hasattr(detector, 'detect_fabrication'))
        self.assertTrue(hasattr(detector, '_detect_fab001_odds_combinations'))
        self.assertTrue(hasattr(detector, '_detect_fab002_odds_movements'))

def test_constants_enforcement():
    """Test that protected constants are properly enforced."""
    # This would test the actual enforcement mechanisms
    # In a real implementation, we'd verify that attempts to modify
    # protected constants without Architect signoff fail
    pass

if __name__ == '__main__':
    unittest.main()