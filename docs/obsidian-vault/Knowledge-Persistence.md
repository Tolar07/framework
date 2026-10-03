# Knowledge Persistence System — Enhanced Vault-Memory Concept

> **Builds on existing vault-memory sync to provide structured knowledge management with automatic summarization, intelligent querying, and session-persistent institutional knowledge.**

---

## Overview

The Knowledge Persistence System extends OLP XDV's existing vault-memory synchronization with:

1. **Structured Knowledge Items** — Rich metadata, relationships, relevance scoring, and automatic categorization
2. **Conversation Summarization** — Automatic extraction of key decisions, action items, and knowledge from sessions
3. **Intelligent Query Interface** — Search by content, type, tags, relevance, and relationships
4. **Relevance Decay & Lifecycle** — Automatic aging of knowledge with reinforcement on access
5. **Brain Integration** — Seamless coordination with the existing SQLite Brain for model state

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE PERSISTENCE LAYER                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │   Knowledge     │    │  Conversation   │    │   Relevance │  │
│  │   Items DB      │◄───│   Summaries     │───►│   Engine    │  │
│  │   (SQLite)      │    │   (SQLite)      │    │   (Decay)   │  │
│  └────────┬────────┘    └────────┬────────┘    └──────┬──────┘  │
│           │                      │                      │         │
│           ▼                      ▼                      ▼         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              VULT-MEMORY SYNC (Existing)                    │ │
│  │  Vault (Git) ←→ Memory (Agent) ←→ Conversations Archive    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │                      │                      │         │
│           ▼                      ▼                      ▼         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    BRAIN (SQLite)                           │ │
│  │  Model State │ Predictions │ Legs │ Corrections │ Runs     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Knowledge Item Structure

Each knowledge item has rich metadata:

| Field | Purpose | Example |
|-------|---------|---------|
| `id` | Unique identifier (hash-based) | `a1b2c3d4e5f6` |
| `title` | Human-readable title | "CLV Gate Requirements" |
| `content` | Full knowledge content | "The CLV gate requires ≥30 legs..." |
| `knowledge_type` | Category for filtering | `fact`, `decision`, `process`, `observation`, `question` |
| `source` | Origin of knowledge | `documentation`, `conversation`, `agent_output`, `external` |
| `tags` | Auto-extracted + manual tags | `{"clv", "gate", "requirements"}` |
| `related_ids` | Links to other knowledge | `{"x7y8z9", "m2n3o4"}` |
| `relevance_score` | Dynamic 0-1 score (decays with age) | `0.87` |
| `confidence` | Reliability measure | `0.95` |
| `expires_at` | Optional TTL for temporary knowledge | `2026-09-15T22:00:00` |

---

## Knowledge Types

| Type | Description | Use Cases |
|------|-------------|-----------|
| `fact` | Verifiable, stable information | "CLV gate requires ≥30 legs", "SportyBet max odds = 1.50" |
| `decision` | Explicit Architect/human decisions | "ARCHITECT_SIGNOFF=1 for side-by-side testing" |
| `process` | Operational procedures | "Daily pipeline runs at 22:00 via Task Scheduler" |
| `observation` | Empirical findings, model performance | "Dixon-Coles accuracy 64.2% on Premier League" |
| `question` | Open items needing resolution | "Should O/U 2.5 market weight be increased?" |

---

## Automatic Tagging System

The system automatically tags content using patterns:

| Pattern | Tag | Example Matches |
|---------|-----|-----------------|
| `\b(CLV|closing line value)\b` | `clv` | "CLV", "closing line value" |
| `\b(HR\d+|hedge rule)\b` | `governance` | "HR35", "hedge rule" |
| `\b(architect|signoff)\b` | `governance` | "Architect", "ARCHITECT_SIGNOFF" |
| `\b(sportyb?et|booking)\b` | `booking` | "SportyBet", "booking code" |
| `\b(acca|accumulator)\b` | `betting` | "Acca A", "accumulator" |
| `\b(dixon-coles|elo|xg)\b` | `model` | "Dixon-Coles", "xG" |
| `\b(gate|threshold)\b` | `configuration` | "CLV gate", "odds threshold" |
| `\b(scan|trigger|publish)\b` | `pipeline` | "SCAN stage", "trigger production" |

---

## Relevance Scoring Algorithm

```
relevance = recency_score + access_boost + access_recency_boost

Where:
- recency_score = max(0.1, 1.0 - (days_since_update / decay_days))
- access_boost = min(0.5, access_count × 0.05)
- access_recency_boost = max(0, 0.3 × (1 - hours_since_access / 168))

Decay period: 30 days (configurable)
Reinforcement boost per access: 0.2
```

**Behavior:**
- New knowledge starts at relevance ~1.0
- Accessing knowledge boosts its relevance
- Unaccessed knowledge decays over ~30 days
- Expired knowledge (confidence < 0.3 or explicit TTL) is automatically cleaned up

---

## Conversation Summarization

Each session generates a structured summary:

```yaml
session_id: "example-session-001"
start_time: "2026-09-06T14:00:00"
end_time: "2026-09-06T16:30:00"
summary: "Discussed CLV gate thresholds and potential adjustments"
key_decisions:
  - "Keep CLV gate at ≥30 legs for now"
  - "Schedule review of mean CLV threshold in 2 weeks"
action_items:
  - "Analyze CLV distribution across leagues"
  - "Prepare proposal for threshold adjustment"
topics_discussed: ["CLV", "model_calibration", "governance", "thresholds"]
knowledge_items: ["a1b2c3d4e5f6", "x7y8z9a1b2c3"]  # IDs of extracted knowledge
participants: ["Human Analyst", "CLV Specialist Agent"]
files_modified: ["config.py", "clv/phase3_gate.py"]
relevance_score: 0.8
```

---

## Integration Points

### 1. With Existing Vault-Memory Sync

The knowledge persistence system **complements** (not replaces) the existing sync:

- **Vault files** → Markdown representations of knowledge items (backward compatible)
- **Memory files** → SQLite database for fast querying + markdown mirrors
- **Sync mappings** → Extended to include knowledge directories

### 2. With Brain (SQLite)

```python
# Example: Store model performance in both systems
brain.save_model_state(
    model_key="dixon_coles_premier_league_august_2026",
    kind="dixon_coles",
    version=1,
    payload=performance_data  # Operational use
)

# Also create knowledge item for broader accessibility
add_fact(
    title="Dixon-Coles Performance - Premier League August 2026",
    content=f"Accuracy: 64.2%, CLV correlation: 0.78, n=124",
    knowledge_type="observation",
    source="model_evaluation",
    tags={"model_performance", "dixon_coles", "premier_league"}
)
```

### 3. With Pipeline Operations

```python
# In run_daily.py - after CLV grading
def _grade_open_legs(...):
    # ... existing grading logic ...

    # NEW: Capture outcome as knowledge
    add_observation(
        title=f"CLV Grading Results - {date}",
        content=f"Graded {graded_count} legs, {hit_count} hits, mean CLV {mean_clv:.2f}%",
        knowledge_type="observation",
        source="pipeline_operation",
        tags={"clv", "grading", date},
        confidence=1.0
    )
```

---

## Query Interface

### Python API

```python
from knowledge_persistence import (
    get_knowledge_persistence,
    add_fact, add_decision, add_process,
    add_observation, add_question,
    search_facts, get_recent_decisions
)

# Initialize
kp = get_knowledge_persistence()

# Add knowledge
add_fact("Title", "Content", tags={"tag1", "tag2"})

# Search
results = kp.search_knowledge(
    query="CLV gate",
    knowledge_type="fact",
    tags={"governance"},
    min_relevance=0.5,
    limit=20
)

# Get related knowledge (graph traversal)
related = kp.get_related_knowledge("item_id", max_depth=2)

# Export report
kp.export_knowledge_report(Path("report.json"))
```

### Convenience Functions

```python
# Quick additions
add_fact("Fact Title", "Content", tags={"tag"})
add_decision("Decision Title", "Content", confidence=0.9)
add_process("Process Title", "Content")
add_observation("Observation Title", "Content", source="pipeline")

# Quick searches
search_facts("query", knowledge_type="fact", limit=10)
get_recent_decisions(days_back=7, limit=20)
```

---

## Maintenance Operations

### Periodic Tasks (Run Daily/Weekly)

```python
# Apply relevance decay (reduces scores based on age)
kp.decay_relevance()

# Clean up expired knowledge
kp.cleanup_expired_knowledge()

# Export knowledge report for audit
kp.export_knowledge_report(
    Path("vault/knowledge/reports/knowledge_report_2026-09-06.json"),
    include_low_relevance=False
)
```

### Configuration Options

```python
config = {
    'relevance_decay_days': 30,        # Knowledge half-life
    'reinforcement_boost': 0.2,         # Boost on access
    'min_confidence_threshold': 0.3,    # Below this = unreliable
    'max_related_items': 10,            # Graph traversal limit
    'auto_tag_patterns': {...}          # Custom tagging rules
}
```

---

## Usage in OLP XDV Workflows

### 1. Session Start (Agent Initialization)

```python
# In session startup hook
kp = get_knowledge_persistence()

# Load recent high-relevance knowledge for context
recent_knowledge = kp.search_knowledge(
    min_relevance=0.7,
    limit=20
)

# Load recent conversations for continuity
recent_conversations = kp.get_conversation_summaries(days_back=7)
```

### 2. During Pipeline Execution

```python
# In run_daily.py after key stages
kp = get_knowledge_persistence()

# SCAN stage completion
add_observation(
    title=f"SCAN Complete - {board_date}",
    content=f"Scanned {leagues_scanned} leagues, {fixtures_found} fixtures",
    knowledge_type="observation",
    source="pipeline_stage",
    tags={"scan", "daily_pipeline", board_date}
)

# Trigger stage - bet production
add_decision(
    title=f"Production Bet Decision - {board_date}",
    content=f"Acca A: {len(acca_a)} legs, Split accas: {len(split_accas)}, Singles: {len(singles)}",
    knowledge_type="decision",
    source="pipeline_production",
    tags={"production", "bet_decision", board_date}
)

# CLV gate evaluation
add_fact(
    title=f"CLV Gate Status - {board_date}",
    content=f"Legs with CLV: {legs_with_clv}/30, Mean CLV: {mean_clv:.2f}%, Gate: {'MET' if gate_met else 'NOT MET'}",
    knowledge_type="fact",
    source="clv_gate",
    tags={"clv", "gate_status", board_date}
)
```

### 3. Session End (Agent Cleanup)

```python
# In stop hook
kp = get_knowledge_persistence()

# Create conversation summary
summary = create_conversation_summary(
    session_id=current_session_id,
    start_time=session_start,
    end_time=datetime.now(),
    # ... extract from transcript
)
kp.add_conversation_summary(summary)

# Export daily knowledge report
kp.export_knowledge_report(
    Path(f"vault/knowledge/reports/daily_{date.today().isoformat()}.json")
)
```

---

## Migration from Current System

### Phase 1: Parallel Operation (Current → Enhanced)

1. Deploy `knowledge_persistence.py` alongside existing sync
2. Run both systems in parallel for validation
3. Verify knowledge items sync correctly to vault/memory

### Phase 2: Conversation Integration

1. Modify Stop hook to extract knowledge from transcripts
2. Create conversation summaries for last 30 days
3. Validate extraction quality

### Phase 3: Pipeline Integration

1. Add knowledge capture to `run_daily.py` stages
2. Integrate with `brain/store.py` for model state knowledge
3. Add `knowledge_persistence` to monitoring/health checks

### Phase 4: Full Replacement

1. Deprecate manual markdown memory files
2. Use knowledge DB as primary query interface
3. Vault markdown files become export/backup format

---

## Benefits Over Current System

| Aspect | Current Vault-Memory | Enhanced Knowledge Persistence |
|--------|---------------------|-------------------------------|
| **Query Capability** | File-based search only | Structured SQL + full-text search |
| **Relationships** | Manual wiki-links only | Automatic graph traversal |
| **Relevance** | Static (newest wins) | Dynamic scoring with decay/reinforcement |
| **Conversation History** | Raw transcripts only | Structured summaries + extracted knowledge |
| **Automation** | Manual curation | Auto-tagging, auto-expiration, auto-decay |
| **Integration** | Separate from Brain | Unified with model state |
| **Audit Trail** | Git history only | Structured reports + compliance logs |

---

## Future Enhancements

1. **Semantic Search** — Vector embeddings for similarity queries
2. **Knowledge Graph Visualization** — D3.js/Graphify integration
3. **Agent Memory API** — Standardized interface for agents to query/store
4. **Cross-Session Learning** — Pattern recognition across conversations
5. **Predictive Relevance** — ML-based relevance prediction
6. **Knowledge Distillation** — Automatic synthesis of related items

---

## Files

| File | Purpose |
|------|---------|
| `knowledge_persistence.py` | Core implementation |
| `example_knowledge_usage.py` | Usage examples |
| `docs/obsidian-vault/Knowledge-Persistence.md` | This documentation |
| `vault/knowledge/` | Markdown exports (auto-generated) |
| `memory/knowledge/knowledge.db` | SQLite database |
| `memory/knowledge/conversations/` | Conversation summaries |

---

*Part of OLP XDV enhanced knowledge persistence initiative*
*Complements existing vault-memory sync (HR54 compliant)*