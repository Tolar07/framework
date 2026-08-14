#!/usr/bin/env python3
"""
OLP XDV Pipeline Agent Communication Bus

Provides inter-agent handoff mechanism using the Obsidian vault as the
shared message bus. Each pipeline stage (agents 01-10) writes its output
to a structured JSON file that the next agent can read.

Usage:
    from pipeline_agent_bus import write_agent_handoff, read_agent_handoff

    # Agent 1 writes its output
    write_agent_handoff(1, {"fixtures": [...], "window": "2026-08-14"})

    # Agent 2 reads Agent 1's output
    payload = read_agent_handoff(1)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Vault configuration
VAULT_ROOT = Path(os.environ.get("OLP_XDV_VAULT", r"C:\Users\Motunrayo\Documents\OLP_XDV_Vault"))
HANDOFFS_DIR = VAULT_ROOT / "Pipeline Runs" / "Handoffs"
STAGE_DIR = VAULT_ROOT / "Pipeline Runs" / "Stages"

# Agent definitions matching the 10 pipeline agents
AGENT_NAMES = {
    1: "macro_ingestion",
    2: "list_filter",
    3: "entity_profiling",
    4: "data_verification",
    5: "xdv_core",
    6: "odds_audit",
    7: "compliance",
    8: "execution",
    9: "team_lead",
    10: "ceo",
}

# Handoff schema version
HANDOFF_SCHEMA_VERSION = "1.0"


@dataclass
class AgentHandoff:
    """Structured handoff between pipeline agents."""
    schema_version: str
    timestamp: str
    from_agent: int
    from_agent_name: str
    to_agent: int
    to_agent_name: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]


def ensure_dirs() -> None:
    """Ensure handoff and stage directories exist."""
    HANDOFFS_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_handoff_path(from_agent: int, to_agent: int, run_id: str) -> Path:
    """Get the file path for a specific handoff."""
    return HANDOFFS_DIR / f"{run_id}_agent{from_agent:02d}_to_agent{to_agent:02d}.json"


def get_stage_path(agent_num: int, run_id: str) -> Path:
    """Get the file path for a stage output."""
    name = AGENT_NAMES.get(agent_num, f"agent{agent_num:02d}")
    return STAGE_DIR / f"{run_id}_stage{agent_num:02d}_{name}.json"


def create_run_id() -> str:
    """Generate a unique run identifier."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]


def write_agent_handoff(
    from_agent: int,
    to_agent: int,
    payload: Dict[str, Any],
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Write an agent handoff to the vault.

    Args:
        from_agent: Source agent number (1-10)
        to_agent: Target agent number (1-10)
        payload: The data being passed
        run_id: Optional run identifier (generated if not provided)
        metadata: Optional metadata (duration, status, etc.)

    Returns:
        Path to the written handoff file
    """
    ensure_dirs()

    if run_id is None:
        run_id = create_run_id()

    if from_agent not in AGENT_NAMES or to_agent not in AGENT_NAMES:
        raise ValueError(f"Invalid agent numbers: {from_agent} -> {to_agent}")

    handoff = AgentHandoff(
        schema_version=HANDOFF_SCHEMA_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        from_agent=from_agent,
        from_agent_name=AGENT_NAMES[from_agent],
        to_agent=to_agent,
        to_agent_name=AGENT_NAMES[to_agent],
        payload=payload,
        metadata=metadata or {},
    )

    path = get_handoff_path(from_agent, to_agent, run_id)
    path.write_text(json.dumps(asdict(handoff), indent=2, ensure_ascii=False), encoding="utf-8")

    return path


def read_agent_handoff(
    from_agent: int,
    to_agent: int,
    run_id: Optional[str] = None,
) -> Optional[AgentHandoff]:
    """
    Read an agent handoff from the vault.

    Args:
        from_agent: Source agent number (1-10)
        to_agent: Target agent number (1-10)
        run_id: Specific run ID, or latest if not provided

    Returns:
        AgentHandoff object or None if not found
    """
    if run_id is None:
        # Find latest handoff for this agent pair
        pattern = f"_agent{from_agent:02d}_to_agent{to_agent:02d}.json"
        files = sorted(HANDOFFS_DIR.glob(f"*{pattern}"))
        if not files:
            return None
        path = files[-1]
    else:
        path = get_handoff_path(from_agent, to_agent, run_id)
        if not path.exists():
            return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AgentHandoff(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def write_stage_output(
    agent_num: int,
    payload: Dict[str, Any],
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Write a pipeline stage output to the vault.

    Args:
        agent_num: Agent number (1-10)
        payload: Stage output data
        run_id: Optional run identifier
        metadata: Optional metadata (duration, status, fixtures_count, etc.)

    Returns:
        Path to the written stage file
    """
    ensure_dirs()

    if run_id is None:
        run_id = create_run_id()

    if agent_num not in AGENT_NAMES:
        raise ValueError(f"Invalid agent number: {agent_num}")

    stage_data = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_num,
        "agent_name": AGENT_NAMES[agent_num],
        "run_id": run_id,
        "payload": payload,
        "metadata": metadata or {},
    }

    path = get_stage_path(agent_num, run_id)
    path.write_text(json.dumps(stage_data, indent=2, ensure_ascii=False), encoding="utf-8")

    return path


def read_stage_output(
    agent_num: int,
    run_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Read a pipeline stage output from the vault.

    Args:
        agent_num: Agent number (1-10)
        run_id: Specific run ID, or latest if not provided

    Returns:
        Stage data dict or None if not found
    """
    if run_id is None:
        name = AGENT_NAMES.get(agent_num, f"agent{agent_num:02d}")
        pattern = f"_stage{agent_num:02d}_{name}.json"
        files = sorted(STAGE_DIR.glob(f"*{pattern}"))
        if not files:
            return None
        path = files[-1]
    else:
        path = get_stage_path(agent_num, run_id)
        if not path.exists():
            return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_recent_runs(limit: int = 10) -> List[str]:
    """List recent pipeline run IDs from stage files."""
    files = sorted(STAGE_DIR.glob("*_stage01_*.json"), reverse=True)
    run_ids = []
    for f in files[:limit]:
        # Extract run_id from filename: {run_id}_stage01_...
        parts = f.stem.split("_stage")
        if parts:
            run_ids.append(parts[0])
    return run_ids


def get_pipeline_status(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get the complete status of a pipeline run across all agents."""
    if run_id is None:
        runs = list_recent_runs(1)
        if not runs:
            return {"status": "no_runs_found"}
        run_id = runs[0]

    status = {
        "run_id": run_id,
        "stages": {},
        "handoffs": {},
        "complete": True,
    }

    for agent_num in range(1, 11):
        stage = read_stage_output(agent_num, run_id)
        status["stages"][agent_num] = {
            "name": AGENT_NAMES[agent_num],
            "completed": stage is not None,
            "timestamp": stage["timestamp"] if stage else None,
            "metadata": stage.get("metadata", {}) if stage else {},
        }

        # Check handoff to next agent
        if agent_num < 10:
            handoff = read_agent_handoff(agent_num, agent_num + 1, run_id)
            status["handoffs"][f"{agent_num}->{agent_num+1}"] = {
                "completed": handoff is not None,
                "timestamp": handoff.timestamp if handoff else None,
            }
            if handoff is None:
                status["complete"] = False

    return status


if __name__ == "__main__":
    # Quick test
    import sys

    run_id = create_run_id()
    print(f"Test run_id: {run_id}")

    # Test write/read handoff
    write_agent_handoff(1, 2, {"fixtures": ["match1", "match2"]}, run_id, {"count": 2})
    handoff = read_agent_handoff(1, 2, run_id)
    print(f"Handoff 1->2: {handoff}")

    # Test write/read stage
    write_stage_output(1, {"fixtures": ["match1", "match2"]}, run_id, {"source": "flashscore"})
    stage = read_stage_output(1, run_id)
    print(f"Stage 1: {stage}")

    # Test status
    status = get_pipeline_status(run_id)
    print(f"Status: {json.dumps(status, indent=2)}")

    print("All tests passed!")