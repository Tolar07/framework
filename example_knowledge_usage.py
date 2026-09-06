"""
Example usage of the Knowledge Persistence system for OLP XDV
Demonstrates how to integrate structured knowledge management
into existing workflows.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from knowledge_persistence import (
    KnowledgePersistence,
    add_fact,
    add_decision,
    add_process,
    add_observation,
    add_question,
    search_facts,
    get_recent_decisions,
    get_knowledge_persistence,
    ConversationSummary
)
from brain.store import Brain


async def example_basic_usage():
    """Demonstrate basic knowledge persistence operations."""
    print("=== Basic Knowledge Persistence Usage ===")

    # Initialize the knowledge persistence system
    kp = get_knowledge_persistence()

    # Add different types of knowledge
    fact_id = add_fact(
        title="CLV Gate Requirements",
        content="The CLV gate requires >=30 legs with CLV AND mean CLV > 0 for publishing to clients",
        knowledge_type="fact",
        source="documentation",
        tags={"clv", "gate", "requirements"},
        confidence=0.95
    )
    print(f"Added fact: {fact_id}")

    decision_id = add_decision(
        title="Architect Signoff for Live Publishing",
        content="ARCHITECT_SIGNOFF=1 allows publishing despite CLV gate not being met, used for side-by-side testing",
        knowledge_type="decision",
        source="architect_directive",
        tags={"governance", "architect", "signoff"},
        confidence=1.0,
        expires_at=datetime.now() + timedelta(days=365)  # Expires in 1 year
    )
    print(f"Added decision: {decision_id}")

    process_id = add_process(
        title="Daily Pipeline Execution",
        content="The daily pipeline runs at 22:00 UTC via Task Scheduler, executing run_daily.py which orchestrates SCAN -> trigger -> publish + CLV loop",
        knowledge_type="process",
        source="operational_documentation",
        tags={"pipeline", "schedule", "daily"},
        confidence=0.9
    )
    print(f"Added process: {process_id}")

    # Search for knowledge
    clv_facts = search_facts("CLV gate", knowledge_type="fact")
    print(f"\nFound {len(clv_facts)} CLV-related facts:")
    for fact in clv_facts:
        print(f"  - {fact.title} (relevance: {fact.relevance_score:.2f})")

    # Get recent decisions
    recent_decisions = get_recent_decisions(days_back=30)
    print(f"\nRecent decisions ({len(recent_decisions)}):")
    for decision in recent_decisions:
        print(f"  - {decision.title} ({decision.knowledge_type})")

    # Get related knowledge
    related = kp.get_related_knowledge(fact_id.id, max_depth=1)
    print(f"\nKnowledge related to '{fact_id.title}':")
    for item in related:
        if item.id != fact_id.id:  # Don't show the original item
            print(f"  - {item.title} ({item.knowledge_type})")

    # Clean up
    kp.close()


async def example_conversation_integration():
    """Example of how to integrate with conversation summarization."""
    print("\n=== Conversation Integration Example ===")

    kp = get_knowledge_persistence()

    # Simulate extracting knowledge from a conversation
    conversation_summary = ConversationSummary(
        session_id='example-session-001',
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now(),
        summary="Discussed CLV gate thresholds and potential adjustments to improve model calibration",
        key_decisions=[
            "Keep CLV gate at >=30 legs for now",
            "Schedule review of mean CLV threshold in 2 weeks"
        ],
        action_items=[
            "Analyze CLV distribution across leagues",
            "Prepare proposal for threshold adjustment"
        ],
        topics_discussed={'CLV', 'model_calibration', 'governance', 'thresholds'},
        knowledge_items=[],  # Will be populated as we extract knowledge
        participants={'Human Analyst', 'CLV Specialist Agent'},
        files_modified={'config.py', 'clv/phase3_gate.py'},
        relevance_score=0.8
    )

    # Extract and store knowledge items from the conversation
    clv_fact = add_fact(
        title="Current CLV Gate Configuration",
        content="As of 2026-09-06, CLV gate requires >=30 legs with CLV AND mean CLV > 0. Current status: 12/30 legs, mean CLV -1.631% (gate NOT met)",
        knowledge_type="fact",
        source="conversation",
        tags={"clv", "gate", "status"},
        confidence=0.9
    )

    # Add the knowledge item ID to the conversation summary
    conversation_summary.knowledge_items.append(clv_fact.id)

    # Store the conversation summary
    kp.add_conversation_summary(conversation_summary)
    print(f"Stored conversation summary with extracted knowledge: {clv_fact.id}")

    # Retrieve and display the conversation
    conversations = kp.get_conversation_summaries(days_back=1)
    if conversations:
        conv = conversations[0]
        print(f"\nRetrieved conversation:")
        print(f"  Session: {conv.session_id}")
        print(f"  Summary: {conv.summary}")
        print(f"  Key decisions: {', '.join(conv.key_decisions)}")
        print(f"  Topics: {', '.join(sorted(conv.topics_discussed))}")
        print(f"  Extracted knowledge: {len(conv.knowledge_items)} items")

    kp.close()


async def example_brain_integration():
    """Example of integrating with the Brain (SQLite) storage."""
    print("\n=== Brain Integration Example ===")

    # Initialize both systems
    brain = Brain()
    kp = get_knowledge_persistence(brain=brain)

    # Example: Store model performance insights in both systems
    model_performance = {
        'model': 'dixon_coles',
        'league': 'Premier League',
        'period': '2026-08-01 to 2026-08-31',
        'accuracy': 0.642,
        'clv_correlation': 0.78,
        'sample_size': 124
    }

    # Store in Brain for operational use
    brain.save_model_state(
        model_key="dixon_coles_premier_league_august_2026",
        kind="dixon_coles",
        version=1,
        content_hash="abc123def456",
        n_matches=model_performance['sample_size'],
        last_date="2026-08-31",
        first_date="2026-08-01",
        payload=model_performance
    )
    print("Stored model performance in Brain")

    # Also create a knowledge item for broader accessibility
    perf_knowledge = add_fact(
        title="Dixon-Coles Model Performance - Premier League August 2026",
        content=f"""Dixon-Coles model performance for Premier League August 2026:
- Accuracy: {model_performance['accuracy']:.1%}
- CLV correlation: {model_performance['clv_correlation']:.2f}
- Sample size: {model_performance['sample_size']} matches
- Period: {model_performance['period']}""",
        knowledge_type="observation",
        source="model_evaluation",
        tags={"model_performance", "dixon_coles", "premier_league", "august_2026"},
        confidence=0.85
    )
    print(f"Created knowledge item for model performance: {perf_knowledge.id}")

    # Demonstrate querying knowledge about models
    model_knowledge = kp.search_knowledge(
        query="dixon coles",
        knowledge_type="observation",
        min_relevance=0.5
    )
    print(f"\nFound {len(model_knowledge)} model-related observations:")
    for item in model_knowledge:
        print(f"  - {item.title}")

    # Clean up
    brain.close()
    kp.close()


async def example_maintenance_operations():
    """Example of maintenance operations on the knowledge base."""
    print("\n=== Maintenance Operations Example ===")

    kp = get_knowledge_persistence()

    # Add some test knowledge that will expire soon
    expiring_fact = add_fact(
        title="Temporary Market Observation",
        content="This is a temporary observation about market behavior that should expire soon",
        knowledge_type="observation",
        source="temporary_analysis",
        tags={"temporary", "market", "observation"},
        confidence=0.6,
        expires_at=datetime.now() + timedelta(hours=1)  # Expires in 1 hour
    )
    print(f"Added expiring fact: {expiring_fact.id}")

    # Check initial count
    initial_count = len(kp.search_knowledge(limit=1000))
    print(f"Initial knowledge items: {initial_count}")

    # Wait a bit to simulate time passing (in real usage, this would be done periodically)
    # await asyncio.sleep(2)  # Uncomment for real delay

    # Apply relevance decay
    decayed_count = kp.decay_relevance()
    print(f"Applied relevance decay to {decayed_count} items")

    # Clean up expired knowledge
    expired_count = kp.cleanup_expired_knowledge()
    print(f"Cleaned up {expired_count} expired knowledge items")

    # Final count
    final_count = len(kp.search_knowledge(limit=1000))
    print(f"Final knowledge items: {final_count}")

    # Export a knowledge report
    report_path = Path("knowledge_report.json")
    kp.export_knowledge_report(report_path, include_low_relevance=True)
    print(f"Exported knowledge report to {report_path}")

    kp.close()


async def main():
    """Run all examples."""
    print("OLP XDV Knowledge Persistence System Examples")
    print("=" * 50)

    await example_basic_usage()
    await example_conversation_integration()
    await example_brain_integration()
    await example_maintenance_operations()

    print("\n" + "=" * 50)
    print("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())