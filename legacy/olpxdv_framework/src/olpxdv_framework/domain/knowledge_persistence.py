"""
Knowledge Persistence System

This module implements the knowledge persistence system from OLP XDV:
- Structured knowledge items with relevance decay
- Tag-based and content-based search
- Relevance scoring and confidence tracking
- Expiration and cleanup mechanisms
"""

from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta
import hashlib
from dataclasses import dataclass, field

from olpxdv_framework.domain.models import KnowledgeItem, KnowledgeRepository
from olpxdv_framework.domain.protected_constants import (
    get_knowledge_relevance_half_life_days,
    get_vault_memory_sync_interval_minutes
)

logger = logging.getLogger(__name__)


class InMemoryKnowledgeRepository(KnowledgeRepository):
    """
    In-memory implementation of the knowledge repository.
    For production, this would be replaced with a persistent storage
    solution (SQLite, PostgreSQL, etc.).
    """

    def __init__(self):
        self._knowledge_items: Dict[str, KnowledgeItem] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a knowledge item by its ID."""
        return self._knowledge_items.get(item_id)

    async def search_by_tags(self, tags: List[str]) -> List[KnowledgeItem]:
        """
        Search for knowledge items by tags.
        Returns items that have ALL the specified tags.
        """
        if not tags:
            return list(self._knowledge_items.values())

        results = []
        for item in self._knowledge_items.values():
            if all(tag in item.tags for tag in tags):
                results.append(item)

        # Sort by relevance score (descending)
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def search_by_content(self, query: str) -> List[KnowledgeItem]:
        """
        Search for knowledge items by content.
        Simple text search - in production would use full-text search.
        """
        if not query or not query.strip():
            return list(self._knowledge_items.values())

        query_lower = query.lower().strip()
        results = []

        for item in self._knowledge_items.values():
            # Search in title and content
            if (query_lower in item.title.lower() or
                query_lower in item.content.lower()):
                results.append(item)

        # Sort by relevance score (descending)
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def save(self, item: KnowledgeItem) -> KnowledgeItem:
        """Save a knowledge item."""
        # Create a new instance with updated timestamp
        updated_item = KnowledgeItem(
            id=item.id,
            title=item.title,
            content=item.content,
            knowledge_type=item.knowledge_type,
            source=item.source,
            tags=item.tags,
            related_ids=item.related_ids,
            relevance_score=item.relevance_score,
            confidence=item.confidence,
            created_at=item.created_at,
            updated_at=datetime.utcnow(),  # New timestamp
            expires_at=item.expires_at,
        )
        
        # Store the new item
        self._knowledge_items[item.id] = updated_item
        self._logger.debug(f"Saved knowledge item: {item.id}")
        return updated_item

    async def update_relevance(self, item_id: str,
                             new_score: Decimal) -> KnowledgeItem:
        """Update the relevance score of a knowledge item."""
        item = self._knowledge_items.get(item_id)
        if not item:
            raise ValueError(f"Knowledge item {item_id} not found")

        # Validate relevance score
        if new_score < Decimal('0') or new_score > Decimal('1'):
            raise ValueError("Relevance score must be between 0 and 1")

        item.relevance_score = new_score
        item.updated_at = datetime.utcnow()

        self._logger.debug(f"Updated relevance for {item_id} to {new_score}")
        return item

    async def delete_expired(self) -> int:
        """
        Delete expired knowledge items.
        Returns the number of items deleted.
        """
        now = datetime.utcnow()
        expired_items = [
            item_id for item_id, item in self._knowledge_items.items()
            if item.expires_at and item.expires_at < now
        ]

        for item_id in expired_items:
            del self._knowledge_items[item_id]
            self._logger.debug(f"Deleted expired knowledge item: {item_id}")

        return len(expired_items)

    async def apply_relevance_decay(self) -> int:
        """
        Apply relevance decay to all knowledge items based on half-life.
        Returns the number of items updated.
        """
        half_life_days = get_knowledge_relevance_half_life_days()
        if half_life_days <= 0:
            return 0

        decay_factor = Decimal('0.5') ** (Decimal('1') / Decimal(str(half_life_days)))
        now = datetime.utcnow()
        updated_count = 0

        for item in self._knowledge_items.values():
            # Calculate age in days
            age_days = Decimal(str((now - item.created_at).total_seconds() / 86400))

            # Apply decay: relevance = initial_relevance * (0.5)^(age/half_life)
            # We'll assume initial relevance was 1.0 for decay calculation
            decayed_relevance = decay_factor ** age_days

            # Apply decay but don't go below a minimum threshold
            new_relevance = max(item.relevance_score * decayed_relevance, Decimal('0.01'))

            if new_relevance != item.relevance_score:
                item.relevance_score = new_relevance
                item.updated_at = now
                updated_count += 1

        if updated_count > 0:
            self._logger.debug(f"Applied relevance decay to {updated_count} items")

        return updated_count

    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        now = datetime.utcnow()
        total_items = len(self._knowledge_items)

        expired_items = sum(
            1 for item in self._knowledge_items.values()
            if item.expires_at and item.expires_at < now
        )

        # Calculate average relevance
        avg_relevance = Decimal('0')
        if total_items > 0:
            avg_relevance = sum(item.relevance_score for item in self._knowledge_items.values()) / total_items

        # Count by knowledge type
        type_counts: Dict[str, int] = {}
        for item in self._knowledge_items.values():
            type_counts[item.knowledge_type] = type_counts.get(item.knowledge_type, 0) + 1

        return {
            "total_items": total_items,
            "expired_items": expired_items,
            "active_items": total_items - expired_items,
            "average_relevance": float(avg_relevance),
            "knowledge_type_counts": type_counts,
            "half_life_days": half_life_days
        }

    def _calculate_expiration_date(self, created_at: datetime) -> Optional[datetime]:
        """
        Calculate expiration date based on half-life.
        Items expire when relevance falls below a threshold.
        """
        half_life_days = get_knowledge_relevance_half_life_days()
        if half_life_days <= 0:
            return None  # No expiration

        # Expire when relevance falls below 0.01 (1% of original)
        # Using formula: final = initial * (0.5)^(time/half_life)
        # Solving for time when final/initial = 0.01
        # time = half_life * log2(1/0.01) = half_life * log2(100)
        import math
        half_lives_to_expire = math.log2(100)  # ~6.64 half-lives to reach 1% relevance
        expire_days = half_life_days * half_lives_to_expire

        return created_at + timedelta(days=expire_days)


class KnowledgePersistenceService:
    """
    Service layer for knowledge persistence operations.
    Provides higher-level operations for managing knowledge.
    """

    def __init__(self, knowledge_repo: Optional[KnowledgeRepository] = None):
        if knowledge_repo is not None:
            self.knowledge_repo = knowledge_repo
        else:
            self.knowledge_repo = InMemoryKnowledgeRepository()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def add_knowledge(
        self,
        title: str,
        content: str,
        knowledge_type: str,
        source: str,
        tags: Optional[List[str]] = None,
        related_ids: Optional[List[str]] = None,
        relevance_score: Decimal = Decimal('1.0'),
        confidence: Decimal = Decimal('0.95')
    ) -> KnowledgeItem:
        """
        Add a new knowledge item to the repository.
        """
        # Generate unique ID based on content hash
        content_hash = hashlib.sha256(
            f"{title}{content}{knowledge_type}{source}".encode()
        ).hexdigest()[:16]

        item_id = f"{knowledge_type}_{content_hash}"

        # Check if item already exists (update instead of create)
        existing_item = await self.knowledge_repo.get_by_id(item_id)
        if existing_item:
            # Update existing item
            existing_item.title = title
            existing_item.content = content
            existing_item.knowledge_type = knowledge_type
            existing_item.source = source
            existing_item.tags = tags or []
            existing_item.related_ids = related_ids or []
            existing_item.relevance_score = relevance_score
            existing_item.confidence = confidence
            existing_item.updated_at = datetime.utcnow()

            # Recalculate expiration
            existing_item.expires_at = self.knowledge_repo._calculate_expiration_date(existing_item.created_at)

            await self.knowledge_repo.save(existing_item)
            self.logger.info(f"Updated knowledge item: {item_id}")
            return existing_item

        # Create new item
        item = KnowledgeItem(
            id=item_id,
            title=title,
            content=content,
            knowledge_type=knowledge_type,
            source=source,
            tags=tags or [],
            related_ids=related_ids or [],
            relevance_score=relevance_score,
            confidence=confidence,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=self.knowledge_repo._calculate_expiration_date(datetime.utcnow())
        )

        await self.knowledge_repo.save(item)
        self.logger.info(f"Added knowledge item: {item_id}")
        return item

    async def get_related_knowledge(
        self,
        item_id: str,
        max_depth: int = 2
    ) -> List[KnowledgeItem]:
        """
        Get knowledge items related to a given item through tags and references.
        """
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
            self.logger.error(f"Error getting related knowledge: {e}")
            return []

    async def search_knowledge(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        knowledge_type: Optional[str] = None,
        source: Optional[str] = None,
        min_relevance: Decimal = Decimal('0.0'),
        limit: int = 50
    ) -> List[KnowledgeItem]:
        """
        Search knowledge items with multiple filters.
        """
        try:
            # Start with content search if query provided
            if query and query.strip():
                candidates = await self.knowledge_repo.search_by_content(query)
            else:
                candidates = list(await self.knowledge_repo.get_all_items())  # Need to add this method

            # Filter by tags
            if tags:
                candidates = [
                    item for item in candidates
                    if all(tag in item.tags for tag in tags)
                ]

            # Filter by knowledge type
            if knowledge_type:
                candidates = [
                    item for item in candidates
                    if item.knowledge_type == knowledge_type
                ]

            # Filter by source
            if source:
                candidates = [
                    item for item in candidates
                    if item.source == source
                ]

            # Filter by minimum relevance
            if min_relevance > Decimal('0'):
                candidates = [
                    item for item in candidates
                    if item.relevance_score >= min_relevance
                ]

            # Sort by relevance and apply limit
            candidates.sort(key=lambda x: x.relevance_score, reverse=True)
            return candidates[:limit]

        except Exception as e:
            self.logger.error(f"Error searching knowledge: {e}")
            return []

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Clean up expired knowledge items and apply relevance decay.
        Returns statistics about the cleanup operation.
        """
        try:
            deleted_count = await self.knowledge_repo.delete_expired()
            decay_count = await self.knowledge_repo.apply_relevance_decay()

            stats = await self.knowledge_repo.get_stats()

            self.logger.info(
                f"Knowledge cleanup: {deleted_count} expired items deleted, "
                f"{decay_count} items updated with relevance decay"
            )

            return {
                "deleted_expired": deleted_count,
                "relevance_decay_applied": decay_count,
                "remaining_items": stats["active_items"]
            }

        except Exception as e:
            self.logger.error(f"Error during knowledge cleanup: {e}")
            return {
                "deleted_expired": 0,
                "relevance_decay_applied": 0,
                "remaining_items": 0,
                "error": str(e)
            }


# KnowledgeRepository extension method - we need to add get_all_items
# Since we can't modify the abstract class easily, we'll handle it in the service
# For the in-memory implementation, we can access the internal dict

def patch_inmemory_repository():
    """Patch the InMemoryKnowledgeRepository to add get_all_items method."""
    original_class = InMemoryKnowledgeRepository

    async def get_all_items(self) -> List[KnowledgeItem]:
        """Get all knowledge items in the repository."""
        return list(self._knowledge_items.values())

    # Add the method to the class
    original_class.get_all_items = get_all_items

    return original_class

# Apply the patch
patch_inmemory_repository()


# Factory function
def create_knowledge_persistence_service(
    knowledge_repo: Optional[KnowledgeRepository] = None
) -> KnowledgePersistenceService:
    """
    Factory function to create a KnowledgePersistenceService.
    If no repository is provided, creates an in-memory repository.
    """
    if knowledge_repo is None:
        knowledge_repo = InMemoryKnowledgeRepository()

    return KnowledgePersistenceService(knowledge_repo)