#!/usr/bin/env python3
"""
OLP XDV variant selection module — config-driven variant population for evolutionary algorithm.

This module replaces the Conway-sandbox variant selection with a clean, config-based
approach that integrates with the OLP XDV pipeline. All Conway-specific dependencies
have been removed - the agent now uses variant_ledger_log.jsonl for state and
getVariantPopulationStatus() for fitness metrics.

Key features:
- Config-driven variant definitions (JSON/YAML)
- Support for multiple variant types (league-based, market-based, etc.)
- Fitness metrics computed from variant_ledger_log.jsonl
- Bridge functions for OLP XDV integration
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Path to the variant ledger (JSONL format)
VARIANT_LEDGER_PATH = Path(__file__).parent / "variant_ledger_log.jsonl"

# Default config if no external config is provided
DEFAULT_CONFIG = {
    "variant_types": [
        "league_based",  # variants based on league groupings
        "market_based",  # variants based on market key groupings
        "team_based",    # variants based on team groupings
    ],
    "default_variant_id": "default",
    "fitness_metrics": [
        "mean_fitness",
        "best_fitness",
        "worst_fitness",
        "alive_variants",
        "dead_variants",
        "window_size",
        "deaths_this_window",
    ],
    "window_size": 100,
}

# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

@dataclass
class Variant:
    variant_id: str
    variant_type: str
    odds_band: str
    fitness: float
    legs_in_window: int
    wins: int
    losses: int
    status: str  # "alive" | "dead" | "pending"
    created_at: str
    last_bet_at: Optional[str] = None

@dataclass
class VariantMetrics:
    total_variants: int
    alive_variants: int
    dead_variants: int
    mean_fitness: float
    best_fitness: float
    worst_fitness: float
    window_size: int
    deaths_this_window: int
    replications_this_window: int

# ---------------------------------------------------------------------------
# CORE FUNCTIONS
# ---------------------------------------------------------------------------

def load_variant_ledger() -> List[Dict[str, Any]]:
    """Load variant ledger from JSONL file."""
    if not VARIANT_LEDGER_PATH.exists():
        return []
    with open(VARIANT_LEDGER_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines if line.strip()]

def save_variant_ledger(ledger: List[Dict[str, Any]]) -> None:
    """Save variant ledger to JSONL file."""
    with open(VARIANT_LEDGER_PATH, 'w', encoding='utf-8') as f:
        for entry in ledger:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def compute_variant_metrics(ledger: List[Dict[str, Any]]) -> VariantMetrics:
    """Compute rolling-window fitness metrics from variant ledger."""
    if not ledger:
        return VariantMetrics(
            total_variants=0,
            alive_variants=0,
            dead_variants=0,
            mean_fitness=0.0,
            best_fitness=0.0,
            worst_fitness=0.0,
            window_size=100,
            deaths_this_window=0,
            replications_this_window=0,
        )

    # Sort by timestamp (assuming ISO format)
    sorted_ledger = sorted(ledger, key=lambda x: x.get('timestamp', ''))
    window_size = 100  # default window size

    # Get the most recent 'window_size' entries
    recent_entries = sorted_ledger[-window_size:] if len(sorted_ledger) >= window_size else sorted_ledger

    total_variants = len(ledger)
    alive_variants = sum(1 for v in ledger if v.get('status') == 'alive')
    dead_variants = sum(1 for v in ledger if v.get('status') == 'dead')

    # Calculate fitness metrics
    fitnesses = [v.get('fitness', 0.0) for v in ledger]
    mean_fitness = sum(fitnesses) / len(fitnesses) if fitnesses else 0.0
    best_fitness = max(fitnesses) if fitnesses else 0.0
    worst_fitness = min(fitnesses) if fitnesses else 0.0

    # Count deaths in the window
    deaths_this_window = sum(1 for v in recent_entries if v.get('status') == 'dead' and 'timestamp' in v)

    return VariantMetrics(
        total_variants=total_variants,
        alive_variants=alive_variants,
        dead_variants=dead_variants,
        mean_fitness=mean_fitness,
        best_fitness=best_fitness,
        worst_fitness=worst_fitness,
        window_size=window_size,
        deaths_this_window=deaths_this_window,
        replications_this_window=0,  # Could be extended later
    )

# ---------------------------------------------------------------------------
# VARIANT SELECTION LOGIC
# ---------------------------------------------------------------------------

def get_variant_population_status() -> Dict[str, Any]:
    """Get current variant population status and metrics."""
    ledger = load_variant_ledger()
    metrics = compute_variant_metrics(ledger)

    # Get all variants
    variants = []
    for entry in ledger:
        if 'variant_id' in entry:
            variants.append({
                'variantId': entry['variant_id'],
                'oddsBand': entry.get('odds_band', ''),
                'fitness': entry.get('fitness', 0.0),
                'legsInWindow': entry.get('legs_in_window', 0),
                'wins': entry.get('wins', 0),
                'losses': entry.get('losses', 0),
                'status': entry.get('status', 'pending'),
                'createdAt': entry.get('created_at', ''),
                'lastBetAt': entry.get('last_bet_at', ''),
            })

    return {
        'variants': variants,
        'summary': {
            'totalVariants': len(variants),
            'aliveVariants': sum(1 for v in variants if v['status'] == 'alive'),
            'deadVariants': sum(1 for v in variants if v['status'] == 'dead'),
            'meanFitness': metrics.mean_fitness,
            'bestFitness': metrics.best_fitness,
            'worstFitness': metrics.worst_fitness,
            'windowSize': metrics.window_size,
            'deathsThisWindow': metrics.deaths_this_window,
            'replicationsThisWindow': metrics.replications_this_window,
        }
    )

def add_variant(variant_id: str, variant_type: str, odds_band: str, fitness: float) -> bool:
    """Add a new variant to the ledger."""
    ledger = load_variant_ledger()

    # Check if variant already exists
    for entry in ledger:
        if entry.get('variant_id') == variant_id:
            return False  # Already exists

    # Create new variant entry
    new_entry = {
        'variant_id': variant_id,
        'variant_type': variant_type,
        'odds_band': odds_band,
        'fitness': fitness,
        'legs_in_window': 0,
        'wins': 0,
        'losses': 0,
        'status': 'alive',
        'created_at': datetime.utcnow().isoformat(),
        'timestamp': datetime.utcnow().isoformat(),
    }

    ledger.append(entry)
    save_variant_ledger(ledger)
    return True

def update_variant_status(variant_id: str, status: str, fitness: Optional[float] = None) -> bool:
    """Update variant status and fitness."""
    ledger = load_variant_ledger()
    updated = False

    for entry in ledger:
        if entry.get('variant_id') == variant_id:
            entry['status'] = status
            if fitness is not None:
                entry['fitness'] = fitness
                entry['timestamp'] = datetime.utcnow().isoformat()
                entry['last_bet_at'] = datetime.utcnow().isoformat()
            updated = True
            break

    if updated:
        save_variant_ledger(ledger)
        return True
    return False

# ---------------------------------------------------------------------------
# BRIDGE FUNCTIONS FOR OLP XDV INTEGRATION
# ---------------------------------------------------------------------------

def get_variant_population_status_bridge() -> Dict[str, Any]:
    """Bridge function for OLP XDV variant selection (replaces Conway-specific logic)."""
    return get_variant_population_status()

def compute_survival_tier_from_variants(variants_data: Dict[str, Any]) -> str:
    """Compute survival tier from variant population data."""
    summary = variants_data['summary']

    # Simple heuristic: if mean fitness is positive and we have enough alive variants,
    # consider it a high survival tier
    if summary['meanFitness'] > 0 and summary['aliveVariants'] > 0:
        if summary['aliveVariants'] / summary['totalVariants'] > 0.7:
            return "high"
        elif summary['aliveVariants'] / summary['totalVariants'] > 0.3:
            return "medium"
        else:
            return "low"
    else:
        return "critical"

# ---------------------------------------------------------------------------
# MOTIVATION LOGIC — Fitness-based selection pressure for variant evolution
# ---------------------------------------------------------------------------

# Import here to avoid circular dependency
from daily_analysis_agent import (
    compute_motivation_signals,
    apply_motivation_signals,
    MotivationSignal,
)

# Re-export for external use
__all__ = [
    "load_variant_ledger",
    "save_variant_ledger",
    "compute_variant_metrics",
    "get_variant_population_status",
    "add_variant",
    "update_variant_status",
    "get_variant_population_status_bridge",
    "compute_survival_tier_from_variants",
    "load_config",
    "apply_config",
    # Motivation logic exports
    "compute_motivation_signals",
    "apply_motivation_signals",
    "MotivationSignal",
]


# ---------------------------------------------------------------------------
# CONFIGURATION MANAGEMENT
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file or use default."""
    config_path = config_path or "variant_selection_config.json"
    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return DEFAULT_CONFIG.copy()

def apply_config(config: Dict[str, Any]) -> None:
    """Apply configuration changes (e.g., update window size)."""
    # This could be extended to actually modify the ledger or config file
    pass

# ---------------------------------------------------------------------------
# MAIN EXECUTION (for direct testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example usage
    print("OLP XDV variant selection module")
    print("Loading variant ledger...")
    ledger = load_variant_ledger()
    print(f"Loaded {len(ledger)} variant entries")

    print("Computing metrics...")
    metrics = compute_variant_metrics(ledger)
    print(f"Metrics: {metrics.__dict__}")

    print("Getting variant population status...")
    status = get_variant_population_status()
    print(f"Status: {status['summary']}")

    # Example: add a new variant
    # add_variant("var_001", "league_based", "EPL", 1.5, 0, 0, 0, "alive")
    # print("Added variant")

    print("Done.")