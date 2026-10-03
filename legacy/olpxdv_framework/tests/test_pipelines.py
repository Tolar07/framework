"""
Unit Tests for OLP XDV Framework Application Pipelines

Tests the SCAN → TRIGGER → PUBLISH pipeline logic.
"""

import unittest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from olpxdv_framework.src.application.scan_pipeline import ScanPipeline
from olpxdv_framework.src.application.trigger_pipeline import TriggerPipeline, TriggerResult
from olpxdv_framework.src.application.publish_pipeline import PublishPipeline
from olpxdv_framework.src.domain.clv_calculator import CLVCalculator
from olpxdv_framework.src.domain.knowledge_persistence import KnowledgePersistenceService
from olpxdv_framework.src.domain.models import EngineConsensus, MarketType
from olpxdv_framework.src.domain.protected_constants import (
    get_current_phase, is_client_publish_enabled, is_paper_only
)


class TestScanPipeline(unittest.TestCase):
    """Test SCAN pipeline functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scan_pipeline = ScanPipeline()

    @patch('olpxdv_framework.src.application.scan_pipeline.ScanPipeline._fetch_upcoming_fixtures')
    @patch('olpxdv_framework.src.application.scan_pipeline.ScanPipeline._fetch_odds_for_fixtures')
    @patch('olpxdv_framework.src.application.scan_pipeline.ScanPipeline._generate_engine_consensus')
    @patch('olpxdv_framework.src.application.scan_pipeline.ScanPipeline._generate_scan_knowledge')
    def test_run_scan_cycle(self, mock_knowledge, mock_consensus, mock_odds, mock_fixtures):
        """Test full SCAN pipeline cycle execution."""
        # Mock the pipeline steps
        mock_fixtures.return_value = []
        mock_odds.return_value = []
        mock_consensus.return_value = []
        mock_knowledge.return_value = []

        # Run the pipeline
        result = self.scan_pipeline.run_scan_cycle()

        # Verify all steps were called
        mock_fixtures.assert_called_once()
        mock_odds.assert_called_once()
        mock_consensus.assert_called_once()
        mock_knowledge.assert_called_once()


class TestTriggerPipeline(unittest.TestCase):
    """Test TRIGGER pipeline functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.clv_calculator = CLVCalculator()
        self.knowledge_service = KnowledgePersistenceService()
        self.trigger_pipeline = TriggerPipeline(
            clv_calculator=self.clv_calculator,
            knowledge_service=self.knowledge_service
        )

    def test_validate_consensus(self):
        """Test consensus validation."""
        # Create valid consensus
        valid_consensus = EngineConsensus(
            fixture_id="TEST_001",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('0.55'),
            expected_value=Decimal('0.1'),
            confidence=Decimal('0.8'),
            engines_used=["Engine1", "Engine2"],
            timestamp=datetime.now()
        )

        # Invalid consensus (probability out of range)
        invalid_consensus = EngineConsensus(
            fixture_id="TEST_002",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('1.5'),  # Invalid: > 1
            expected_value=Decimal('0.1'),
            confidence=Decimal('0.8'),
            engines_used=["Engine1"],
            timestamp=datetime.now()
        )

        # Test validation logic
        validated = self.trigger_pipeline._validate_consensus([valid_consensus, invalid_consensus])

        # Should only include valid consensus
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0].fixture_id, "TEST_001")

    def test_calculate_kelly_stakes(self):
        """Test Kelly stake calculation."""
        consensus = EngineConsensus(
            fixture_id="TEST_001",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('0.6'),
            expected_value=Decimal('0.15'),
            confidence=Decimal('0.8'),
            engines_used=["Engine1"],
            timestamp=datetime.now()
        )

        # Test that the method calculates positive Kelly for positive EV
        edge = consensus.expected_value  # For unit stake, EV = edge
        analyzed = [(consensus, consensus.expected_value, edge)]

        # This would need proper async test setup
        # For now, we test the internal method directly
        import asyncio
        result = asyncio.run(self.trigger_pipeline._calculate_kelly_stakes(analyzed))

        # Should produce a stake for positive EV
        self.assertEqual(len(result), 1)
        consensus_obj, ev, edge_val, kelly, stake = result[0]
        self.assertGreaterEqual(kelly, Decimal('0'))

    def test_kelly_fraction_formula(self):
        """Test Kelly formula implementation directly."""
        # Kelly = (bp - q) / b
        # b = odds - 1 (net odds)
        # p = probability of winning
        # q = 1 - p

        # Test case: p=0.6, odds=2.0 (b=1.0)
        # Kelly = (1.0 * 0.6 - 0.4) / 1.0 = 0.2
        probability = Decimal('0.6')
        decimal_odds = Decimal('2.0')

        kelly = self.trigger_pipeline._calculate_kelly_fraction(probability, decimal_odds)
        self.assertEqual(kelly, Decimal('0.2'))

        # Test case: p=0.5, odds=2.0 (b=1.0)
        # Kelly = (1.0 * 0.5 - 0.5) / 1.0 = 0.0 (fair bet)
        probability = Decimal('0.5')
        kelly = self.trigger_pipeline._calculate_kelly_fraction(probability, decimal_odds)
        self.assertEqual(kelly, Decimal('0'))

        # Test case: p=0.4, odds=2.0 (b=1.0)
        # Kelly = (1.0 * 0.4 - 0.6) / 1.0 = -0.2 -> max with 0 = 0
        probability = Decimal('0.4')
        kelly = self.trigger_pipeline._calculate_kelly_fraction(probability, decimal_odds)
        self.assertEqual(kelly, Decimal('0'))

    def test_apply_risk_management(self):
        """Test risk management limits."""
        consensus = EngineConsensus(
            fixture_id="TEST_001",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('0.6'),
            expected_value=Decimal('0.15'),
            confidence=Decimal('0.8'),
            engines_used=["Engine1"],
            timestamp=datetime.now()
        )

        edge = Decimal('0.15')
        kelly = Decimal('0.2')
        recommended_stake = Decimal('200')  # 1000 bankroll * 0.2 Kelly
        adjusted_stake = Decimal('200')

        staked = [(consensus, Decimal('0.15'), edge, kelly, recommended_stake)]

        import asyncio
        result = asyncio.run(self.trigger_pipeline._apply_risk_management(staked))

        self.assertEqual(len(result), 1)
        _, _, _, _, _, final_stake = result[0]
        # Daily exposure limit should be applied
        self.assertLessEqual(final_stake, Decimal('100'))  # MAX_DAILY_EXPOSURE

    def test_apply_preliminary_filters(self):
        """Test preliminary filter logic."""
        consensus = EngineConsensus(
            fixture_id="TEST_001",
            market_type=MarketType.MATCH_ODDS,
            selection="Home",
            probability=Decimal('0.6'),
            expected_value=Decimal('0.15'),
            confidence=Decimal('0.8'),
            engines_used=["Engine1"],
            timestamp=datetime.now()
        )

        risk_managed = [(consensus, Decimal('0.15'), Decimal('0.15'), Decimal('0.2'), Decimal('200'), Decimal('100'))]

        import asyncio
        results = asyncio.run(self.trigger_pipeline._apply_preliminary_filters(risk_managed))

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsInstance(result, TriggerResult)
        self.assertEqual(result.consensus.fixture_id, "TEST_001")


class TestPublishPipeline(unittest.TestCase):
    """Test PUBLISH pipeline functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.clv_calculator = CLVCalculator()
        self.knowledge_service = KnowledgePersistenceService()
        self.publish_pipeline = PublishPipeline(
            clv_calculator=self.clv_calculator,
            knowledge_service=self.knowledge_service
        )

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        self.assertIsNotNone(self.publish_pipeline)
        self.assertIsNotNone(self.publish_pipeline.clv_calculator)
        self.assertIsNotNone(self.publish_pipeline.knowledge_service)


if __name__ == '__main__':
    unittest.main()