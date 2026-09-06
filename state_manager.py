"""
StateManager — Unified storage facade for OLP XDV
Provides consistent access to Brain (SQLite), file caches, and vault-memory
with atomic operations and cache validation.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from brain.store import Brain
from booking.sportybet_fixtures import CachedFixture, _read_cache, _write_cache


@dataclass
class CacheEntry:
    """Represents a cached item with metadata for validation."""
    data: Any
    timestamp: float
    ttl_seconds: int
    source: str  # 'brain', 'cache', 'vault', 'external'

    @property
    def is_fresh(self) -> bool:
        """Check if cache entry is still valid."""
        return (time.time() - self.timestamp) < self.ttl_seconds


class StateManager:
    """
    Unified storage layer that abstracts Brain (SQLite), file caches, and external sources.

    Provides:
    - Cache validation with TTL
    - Write-through to multiple stores when appropriate
    - Fallback chains (Brain → Cache → External)
    - Atomic operations where possible
    """

    def __init__(self, brain_path: Optional[Path] = None, cache_root: Optional[Path] = None):
        self.brain = Brain(brain_path) if brain_path else Brain()
        self.cache_root = cache_root or (Path(__file__).parent / "data" / "cache")
        self.cache_root.mkdir(parents=True, exist_ok=True)

        # Default TTL values (seconds)
        self.ttl_config = {
            'sportybet_fixtures': 6 * 3600,  # 6 hours
            'football_data': 24 * 3600,      # 24 hours
            'model_state': 1 * 3600,         # 1 hour
            'predictions': 0,                # Never expire (immutable)
            'clv_log': 0,                    # Never expire (append-only)
        }

    async def get_fixture(self, league: str, fixture_id: str) -> Optional[CachedFixture]:
        """
        Get fixture with fallback chain: Brain → Cache → External.
        Returns None if not found in any store.
        """
        # 1. Try Brain (processed, validated data)
        brain_fixture = await self._brain_get_fixture(league, fixture_id)
        if brain_fixture and brain_fixture.is_fresh:
            return brain_fixture

        # 2. Try file cache (raw scraped data)
        cache_fixture = await self._cache_get_fixture(league, fixture_id)
        if cache_fixture and cache_fixture.is_fresh:
            return cache_fixture

        # 3. Fetch fresh from external source
        fresh_fixture = await self._fetch_fresh_fixture(league, fixture_id)
        if fresh_fixture:
            # Write-through to all stores for future access
            await self._brain_save_fixture(fresh_fixture)
            await self._cache_save_fixture(fresh_fixture)

        return fresh_fixture

    async def save_fixture(self, fixture: CachedFixture, source: str = "external") -> None:
        """Save fixture to appropriate stores based on source."""
        if source == "external":
            # Write-through to both Brain and cache
            await self._brain_save_fixture(fixture)
            await self._cache_save_fixture(fixture)
        elif source == "brain":
            # Only update cache (Brain is source of truth)
            await self._cache_save_fixture(fixture)
        elif source == "cache":
            # Only update Brain (cache is source of truth for raw data)
            await self._brain_save_fixture(fixture)

    async def get_model_state(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get model state with caching."""
        # Brain is source of truth for model state
        return self.brain.load_model_state(model_key)

    async def save_model_state(self, model_key: str, kind: str, version: int,
                              content_hash: str, n_matches: int,
                              last_date: Optional[str], first_date: Optional[str],
                              payload: dict) -> None:
        """Save model state to Brain."""
        self.brain.save_model_state(
            model_key, kind, version, content_hash, n_matches,
            last_date, first_date, payload
        )

    async def log_clv_leg(self, leg_data: Dict[str, Any]) -> str:
        """Log a CLV leg to the canonical ledger."""
        from clv.clv_logger import CLVLog
        log = CLVLog()
        leg = log.log_entry(**leg_data)
        return leg.leg_id

    # Private implementation methods

    async def _brain_get_fixture(self, league: str, fixture_id: str) -> Optional[CachedFixture]:
        """Get fixture from Brain (if we stored processed fixtures there)."""
        # Currently Brain doesn't store raw fixtures, but we could extend it
        # For now, return None to fall back to cache
        return None

    async def _brain_save_fixture(self, fixture: CachedFixture) -> None:
        """Save fixture to Brain (if we decide to store processed fixtures there)."""
        # Placeholder for future implementation
        pass

    async def _cache_get_fixture(self, league: str, fixture_id: str) -> Optional[CachedFixture]:
        """Get fixture from file cache."""
        cache_file = self._get_cache_path(league, "sportybet_fixtures")
        if not cache_file.exists():
            return None

        try:
            data = _read_cache(str(cache_file))
            # Find specific fixture in the cached data
            for fixture_data in data:
                if fixture_data.get('id') == fixture_id:
                    return CachedFixture(**fixture_data)
        except Exception:
            pass

        return None

    async def _cache_save_fixture(self, fixture: CachedFixture) -> None:
        """Save fixture to file cache."""
        cache_file = self._get_cache_path(fixture.league, "sportybet_fixtures")

        # Read existing cache
        existing_data = []
        if cache_file.exists():
            try:
                existing_data = _read_cache(str(cache_file))
            except Exception:
                existing_data = []

        # Update or add fixture
        fixture_dict = asdict(fixture)
        updated = False
        for i, existing in enumerate(existing_data):
            if existing.get('id') == fixture.fixture_id:
                existing_data[i] = fixture_dict
                updated = True
                break

        if not updated:
            existing_data.append(fixture_dict)

        # Write back atomically
        _write_cache(str(cache_file), existing_data)

    async def _fetch_fresh_fixture(self, league: str, fixture_id: str) -> Optional[CachedFixture]:
        """Fetch fresh fixture from external source (SportyBet via Playwright)."""
        from booking.sportybet_fixtures import _scrape_one_league

        try:
            # This is a simplified version - in practice we'd need to scrape
            # the specific league and find the fixture
            fixtures = await _scrape_one_league(league, headless=True)
            for fixture in fixtures:
                if fixture.fixture_id == fixture_id:
                    return fixture
        except Exception:
            pass

        return None

    def _get_cache_path(self, league: str, cache_type: str) -> Path:
        """Get cache file path for a league and cache type."""
        safe_league = "".join(c for c in league if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return self.cache_root / f"{safe_league}_{cache_type}.json"

    def close(self) -> None:
        """Close underlying connections."""
        self.brain.close()


# Global instance for easy access
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get or create the global StateManager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


async def initialize_state_manager(brain_path: Optional[Path] = None,
                                  cache_root: Optional[Path] = None) -> StateManager:
    """Initialize the global StateManager with custom paths."""
    global _state_manager
    _state_manager = StateManager(brain_path, cache_root)
    return _state_manager