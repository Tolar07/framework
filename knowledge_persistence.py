"""
Enhanced Knowledge Persistence Layer for OLP XDV
Provides structured knowledge storage, automatic summarization,
and intelligent querying capabilities built on top of the existing
vault-memory sync system.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
import yaml

from brain.store import Brain


@dataclass
class KnowledgeItem:
    """Represents a single piece of knowledge with rich metadata."""
    id: str
    title: str
    content: str
    knowledge_type: str  # 'fact', 'decision', 'process', 'observation', 'question'
    source: str  # 'conversation', 'document', 'agent_output', 'external'
    tags: Set[str] = field(default_factory=set)
    related_ids: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    relevance_score: float = 1.0  # Decays over time unless reinforced
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    confidence: float = 1.0  # How confident we are in this knowledge
    expires_at: Optional[datetime] = None  # For time-sensitive knowledge
    vault_path: Optional[Path] = None  # Where it's stored in the vault
    memory_path: Optional[Path] = None  # Where it's mirrored in memory

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'knowledge_type': self.knowledge_type,
            'source': self.source,
            'tags': list(self.tags),
            'related_ids': list(self.related_ids),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'relevance_score': self.relevance_score,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'confidence': self.confidence,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'vault_path': str(self.vault_path) if self.vault_path else None,
            'memory_path': str(self.memory_path) if self.memory_path else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeItem':
        """Create from dictionary."""
        # Convert sets from lists
        data['tags'] = set(data.get('tags', []))
        data['related_ids'] = set(data.get('related_ids', []))

        # Convert datetime strings
        for field in ['created_at', 'updated_at', 'last_accessed', 'expires_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])

        # Convert paths
        for field in ['vault_path', 'memory_path']:
            if data.get(field):
                data[field] = Path(data[field])

        return cls(**data)


@dataclass
class ConversationSummary:
    """Summary of a conversation session."""
    session_id: str
    start_time: datetime
    end_time: datetime
    summary: str
    key_decisions: List[str]
    action_items: List[str]
    topics_discussed: Set[str]
    knowledge_items: List[str]  # IDs of knowledge items extracted
    participants: Set[str]  # Who was involved (human/agent names)
    files_modified: Set[str]
    relevance_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'summary': self.summary,
            'key_decisions': self.key_decisions,
            'action_items': self.action_items,
            'topics_discussed': list(self.topics_discussed),
            'knowledge_items': self.knowledge_items,
            'participants': list(self.participants),
            'files_modified': list(self.files_modified),
            'relevance_score': self.relevance_score
        }


class KnowledgePersistence:
    """
    Enhanced knowledge persistence system that builds on top of
    the existing vault-memory sync to provide structured knowledge
    management capabilities.
    """

    def __init__(self, vault_root: Path, memory_root: Path, brain: Optional[Brain] = None):
        self.vault_root = vault_root
        self.memory_root = memory_root
        self.brain = brain or Brain()

        # Knowledge storage locations
        self.knowledge_vault_dir = vault_root / "knowledge"
        self.knowledge_memory_dir = memory_root / "knowledge"
        self.conversations_vault_dir = vault_root / "conversations"
        self.conversations_memory_dir = memory_root / "conversations"

        # Database for structured knowledge queries
        self.db_path = self.knowledge_memory_dir / "knowledge.db"

        # Ensure directories exist
        self.knowledge_vault_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_memory_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_vault_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_memory_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        # Configuration
        self.config = {
            'relevance_decay_days': 30,  # Knowledge loses relevance after this many days
            'reinforcement_boost': 0.2,   # Boost when knowledge is accessed
            'min_confidence_threshold': 0.3,  # Below this, knowledge is considered unreliable
            'max_related_items': 10,      # Maximum number of related items to track
            'auto_tag_patterns': {        # Patterns for automatic tagging
                r'\b(CLV|closing line value)\b': 'clv',
                r'\b(hedge rule|HR\d+)\b': 'governance',
                r'\b(architect|signoff)\b': 'governance',
                r'\b(sportyb?et|booking)\b': 'booking',
                r'\b(acca|accumulator)\b': 'betting',
                r'\b(dixon-coles|elo|xg)\b': 'model',
                r'\b(gate|threshold)\b': 'configuration',
                r'\b(scan|trigger|publish)\b': 'pipeline',
                r'\b(conversation|fabrication|FAB-\d+)\b': 'auditing',
                r'\b(league|whitelist)\b': 'leagues',
                r'\b(market|odds|price)\b': 'markets',
            }
        }

    def _init_database(self) -> None:
        """Initialize the SQLite database for structured knowledge storage."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    knowledge_type TEXT,
                    source TEXT,
                    tags TEXT,  -- JSON array
                    related_ids TEXT,  -- JSON array
                    created_at TEXT,
                    updated_at TEXT,
                    relevance_score REAL,
                    access_count INTEGER,
                    last_accessed TEXT,
                    confidence REAL,
                    expires_at TEXT,
                    vault_path TEXT,
                    memory_path TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    session_id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    summary TEXT,
                    key_decisions TEXT,  -- JSON array
                    action_items TEXT,  -- JSON array
                    topics_discussed TEXT,  -- JSON array
                    knowledge_items TEXT,  -- JSON array
                    participants TEXT,  -- JSON array
                    files_modified TEXT,  -- JSON array
                    relevance_score REAL
                )
            ''')

            # Create indexes for common queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_type ON knowledge_items(knowledge_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_source ON knowledge_items(source)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_relevance ON knowledge_items(relevance_score)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_updated ON knowledge_items(updated_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tags ON knowledge_items(tags)')

            conn.commit()

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for a knowledge item."""
        timestamp = datetime.now().isoformat()
        hash_input = f"{content[:100]}{timestamp}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def _extract_tags_from_content(self, content: str) -> Set[str]:
        """Automatically extract tags from content based on patterns."""
        tags = set()
        content_lower = content.lower()

        for pattern, tag in self.config['auto_tag_patterns'].items():
            if re.search(pattern, content_lower, re.IGNORECASE):
                tags.add(tag)

        return tags

    def _calculate_relevance(self,
                           created_at: datetime,
                           updated_at: datetime,
                           access_count: int,
                           last_accessed: Optional[datetime]) -> float:
        """Calculate relevance score based on age, updates, and access patterns."""
        now = datetime.now()

        # Base relevance from recency (newer = higher score)
        age_days = (now - updated_at).total_seconds() / 86400
        recency_score = max(0.1, 1.0 - (age_days / self.config['relevance_decay_days']))

        # Access frequency boost
        access_boost = min(0.5, access_count * 0.05)  # Max 0.5 boost from access

        # Recency of access boost
        access_recency_boost = 0.0
        if last_accessed:
            hours_since_access = (now - last_accessed).total_seconds() / 3600
            access_recency_boost = max(0.0, 0.3 * (1 - hours_since_access / 168))  # Decay over week

        # Combine factors
        relevance = recency_score + access_boost + access_recency_boost
        return min(1.0, max(0.0, relevance))  # Clamp to 0-1

    def add_knowledge_item(self,
                          title: str,
                          content: str,
                          knowledge_type: str = 'fact',
                          source: str = 'agent_output',
                          tags: Optional[Set[str]] = None,
                          related_ids: Optional[Set[str]] = None,
                          confidence: float = 1.0,
                          expires_at: Optional[datetime] = None,
                          vault_path: Optional[Path] = None,
                          memory_path: Optional[Path] = None) -> KnowledgeItem:
        """Add a new knowledge item to the persistence system."""

        # Generate ID
        kid = self._generate_id(content)

        # Extract automatic tags
        auto_tags = self._extract_tags_from_content(content)
        all_tags = (tags or set()) | auto_tags

        # Create knowledge item
        item = KnowledgeItem(
            id=kid,
            title=title,
            content=content,
            knowledge_type=knowledge_type,
            source=source,
            tags=all_tags,
            related_ids=related_ids or set(),
            confidence=confidence,
            expires_at=expires_at,
            vault_path=vault_path,
            memory_path=memory_path
        )

        # Calculate initial relevance
        item.relevance_score = self._calculate_relevance(
            item.created_at, item.updated_at,
            item.access_count, item.last_accessed
        )

    def add_clv_evaluation_fact(self, clv_data: dict, source: str = "clv_gate_evaluation") -> str:
        """Add a CLV evaluation fact with enhanced market breakdown (HR60 LENGTH/DEPTH improvement)."""
        # Extract basic CLV data
        legs_with_clv = clv_data.get('legs_with_clv', 0)
        mean_clv = clv_data.get('mean_clv_pct')
        gate_met = clv_data.get('gate_met', False)
        architect_signed_off = clv_data.get('architect_signed_off', False)

        # Build enhanced content with market breakdown
        content_lines = [
            f"CLV Gate Evaluation:",
            f"- Legs with CLV: {legs_with_clv}",
            f"- Mean CLV: {mean_clv:.2f}%" if mean_clv is not None else "- Mean CLV: NO DATA",
            f"- Gate Met: {gate_met}",
            f"- Architect Signed Off: {architect_signed_off}",
        ]

        # Add market breakdown if available (HR60 enhancement)
        market_analysis = clv_data.get('market_analysis', {})
        if market_analysis:
            content_lines.extend([
                "",
                "Per-Market Breakdown:",
            ])
            for market, stats in market_analysis.items():
                content_lines.append(
                    f"- {market}: {stats.get('legs_count', 0)} legs, "
                    f"CLV: {stats.get('mean_clv_pct', 0):.2f}%, "
                    f"Hit Rate: {stats.get('hit_rate', 0):.1%}"
                )

        content = "\n".join(content_lines)

        # Create tags for easy filtering
        tags = {"clv", "evaluation", "gate"}
        if legs_with_clv >= 30:
            tags.add("gate_threshold_met")
        if mean_clv and mean_clv > 0:
            tags.add("positive_clv")

        # Generate title
        mean_clv_str = f"{mean_clv:.2f}%" if mean_clv is not None else "NO DATA"
        title = f"CLV Gate Evaluation - {legs_with_clv} legs, {mean_clv_str} CLV"

        return self.add_knowledge_item(
            title=title,
            content=content,
            knowledge_type="fact",
            source=source,
            tags=tags,
            confidence=0.95
        )

        # Store in database
        self._store_knowledge_item(item)

        # Also save as markdown file for backward compatibility
        self._save_knowledge_as_markdown(item)

        return item

    def _store_knowledge_item(self, item: KnowledgeItem) -> None:
        """Store knowledge item in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO knowledge_items
                (id, title, content, knowledge_type, source, tags, related_ids,
                 created_at, updated_at, relevance_score, access_count,
                 last_accessed, confidence, expires_at, vault_path, memory_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.id,
                item.title,
                item.content,
                item.knowledge_type,
                item.source,
                json.dumps(list(item.tags)),
                json.dumps(list(item.related_ids)),
                item.created_at.isoformat(),
                item.updated_at.isoformat(),
                item.relevance_score,
                item.access_count,
                item.last_accessed.isoformat() if item.last_accessed else None,
                item.confidence,
                item.expires_at.isoformat() if item.expires_at else None,
                str(item.vault_path) if item.vault_path else None,
                str(item.memory_path) if item.memory_path else None
            ))
            conn.commit()

    def _save_knowledge_as_markdown(self, item: KnowledgeItem) -> None:
        """Save knowledge item as markdown file for backward compatibility."""
        # Determine file path based on knowledge type and tags
        if item.vault_path:
            file_path = item.vault_path
        elif item.memory_path:
            file_path = item.memory_path
        else:
            # Default location based on knowledge type
            type_dir = self.knowledge_vault_dir / item.knowledge_type
            type_dir.mkdir(exist_ok=True)
            # Create filename from title
            safe_title = re.sub(r'[^\w\s-]', '', item.title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            file_path = type_dir / f"{safe_title[:50]}.md"

        # Create markdown content
        markdown_content = f"""# {item.title}

**ID**: {item.id}
**Type**: {item.knowledge_type}
**Source**: {item.source}
**Created**: {item.created_at.isoformat()}
**Updated**: {item.updated_at.isoformat()}
**Relevance**: {item.relevance_score:.2f}
**Confidence**: {item.confidence:.2f}
**Tags**: {', '.join(sorted(item.tags)) if item.tags else 'None'}
**Related**: {', '.join(item.related_ids) if item.related_ids else 'None'}

---

{item.content}

---
*Generated by OLP XDV Knowledge Persistence System*
"""

        # Write file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(markdown_content, encoding='utf-8')

        # Update item with actual paths
        item.vault_path = file_path
        # Memory path would be determined by vault-memory sync mappings

    def get_knowledge_item(self, kid: str) -> Optional[KnowledgeItem]:
        """Retrieve a knowledge item by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM knowledge_items WHERE id = ?', (kid,)
            )
            row = cursor.fetchone()

            if row:
                item = KnowledgeItem.from_dict(dict(row))
                # Update access statistics
                self._update_access_stats(item.id)
                return item

        return None

    def _update_access_stats(self, kid: str) -> None:
        """Update access statistics for a knowledge item."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current stats
            cursor = conn.execute(
                'SELECT access_count, relevance_score FROM knowledge_items WHERE id = ?',
                (kid,)
            )
            row = cursor.fetchone()

            if row:
                access_count, relevance_score = row
                # Boost relevance on access
                new_relevance = min(
                    1.0,
                    relevance_score + self.config['reinforcement_boost']
                )
                # Decay boost over time (will be recalculated on next access)

                conn.execute('''
                    UPDATE knowledge_items
                    SET access_count = ?,
                        last_accessed = ?,
                        relevance_score = ?
                    WHERE id = ?
                ''', (
                    access_count + 1,
                    datetime.now().isoformat(),
                    new_relevance,
                    kid
                ))
                conn.commit()

    def search_knowledge(self,
                        query: Optional[str] = None,
                        knowledge_type: Optional[str] = None,
                        tags: Optional[Set[str]] = None,
                        source: Optional[str] = None,
                        min_relevance: float = 0.0,
                        limit: int = 50) -> List[KnowledgeItem]:
        """Search for knowledge items with various filters."""

        # Build SQL query
        where_clauses = []
        params = []

        if query:
            where_clauses.append('(title LIKE ? OR content LIKE ?)')
            search_term = f'%{query}%'
            params.extend([search_term, search_term])

        if knowledge_type:
            where_clauses.append('knowledge_type = ?')
            params.append(knowledge_type)

        if source:
            where_clauses.append('source = ?')
            params.append(source)

        if min_relevance > 0:
            where_clauses.append('relevance_score >= ?')
            params.append(min_relevance)

        # Handle tags (SQLite doesn't have great JSON querying, so we'll do basic matching)
        if tags:
            # For simplicity, we'll fetch and filter in Python for tag matching
            # In production, you might want to use a proper JSON extension or redesign
            pass

        where_clause = ' AND '.join(where_clauses) if where_clauses else '1=1'

        sql = f'''
            SELECT * FROM knowledge_items
            WHERE {where_clause}
            ORDER BY relevance_score DESC, updated_at DESC
            LIMIT ?
        '''
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            items = [KnowledgeItem.from_dict(dict(row)) for row in rows]

            # Post-filter by tags if needed
            if tags:
                items = [item for item in items if tags.issubset(item.tags)]

            return items

    def get_related_knowledge(self, kid: str, max_depth: int = 2) -> List[KnowledgeItem]:
        """Get knowledge items related to a given item."""
        visited = set()
        to_visit = [(kid, 0)]  # (item_id, depth)
        results = []

        while to_visit and len(results) < 50:  # Limit results
            current_id, depth = to_visit.pop(0)

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)

            item = self.get_knowledge_item(current_id)
            if item:
                results.append(item)

                # Add related items to visit queue
                for related_id in item.related_ids:
                    if related_id not in visited:
                        to_visit.append((related_id, depth + 1))

        return results

    def decay_relevance(self) -> int:
        """Apply relevance decay to all knowledge items based on age.

        Returns:
            Number of items updated
        """
        with sqlite3.connect(self.db_path) as conn:
            # Update relevance scores based on age
            cursor = conn.execute('''
                UPDATE knowledge_items
                SET relevance_score =
                    CASE
                        WHEN expires_at IS NOT NULL AND expires_at < ? THEN 0.0
                        ELSE
                            MAX(
                                0.0,
                                MIN(
                                    1.0,
                                    1.0 -
                                    (julianday('now') - julianday(updated_at)) /
                                    ?
                                )
                            )
                    END
                WHERE relevance_score > 0.0
            ''', (datetime.now().isoformat(), self.config['relevance_decay_days']))

            updated_count = cursor.rowcount
            conn.commit()
            return updated_count

    def cleanup_expired_knowledge(self) -> int:
        """Remove expired knowledge items.

        Returns:
            Number of items removed
        """
        with sqlite3.connect(self.db_path) as conn:
            # Delete expired items
            cursor = conn.execute('''
                DELETE FROM knowledge_items
                WHERE expires_at IS NOT NULL AND expires_at < ?
            ''', (datetime.now().isoformat(),))

            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def add_conversation_summary(self, summary: ConversationSummary) -> None:
        """Add a conversation summary to the persistence system."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO conversation_summaries
                (session_id, start_time, end_time, summary, key_decisions,
                 action_items, topics_discussed, knowledge_items,
                 participants, files_modified, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                summary.session_id,
                summary.start_time.isoformat(),
                summary.end_time.isoformat(),
                summary.summary,
                json.dumps(summary.key_decisions),
                json.dumps(summary.action_items),
                json.dumps(list(summary.topics_discussed)),
                json.dumps(summary.knowledge_items),
                json.dumps(list(summary.participants)),
                json.dumps(list(summary.files_modified)),
                summary.relevance_score
            ))
            conn.commit()

    def get_conversation_summaries(self,
                                 days_back: int = 30,
                                 limit: int = 100) -> List[ConversationSummary]:
        """Get conversation summaries from the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days_back)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM conversation_summaries
                WHERE start_time >= ?
                ORDER BY start_time DESC
                LIMIT ?
            ''', (cutoff_date.isoformat(), limit))

            rows = cursor.fetchall()
            summaries = []

            for row in rows:
                data = dict(row)
                # Convert JSON fields back to Python types
                for field in ['key_decisions', 'action_items', 'topics_discussed',
                             'knowledge_items', 'participants', 'files_modified']:
                    if data[field]:
                        data[field] = set(json.loads(data[field]))
                    else:
                        data[field] = set()

                # Convert datetime strings
                for field in ['start_time', 'end_time']:
                    data[field] = datetime.fromisoformat(data[field])

                summaries.append(ConversationSummary(**data))

            return summaries

    def export_knowledge_report(self,
                              output_path: Path,
                              include_low_relevance: bool = False) -> None:
        """Export a comprehensive knowledge report."""
        min_relevance = 0.0 if include_low_relevance else 0.3

        knowledge_items = self.search_knowledge(
            min_relevance=min_relevance,
            limit=1000  # Get a lot of items
        )

        conversations = self.get_conversation_summaries(days_back=90)

        report = {
            'generated_at': datetime.now().isoformat(),
            'total_knowledge_items': len(knowledge_items),
            'total_conversations': len(conversations),
            'knowledge_by_type': {},
            'knowledge_by_source': {},
            'top_tags': {},
            'recent_high_relevance': [],
            'knowledge_items': [item.to_dict() for item in knowledge_items[:50]],  # Top 50
            'recent_conversations': [conv.to_dict() for conv in conversations[:10]]
        }

        # Calculate statistics
        for item in knowledge_items:
            # By type
            kb_type = item.knowledge_type
            report['knowledge_by_type'][kb_type] = report['knowledge_by_type'].get(kb_type, 0) + 1

            # By source
            kb_source = item.source
            report['knowledge_by_source'][kb_source] = report['knowledge_by_source'].get(kb_source, 0) + 1

            # Tags
            for tag in item.tags:
                report['top_tags'][tag] = report['top_tags'].get(tag, 0) + 1

        # Sort top tags
        report['top_tags'] = dict(
            sorted(report['top_tags'].items(), key=lambda x: x[1], reverse=True)[:20]
        )

        # High relevance items
        high_relevance = [item for item in knowledge_items if item.relevance_score >= 0.7]
        report['recent_high_relevance'] = [
            {
                'id': item.id,
                'title': item.title,
                'relevance': item.relevance_score,
                'updated_at': item.updated_at.isoformat()
            }
            for item in sorted(high_relevance, key=lambda x: x.relevance_score, reverse=True)[:10]
        ]

        # Write report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

    def sync_knowledge_to_brain(self, knowledge_item: KnowledgeItem) -> None:
        """Sync a knowledge item to Brain storage if it's model-related.

        This creates a bidirectional link between the knowledge persistence
        system and the Brain for model state synchronization.
        """
        # Only sync items that are likely to be useful for model state
        model_related_tags = {'model_performance', 'dixon_coles', 'elo', 'xg',
                             'clv', 'grading', 'prediction', 'forecast'}

        if not knowledge_item.tags.intersection(model_related_tags):
            return  # Not model-related, skip Brain sync

        # Create a model key based on the knowledge item
        tags_sorted = sorted(knowledge_item.tags)
        model_key = f"knowledge_{knowledge_item.knowledge_type}_{'_'.join(tags_sorted[:3])}"

        # Prepare payload for Brain storage
        payload = {
            'title': knowledge_item.title,
            'content': knowledge_item.content,
            'knowledge_type': knowledge_item.knowledge_type,
            'source': knowledge_item.source,
            'tags': list(knowledge_item.tags),
            'created_at': knowledge_item.created_at.isoformat(),
            'updated_at': knowledge_item.updated_at.isoformat(),
            'confidence': knowledge_item.confidence,
            'relevance_score': knowledge_item.relevance_score
        }

        # Store in Brain (upsert by model_key)
        try:
            self.brain.save_model_state(
                model_key=model_key,
                kind="knowledge_item",
                version=1,
                content_hash=hashlib.sha256(knowledge_item.content.encode()).hexdigest()[:16],
                n_matches=1,  # Knowledge items aren't match-based, so use 1
                last_date=knowledge_item.updated_at.date().isoformat(),
                first_date=knowledge_item.created_at.date().isoformat(),
                payload=payload
            )
        except Exception:
            # Silently fail - Brain sync is best-effort
            pass

    def sync_brain_to_knowledge(self, model_key: str) -> Optional[KnowledgeItem]:
        """Retrieve a model state from Brain and convert it to a knowledge item.

        Args:
            model_key: The Brain model key to retrieve

        Returns:
            KnowledgeItem if found and valid, None otherwise
        """
        try:
            model_state = self.brain.load_model_state(model_key)
            if not model_state:
                return None

            # Only convert if it's actually a knowledge item stored in Brain
            if model_state.get('kind') != "knowledge_item":
                return None

            payload = model_state.get('payload', {})
            if not payload:
                return None

            # Reconstruct knowledge item from Brain payload
            tags = set(payload.get('tags', []))

            knowledge_item = KnowledgeItem(
                id=hashlib.sha256(f"{model_key}:{payload.get('title', '')}".encode()).hexdigest()[:16],
                title=payload.get('title', 'Unknown Knowledge Item'),
                content=payload.get('content', ''),
                knowledge_type=payload.get('knowledge_type', 'fact'),
                source=payload.get('source', 'brain_sync'),
                tags=tags,
                confidence=payload.get('confidence', 0.8),
                relevance_score=payload.get('relevance_score', 0.5),
                created_at=datetime.fromisoformat(payload.get('created_at', datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(payload.get('updated_at', datetime.now().isoformat()))
            )

            return knowledge_item
        except Exception:
            # Silently fail - Brain sync is best-effort
            return None

    def auto_sync_model_knowledge(self, model_key: str, kind: str, payload: dict) -> str:
        """Automatically create and sync knowledge item when storing model state in Brain.

        This is meant to be called from Brain.save_model_state to create
        a corresponding knowledge item for broader accessibility.

        Args:
            model_key: The Brain model key
            kind: The type of model (dixon_coles, elo, etc.)
            payload: The model payload data

        Returns:
            The ID of the created knowledge item
        """
        # Extract useful information from payload to create a knowledge item
        title_parts = [model_key.replace('_', ' ').title()]
        if 'accuracy' in payload:
            title_parts.append(f"Accuracy: {payload['accuracy']:.1%}")
        if 'clv_correlation' in payload:
            title_parts.append(f"CLV Correlation: {payload['clv_correlation']:.2f}")
        if 'sample_size' in payload:
            title_parts.append(f"Sample Size: {payload['sample_size']} matches")

        title = " - ".join(title_parts)

        content_parts = [
            f"Model: {kind}",
            f"Key: {model_key}",
            f"Version: 1"
        ]

        if 'accuracy' in payload:
            content_parts.append(f"- Accuracy: {payload['accuracy']:.1%}")
        if 'clv_correlation' in payload:
            content_parts.append(f"- CLV Correlation: {payload['clv_correlation']:.2f}")
        if 'sample_size' in payload:
            content_parts.append(f"- Sample Size: {payload['sample_size']} matches")
        if 'period' in payload:
            content_parts.append(f"- Period: {payload['period']}")

        content = "\n".join(content_parts)

        # Determine knowledge type based on content
        if 'accuracy' in payload or 'performance' in str(payload).lower():
            knowledge_type = "observation"
        else:
            knowledge_type = "fact"

        # Create tags
        tags = {kind, "model_performance", "brain_sync"}
        if 'accuracy' in payload:
            tags.add("model_accuracy")
        if 'clv_correlation' in payload:
            tags.add("clv_correlation")

        # Add the knowledge item
        knowledge_item = self.add_knowledge_item(
            title=title,
            content=content,
            knowledge_type=knowledge_type,
            source="brain_sync",
            tags=tags,
            confidence=0.8  # Brain-derived knowledge has good confidence
        )

        # Also sync it back to Brain to create the bidirectional link
        # (but avoid infinite recursion by checking if it's already from brain)
        if knowledge_item.source != "brain_sync":
            self.sync_knowledge_to_brain(knowledge_item)

        return knowledge_item.id

    def close(self) -> None:
        """Close database connections."""
        # SQLite connections are closed automatically when using context manager
        # but we close the brain connection if we created it
        if self.brain:
            self.brain.close()


# Global instance for easy access
_knowledge_persistence: Optional[KnowledgePersistence] = None


def get_knowledge_persistence(vault_root: Optional[Path] = None,
                             memory_root: Optional[Path] = None,
                             brain: Optional[Brain] = None) -> KnowledgePersistence:
    """Get or create the global KnowledgePersistence instance."""
    global _knowledge_persistence
    if _knowledge_persistence is None:
        # Default paths if not provided
        if vault_root is None:
            vault_root = Path('c:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv/docs/obsidian-vault')
        if memory_root is None:
            memory_root = Path('c:/Users/Motunrayo/.claude/projects/C--Users-Motunrayo-omniroute-test/memory')

        _knowledge_persistence = KnowledgePersistence(vault_root, memory_root, brain)

    return _knowledge_persistence


# Convenience functions for common operations
def add_fact(title: str, content: str, **kwargs) -> KnowledgeItem:
    """Add a fact to the knowledge base."""
    kwargs.setdefault('knowledge_type', 'fact')
    return get_knowledge_persistence().add_knowledge_item(title, content, **kwargs)

def add_decision(title: str, content: str, **kwargs) -> KnowledgeItem:
    """Add a decision to the knowledge base."""
    kwargs.setdefault('knowledge_type', 'decision')
    return get_knowledge_persistence().add_knowledge_item(title, content, **kwargs)

def add_process(title: str, content: str, **kwargs) -> KnowledgeItem:
    """Add a process to the knowledge base."""
    kwargs.setdefault('knowledge_type', 'process')
    return get_knowledge_persistence().add_knowledge_item(title, content, **kwargs)

def add_observation(title: str, content: str, **kwargs) -> KnowledgeItem:
    """Add an observation to the knowledge base."""
    kwargs.setdefault('knowledge_type', 'observation')
    return get_knowledge_persistence().add_knowledge_item(title, content, **kwargs)

def add_question(title: str, content: str, **kwargs) -> KnowledgeItem:
    """Add a question to the knowledge base."""
    kwargs.setdefault('knowledge_type', 'question')
    return get_knowledge_persistence().add_knowledge_item(title, content, **kwargs)

def search_facts(query: str, **kwargs) -> List[KnowledgeItem]:
    """Search for facts matching a query."""
    kwargs.setdefault('knowledge_type', 'fact')
    return get_knowledge_persistence().search_knowledge(query=query, **kwargs)

def get_recent_decisions(days_back: int = 7, limit: int = 20) -> List[KnowledgeItem]:
    """Get recent decisions."""
    return get_knowledge_persistence().search_knowledge(
        knowledge_type='decision',
        min_relevance=0.5,
        limit=limit
    )