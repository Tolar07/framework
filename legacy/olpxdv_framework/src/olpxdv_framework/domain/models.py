"""
Core domain models for the OLP XDV-inspired framework.
These are pure Python classes with no framework dependencies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class MarketType(Enum):
    """Types of betting markets"""
    MATCH_ODDS = "match_odds"  # 1X2
    OVER_UNDER = "over_under"  # O/U
    BTTS = "btts"              # Both Teams To Score
    DOUBLE_CHANCE = "double_chance"  # DC
    ASIAN_HANDICAP = "asian_handicap"
    CORRECT_SCORE = "correct_score"


class LeagueTier(Enum):
    """League tiers for classification"""
    TIER_A = "tier_a"   # Top leagues (EPL, La Liga, etc.)
    TIER_B = "tier_b"   # Second tier leagues
    TIER_C = "tier_c"   # Lower leagues


class FixtureStatus(Enum):
    """Status of a football fixture"""
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class BetResult(Enum):
    """Result of a bet"""
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"  # Void/refund
    PENDING = "pending"


class BetType(Enum):
    """Types of bets"""
    SINGLE = "single"
    ACCUMULATOR = "accumulator"
    SYSTEM = "system"


@dataclass(frozen=True)
class Team:
    """Immutable team entity"""
    id: str
    name: str
    short_name: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Team ID cannot be empty")
        if not self.name:
            raise ValueError("Team name cannot be empty")


@dataclass(frozen=True)
class Fixture:
    """Immutable football fixture"""
    id: str
    home_team: Team
    away_team: Team
    league: str
    league_tier: LeagueTier
    match_date: datetime
    status: FixtureStatus = FixtureStatus.SCHEDULED
    home_score: Optional[int] = None
    away_score: Optional[int] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Fixture ID cannot be empty")
        if self.home_team.id == self.away_team.id:
            raise ValueError("Home and away teams must be different")
        if self.match_date is None:
            raise ValueError("Match date cannot be None")


@dataclass(frozen=True)
class Odds:
    """Immutable betting odds"""
    id: str
    fixture_id: str
    market_type: MarketType
    selection: str  # e.g., "Home", "Draw", "Away", "Over 2.5", "Yes"
    decimal_odds: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)
    bookmaker: str = "unknown"

    def __post_init__(self):
        if not self.id:
            raise ValueError("Odds ID cannot be empty")
        if not self.fixture_id:
            raise ValueError("Fixture ID cannot be empty")
        if self.decimal_odds <= Decimal('1.0'):
            raise ValueError("Decimal odds must be greater than 1.0")
        if self.timestamp is None:
            raise ValueError("Timestamp cannot be None")


@dataclass
class CLVLeg:
    """Closing Line Value leg - tracks a bet's performance vs closing line"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    fixture_id: str = ""
    market_type: MarketType = MarketType.MATCH_ODDS
    selection: str = ""
    opening_odds: Decimal = Decimal('0.0')
    closing_odds: Decimal = Decimal('0.0')
    stake: Decimal = Decimal('1.0')  # Unit stake for paper trading
    potential_return: Decimal = field(init=False)
    clv_value: Decimal = field(init=False)
    clv_percentage: Decimal = field(init=False)
    placed_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    result: BetResult = BetResult.PENDING
    is_valid: bool = True

    def __post_init__(self):
        if not self.fixture_id:
            raise ValueError("Fixture ID cannot be empty")
        if self.opening_odds <= Decimal('0'):
            raise ValueError("Opening odds must be positive")
        if self.closing_odds < Decimal('0'):
            raise ValueError("Closing odds cannot be negative")
        if self.stake <= Decimal('0'):
            raise ValueError("Stake must be positive")

        # Calculate derived values
        self.potential_return = self.stake * self.opening_odds
        if self.closing_odds > Decimal('0'):
            self.clv_value = (self.closing_odds - self.opening_odds) * self.stake
            if self.opening_odds > Decimal('0'):
                self.clv_percentage = (self.clv_value / (self.stake * self.opening_odds)) * Decimal('100')

    def close_leg(self, closing_odds: Decimal, result: BetResult) -> None:
        """Close the leg with actual closing odds and result"""
        if closing_odds <= Decimal('0'):
            raise ValueError("Closing odds must be positive when closing leg")

        object.__setattr__(self, 'closing_odds', closing_odds)
        object.__setattr__(self, 'closed_at', datetime.utcnow())
        object.__setattr__(self, 'result', result)

        # Recalculate CLV values
        self.clv_value = (closing_odds - self.opening_odds) * self.stake
        if self.opening_odds > Decimal('0'):
            self.clv_percentage = (self.clv_value / (self.stake * self.opening_odds)) * Decimal('100')

    def is_profitable(self) -> bool:
        """Check if the leg was profitable (positive CLV)"""
        return self.clv_value > Decimal('0')

    def is_won(self) -> bool:
        """Check if the bet won"""
        return self.result == BetResult.WIN


@dataclass
class CLVMetrics:
    """Aggregate CLV metrics for performance tracking"""
    total_legs: int = 0
    valid_legs: int = 0
    winning_legs: int = 0
    total_stake: Decimal = Decimal('0')
    total_return: Decimal = Decimal('0')
    total_clv: Decimal = Decimal('0')
    mean_clv: Decimal = Decimal('0')
    clv_percentage: Decimal = Decimal('0')
    yield_percentage: Decimal = Decimal('0')
    hit_rate: Decimal = Decimal('0')

    def calculate_from_legs(self, legs: List[CLVLeg]) -> None:
        """Calculate metrics from a list of CLV legs"""
        valid_legs = [leg for leg in legs if leg.is_valid and leg.closed_at is not None]

        self.total_legs = len(legs)
        self.valid_legs = len(valid_legs)
        self.winning_legs = sum(1 for leg in valid_legs if leg.is_won())
        self.total_stake = sum(leg.stake for leg in valid_legs)
        self.total_return = sum(leg.stake * leg.opening_odds for leg in valid_legs if leg.is_won())
        self.total_clv = sum(leg.clv_value for leg in valid_legs)

        if self.valid_legs > 0:
            self.mean_clv = self.total_clv / Decimal(str(self.valid_legs))
            self.clv_percentage = (self.total_clv / (self.total_stake * Decimal('100'))) * Decimal('100') if self.total_stake > 0 else Decimal('0')
            self.yield_percentage = ((self.total_return - self.total_stake) / self.total_stake * Decimal('100')) if self.total_stake > 0 else Decimal('0')
            self.hit_rate = (Decimal(str(self.winning_legs)) / Decimal(str(self.valid_legs)) * Decimal('100')) if self.valid_legs > 0 else Decimal('0')


@dataclass(frozen=True)
class KnowledgeItem:
    """Immutable knowledge item for the knowledge persistence system"""
    id: str
    title: str
    content: str
    knowledge_type: str  # fact, decision, process, observation, question
    source: str  # documentation, conversation, agent_output, external
    tags: List[str] = field(default_factory=list)
    related_ids: List[str] = field(default_factory=list)
    relevance_score: Decimal = field(default=Decimal('1.0'))
    confidence: Decimal = field(default=Decimal('0.95'))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Knowledge item ID cannot be empty")
        if not self.title:
            raise ValueError("Knowledge item title cannot be empty")
        if not self.content:
            raise ValueError("Knowledge item content cannot be empty")
        if self.relevance_score < Decimal('0') or self.relevance_score > Decimal('1'):
            raise ValueError("Relevance score must be between 0 and 1")
        if self.confidence < Decimal('0') or self.confidence > Decimal('1'):
            raise ValueError("Confidence must be between 0 and 1")


@dataclass
class EngineConsensus:
    """Result from the engine consensus process"""
    fixture_id: str
    market_type: MarketType
    selection: str
    probability: Decimal  # 0-1
    confidence: Decimal   # 0-1
    expected_value: Decimal
    kelly_fraction: Decimal
    engines_used: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.fixture_id:
            raise ValueError("Fixture ID cannot be empty")
        if self.probability < Decimal('0') or self.probability > Decimal('1'):
            raise ValueError("Probability must be between 0 and 1")
        if self.confidence < Decimal('0') or self.confidence > Decimal('1'):
            raise ValueError("Confidence must be between 0 and 1")


# Repository interfaces (to be implemented in infrastructure layer)
class FixtureRepository:
    """Abstract repository for fixtures"""
    async def get_by_id(self, fixture_id: str) -> Optional[Fixture]:
        raise NotImplementedError

    async def get_upcoming(self, league: Optional[str] = None,
                          limit: int = 50) -> List[Fixture]:
        raise NotImplementedError

    async def save(self, fixture: Fixture) -> Fixture:
        raise NotImplementedError


class OddsRepository:
    """Abstract repository for odds"""
    async def get_by_fixture_and_market(self, fixture_id: str,
                                      market_type: MarketType) -> List[Odds]:
        raise NotImplementedError

    async def save(self, odds: Odds) -> Odds:
        raise NotImplementedError

    async def get_latest(self, fixture_id: str,
                        market_type: MarketType) -> Optional[Odds]:
        raise NotImplementedError


class CLVLegRepository:
    """Abstract repository for CLV legs"""
    async def get_by_id(self, leg_id: str) -> Optional[CLVLeg]:
        raise NotImplementedError

    async def get_open_legs(self) -> List[CLVLeg]:
        raise NotImplementedError

    async def get_closed_legs(self, limit: int = 1000) -> List[CLVLeg]:
        raise NotImplementedError

    async def save(self, leg: CLVLeg) -> CLVLeg:
        raise NotImplementedError

    async def update(self, leg: CLVLeg) -> CLVLeg:
        raise NotImplementedError


class KnowledgeRepository:
    """Abstract repository for knowledge items"""
    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        raise NotImplementedError

    async def search_by_tags(self, tags: List[str]) -> List[KnowledgeItem]:
        raise NotImplementedError

    async def search_by_content(self, query: str) -> List[KnowledgeItem]:
        raise NotImplementedError

    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        raise NotImplementedError

    async def update_relevance(self, item_id: str,
                             new_score: Decimal) -> KnowledgeItem:
        raise NotImplementedError

    async def get_related_knowledge(self, item_id: str, max_depth: int = 2) -> List[KnowledgeItem]:
        """Get knowledge items related to a given item through tags and references."""
        try:
            # Get the source item
            source_item = await self.knowledge_repo.get_by_id(item_id)
            if not source_item:
                return []

            # Start with direct references
            related_ids = set(source_item.related_ids)

            # Add items with matching tags
            if source_item.tags:
                tag_matches = await self.knowledge_repo.search_by_tags(source_item.tags)
                related_ids.update(item.id for item in tag_matches)

            # Remove the source item itself
            related_ids.discard(item_id)

            # Limit depth to prevent infinite recursion
            if max_depth <= 0:
                related_ids = set()

            # Fetch all related items
            related_items = []
            for rid in related_ids:
                item = await self.knowledge_repo.get_by_id(rid)
                if item:
                    related_items.append(item)

            # Sort by relevance score
            related_items.sort(key=lambda x: x.relevance_score, reverse=True)
            return related_items

        except Exception as e:
            self.logger.error(f"Error getting related knowledge for {item_id}: {e}")
            return []


class QualifiedOpportunity:
    """Represents a qualified betting opportunity based on engine consensus."""
    
    def __init__(
        self,
        consensus: EngineConsensus,
        value_betting_score: Decimal,
        kelly_stake: Decimal,
        risk_adjusted_stake: Decimal,
        max_stake: Decimal,
        confidence_tier: str,
        reasoning: str,
        timestamp: datetime
    ):
        self.consensus = consensus
        self.value_betting_score = value_betting_score
        self.kelly_stake = kelly_stake
        self.risk_adjusted_stake = risk_adjusted_stake
        self.max_stake = max_stake
        self.confidence_tier = confidence_tier
        self.reasoning = reasoning
        self.timestamp = timestamp


@dataclass(frozen=True)
class BettingRecommendation:
    """Final betting recommendation generated by the PUBLISH pipeline."""
    
    opportunity: QualifiedOpportunity
    recommended_stake: Decimal
    bet_type: BetType
    expected_return: Decimal
    potential_profit: Decimal
    betting_code: str
    expiry_time: datetime
    timestamp: datetime