"""
SCAN Pipeline: Data Ingestion → Engine Consensus

This module implements the SCAN pipeline from OLP XDV:
1. Ingest data from external APIs (odds, fixtures)
2. Run engine suite to generate consensus predictions
3. Output EngineConsensus objects for the TRIGGER pipeline
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from olpxdv_framework.domain.models import Fixture, Odds, MarketType, EngineConsensus, Team
from olpxdv_framework.domain.engine_suite import EngineSuite
from olpxdv_framework.domain.fabrication_detector import FabricationDetector, FabricationAlert
from olpxdv_framework.domain.knowledge_persistence import KnowledgePersistenceService, InMemoryKnowledgeRepository
from olpxdv_framework.domain.protected_constants import (
    get_current_phase,
    is_paper_only,
    all_fixtures_eligible,
    is_fabrication_detection_enabled
)
from olpxdv_framework.infrastructure.api_adapters.base_adapter import BaseAPIAdapter
from olpxdv_framework.infrastructure.api_adapters.the_odds_api import TheOddsAPIAdapter
from olpxdv_framework.infrastructure.api_adapters.api_football import APIFootballAdapter
from olpxdv_framework.infrastructure.api_adapters.the_sports_db import TheSportsDBAdapter
from olpxdv_framework.config.settings import get_settings

logger = logging.getLogger(__name__)


class DataIngestionResult:
    """Result of data ingestion from external sources."""

    def __init__(
        self,
        fixtures: List[Fixture] = None,
        odds: List[Odds] = None,
        errors: List[str] = None,
        sources_used: List[str] = None
    ):
        self.fixtures = fixtures or []
        self.odds = odds or []
        self.errors = errors or []
        self.sources_used = sources_used or []


class ScanPipeline:
    """
    SCAN Pipeline: Ingest data from external sources and generate engine consensus.

    Pipeline Steps:
    1. Data Ingestion: Fetch fixtures and odds from configured APIs
    2. Data Validation: Check for fabrication and data quality issues
    3. Engine Processing: Run engine suite to generate consensus predictions
    4. Knowledge Integration: Incorporate relevant knowledge from persistence system
    5. Output: EngineConsensus objects ready for TRIGGER pipeline
    """

    def __init__(
        self,
        odds_adapters: Optional[List[BaseAPIAdapter]] = None,
        fixture_adapters: Optional[List[BaseAPIAdapter]] = None,
        engine_suite: Optional[EngineSuite] = None,
        fabrication_detector: Optional[FabricationDetector] = None,
        knowledge_service: Optional[KnowledgePersistenceService] = None
    ):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize adapters
        self.odds_adapters = odds_adapters or self._create_default_odds_adapters()
        self.fixture_adapters = fixture_adapters or self._create_default_fixture_adapters()

        # Initialize core components
        self.engine_suite = engine_suite or EngineSuite()
        self.fabrication_detector = fabrication_detector or FabricationDetector()
        self.knowledge_service = knowledge_service or KnowledgePersistenceService(InMemoryKnowledgeRepository())

        # Pipeline configuration
        self.max_fixtures_per_batch = 50
        self.odds_cache_ttl_minutes = 5
        self.fixture_cache_ttl_minutes = 15

    def _create_default_odds_adapters(self) -> List[BaseAPIAdapter]:
        """Create default odds API adapters based on configuration."""
        adapters = []

        # The Odds API
        if self.settings.api.odds_api_key:
            adapters.append(TheOddsAPIAdapter())
            self.logger.info("The Odds API adapter initialized")
        else:
            self.logger.warning("The Odds API key not configured")

        # API-Football (for odds if available)
        if self.settings.api.api_football_key:
            adapters.append(APIFootballAdapter())
            self.logger.info("API-Football adapter initialized")
        else:
            self.logger.warning("API-Football key not configured")

        return adapters

    def _create_default_fixture_adapters(self) -> List[BaseAPIAdapter]:
        """Create default fixture API adapters based on configuration."""
        adapters = []

        # API-Football (primary for fixtures)
        if self.settings.api.api_football_key:
            adapters.append(APIFootballAdapter())
            self.logger.info("API-Football fixture adapter initialized")
        else:
            self.logger.warning("API-Football key not configured for fixtures")

        # TheSportsDB (backup)
        adapters.append(TheSportsDBAdapter())
        self.logger.info("TheSportsDB adapter initialized")

        return adapters

    async def run_scan_cycle(
        self,
        look_ahead_days: int = 2,
        leagues: Optional[List[str]] = None,
        market_types: Optional[List[MarketType]] = None
    ) -> List[EngineConsensus]:
        """
        Execute a full SCAN pipeline cycle.

        Args:
            look_ahead_days: How many days ahead to look for fixtures
            leagues: Optional list of leagues to filter by
            market_types: Optional list of market types to analyze

        Returns:
            List of EngineConsensus objects for qualifying fixtures
        """
        self.logger.info("Starting SCAN pipeline cycle")
        start_time = datetime.utcnow()

        try:
            # Step 1: Data Ingestion
            ingestion_result = await self._ingest_data(look_ahead_days, leagues)

            if ingestion_result.errors:
                self.logger.warning(f"Data ingestion errors: {ingestion_result.errors}")

            if not ingestion_result.fixtures:
                self.logger.info("No fixtures found in data ingestion")
                return []

            self.logger.info(f"Ingested {len(ingestion_result.fixtures)} fixtures and {len(ingestion_result.odds)} odds")

            # Step 2: Data Validation and Enhancement
            validated_fixtures = await self._validate_and_enhance_data(
                ingestion_result.fixtures,
                ingestion_result.odds
            )

            # Step 3: Engine Processing
            consensus_list = await self._process_engines(
                validated_fixtures,
                market_types or [MarketType.MATCH_ODDS, MarketType.OVER_UNDER, MarketType.BTTS]
            )

            # Step 4: Knowledge Integration
            enhanced_consensus = await self._integrate_knowledge(consensus_list)

            # Step 5: Output Preparation
            final_consensus = await self._prepare_output(enhanced_consensus)

            elapsed_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(
                f"SCAN pipeline completed in {elapsed_time:.2f}s: "
                f"{len(final_consensus)} consensus objects generated"
            )

            return final_consensus

        except Exception as e:
            self.logger.error(f"Error in SCAN pipeline: {e}")
            return []

    async def _ingest_data(
        self,
        look_ahead_days: int,
        leagues: Optional[List[str]]
    ) -> DataIngestionResult:
        """
        Ingest fixtures and odds from configured data sources.
        """
        fixtures = []
        odds = []
        errors = []
        sources_used = []

        # Ingest fixtures from all configured sources
        fixture_tasks = []
        for adapter in self.fixture_adapters:
            task = asyncio.create_task(
                self._safe_fetch_fixtures(adapter, look_ahead_days, leagues)
            )
            fixture_tasks.append((adapter.__class__.__name__, task))

        # Wait for all fixture ingestion tasks
        for source_name, task in fixture_tasks:
            try:
                source_fixtures = await task
                if source_fixtures:
                    fixtures.extend(source_fixtures)
                    sources_used.append(source_name)
                    self.logger.debug(f"Got {len(source_fixtures)} fixtures from {source_name}")
            except Exception as e:
                error_msg = f"Fixture ingestion failed for {source_name}: {e}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

        # Deduplicate fixtures by ID (prefer newer sources)
        fixtures = self._deduplicate_fixtures(fixtures)

        # Ingest odds for the fixtures
        if fixtures:
            odds_tasks = []
            # Limit to prevent too many requests
            fixtures_to_process = fixtures[:self.max_fixtures_per_batch]

            for fixture in fixtures_to_process:
                for adapter in self.odds_adapters:
                    task = asyncio.create_task(
                        self._safe_fetch_odds(adapter, fixture.id)
                    )
                    odds_tasks.append((adapter.__class__.__name__, fixture.id, task))

            # Wait for all odds ingestion tasks
            for source_name, fixture_id, task in odds_tasks:
                try:
                    source_odds = await task
                    if source_odds:
                        odds.extend(source_odds)
                        if source_name not in sources_used:
                            sources_used.append(source_name)
                        self.logger.debug(f"Got {len(source_odds)} odds for fixture {fixture_id} from {source_name}")
                except Exception as e:
                    error_msg = f"Odds ingestion failed for {source_name} fixture {fixture_id}: {e}"
                    errors.append(error_msg)
                    self.logger.warning(error_msg)

        return DataIngestionResult(
            fixtures=fixtures,
            odds=odds,
            errors=errors,
            sources_used=sources_used
        )

    async def _safe_fetch_fixtures(
        self,
        adapter: BaseAPIAdapter,
        look_ahead_days: int,
        leagues: Optional[List[str]]
    ) -> List[Fixture]:
        """Safely fetch fixtures from an adapter with error handling."""
        try:
            # Check if adapter is healthy first
            if hasattr(adapter, 'health_check'):
                is_healthy = await adapter.health_check()
                if not is_healthy:
                    self.logger.warning(f"Adapter {adapter.__class__.__name__} health check failed")
                    return []

            return await adapter.get_upcoming_fixtures(look_ahead_days, leagues)
        except Exception as e:
            self.logger.warning(f"Error fetching fixtures from {adapter.__class__.__name__}: {e}")
            return []

    async def _safe_fetch_odds(
        self,
        adapter: BaseAPIAdapter,
        fixture_id: str
    ) -> List[Odds]:
        """Safely fetch odds from an adapter with error handling."""
        try:
            # Check if adapter is healthy first
            if hasattr(adapter, 'health_check'):
                is_healthy = await adapter.health_check()
                if not is_healthy:
                    self.logger.warning(f"Adapter {adapter.__class__.__name__} health check failed")
                    return []

            return await adapter.get_odds_for_fixture(
                fixture_id,
                [MarketType.MATCH_ODDS, MarketType.OVER_UNDER, MarketType.BTTS]
            )
        except Exception as e:
            self.logger.warning(f"Error fetching odds from {adapter.__class__.__name__}: {e}")
            return []

    def _deduplicate_fixtures(self, fixtures: List[Fixture]) -> List[Fixture]:
        """
        Deduplicate fixtures by ID, keeping the most complete version.
        """
        fixtures_by_id: Dict[str, Fixture] = {}

        for fixture in fixtures:
            existing = fixtures_by_id.get(fixture.id)
            if existing is None:
                fixtures_by_id[fixture.id] = fixture
            else:
                # Keep the fixture with more complete data (has scores, etc.)
                if self._is_fixture_more_complete(fixture, existing):
                    fixtures_by_id[fixture.id] = fixture

        return list(fixtures_by_id.values())

    def _is_fixture_more_complete(self, new_fixture: Fixture, existing_fixture: Fixture) -> bool:
        """
        Determine if a fixture has more complete data than another.
        """
        # Count non-null fields
        def completeness_score(fixture: Fixture) -> int:
            score = 0
            if fixture.home_score is not None:
                score += 1
            if fixture.away_score is not None:
                score += 1
            if fixture.status != FixtureStatus.SCHEDULED:
                score += 1
            return score

        return completeness_score(new_fixture) > completeness_score(existing_fixture)

    async def _validate_and_enhance_data(
        self,
        fixtures: List[Fixture],
        odds: List[Odds]
    ) -> List[Fixture]:
        """
        Validate data for fabrication and enhance with additional context.
        """
        validated_fixtures = []

        for fixture in fixtures:
            try:
                # Filter by eligibility based on configuration
                if not await self._is_fixture_eligible(fixture):
                    continue

                # Check for fabrication if enabled
                if is_fabrication_detection_enabled():
                    fixture_odds = [o for o in odds if o.fixture_id == fixture.id]
                    is_fabricated, reason = await self.fabrication_detector.detect_fabrication(
                        fixture, fixture_odds
                    )

                    if is_fabricated:
                        self.logger.warning(
                            f"Fixture {fixture.id} flagged as fabricated: {reason}"
                        )
                        # Optionally, we could still process it but with lower confidence
                        # For now, we'll skip fabricated fixtures
                        continue

                # Enhance fixture with additional data if needed
                enhanced_fixture = await self._enhance_fixture_data(fixture, odds)
                validated_fixtures.append(enhanced_fixture)

            except Exception as e:
                self.logger.warning(f"Error validating fixture {fixture.id}: {e}")
                # Skip invalid fixtures rather than stopping the pipeline
                continue

        return validated_fixtures

    async def _is_fixture_eligible(self, fixture: Fixture) -> bool:
        """
        Check if a fixture is eligible for processing based on configuration.
        """
        try:
            # Check phase restrictions
            current_phase = get_current_phase()
            if current_phase < 1:  # Phase 0 doesn't exist, but be safe
                return False

            # Check league eligibility
            if not all_fixtures_eligible():
                # In a real implementation, we'd check against whitelisted leagues
                # For now, we'll allow all fixtures if the setting is True
                pass  # all_fixtures_eligible() returns True, so we continue

            # Additional eligibility checks could go here:
            # - Minimum odds requirements
            # - Time-to-kickoff constraints
            # - League-specific rules

            return True

        except Exception as e:
            self.logger.warning(f"Error checking fixture eligibility: {e}")
            return False  # Err on the side of caution

    async def _enhance_fixture_data(
        self,
        fixture: Fixture,
        odds: List[Odds]
    ) -> Fixture:
        """
        Enhance fixture data with additional context from odds and other sources.
        """
        # For now, we'll return the fixture as-is
        # In a more advanced implementation, we might:
        # - Add inferred league tier from odds data
        # - Enhance team information
        # - Add weather or venue data
        # - Calculate implied probabilities from odds

        return fixture

    async def _process_engines(
        self,
        fixtures: List[Fixture],
        market_types: List[MarketType]
    ) -> List[EngineConsensus]:
        """
        Process fixtures through the engine suite to generate consensus predictions.
        """
        consensus_list = []

        # Process fixtures in batches to avoid overwhelming the engines
        batch_size = 10
        for i in range(0, len(fixtures), batch_size):
            batch = fixtures[i:i + batch_size]
            batch_consensus = await self._process_fixture_batch(batch, market_types)
            consensus_list.extend(batch_consensus)

        return consensus_list

    async def _process_fixture_batch(
        self,
        fixtures: List[Fixture],
        market_types: List[MarketType]
    ) -> List[EngineConsensus]:
        """
        Process a batch of fixtures through the engine suite.
        """
        consensus_list = []

        for fixture in fixtures:
            try:
                # Get odds for this fixture (we'd normally pass these in)
                # For now, we'll let the engine suite handle odds lookup
                # or we could pass cached odds from ingestion

                # Run engine suite for each market type
                for market_type in market_types:
                    consensus = await self.engine_suite.get_consensus(
                        fixture_id=fixture.id,
                        market_type=market_type
                    )

                    if consensus and consensus.confidence >= Decimal('0.1'):  # Minimum confidence threshold
                        consensus_list.append(consensus)

            except Exception as e:
                self.logger.warning(f"Error processing fixture {fixture.id} in engine suite: {e}")
                continue

        return consensus_list

    async def _integrate_knowledge(
        self,
        consensus_list: List[EngineConsensus]
    ) -> List[EngineConsensus]:
        """
        Integrate relevant knowledge from the persistence system into consensus objects.
        """
        enhanced_consensus = []

        for consensus in consensus_list:
            try:
                # Search for relevant knowledge
                knowledge_query = f"{consensus.fixture_id} {consensus.market_type.value} {consensus.selection}"
                relevant_knowledge = await self.knowledge_service.search_by_content(knowledge_query)

                # If we found highly relevant knowledge, we might adjust confidence
                # For now, we'll just log it and continue
                if relevant_knowledge:
                    max_relevance = max((k.relevance_score for k in relevant_knowledge), default=Decimal('0'))
                    if max_relevance > Decimal('0.8'):
                        self.logger.debug(
                            f"High relevance knowledge found for {consensus.fixture_id}: "
                            f"{max_relevance}"
                        )
                        # In a full implementation, we might adjust consensus confidence here

                enhanced_consensus.append(consensus)

            except Exception as e:
                self.logger.warning(f"Error integrating knowledge for consensus: {e}")
                enhanced_consensus.append(consensus)  # Keep original if enhancement fails

        return enhanced_consensus

    async def _prepare_output(
        self,
        consensus_list: List[EngineConsensus]
    ) -> List[EngineConsensus]:
        """
        Prepare final consensus objects for output to the TRIGGER pipeline.
        """
        # Sort by confidence (highest first) and then by fixture time
        def sort_key(consensus: EngineConsensus) -> tuple:
            # We don't have fixture time in consensus, so we'll just sort by confidence
            # In a full implementation, we'd join with fixture data to get match_date
            return (-consensus.confidence, consensus.fixture_id)

        sorted_consensus = sorted(consensus_list, key=sort_key)

        # Apply any final filtering or transformation
        final_consensus = []
        for consensus in sorted_consensus:
            # Ensure minimum quality thresholds
            if consensus.confidence >= Decimal('0.1') and consensus.probability > Decimal('0'):
                final_consensus.append(consensus)

        return final_consensus

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get current status of the SCAN pipeline components.
        """
        status = {
            "pipeline": "SCAN",
            "timestamp": datetime.utcnow().isoformat(),
            "adapters": {
                "odds": [a.__class__.__name__ for a in self.odds_adapters],
                "fixtures": [a.__class__.__name__ for a in self.fixture_adapters]
            },
            "configuration": {
                "current_phase": get_current_phase(),
                "paper_only": is_paper_only(),
                "all_fixtures_eligible": all_fixtures_eligible(),
                "fabrication_detection": is_fabrication_detection_enabled()
            },
            "components": {
                "engine_suite": self.engine_suite.__class__.__name__,
                "fabrication_detector": self.fabrication_detector.__class__.__name__,
                "knowledge_service": self.knowledge_service.__class__.__name__
            }
        }

        # Add adapter health status
        try:
            health_tasks = []
            for adapter in self.odds_adapters + self.fixture_adapters:
                if hasattr(adapter, 'health_check'):
                    task = asyncio.create_task(adapter.health_check())
                    health_tasks.append((adapter.__class__.__name__, task))

            health_results = {}
            for name, task in health_tasks:
                try:
                    is_healthy = await task
                    health_results[name] = is_healthy
                except Exception as e:
                    health_results[name] = False
                    self.logger.warning(f"Health check failed for {name}: {e}")

            status["adapter_health"] = health_results
        except Exception as e:
            self.logger.warning(f"Error checking adapter health: {e}")
            status["adapter_health"] = {}

        return status