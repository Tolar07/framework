#!/usr/bin/env python3
"""OLP XDV Agent CLI — read-only query surface for the brain, CLV ledger, board, and audit.

Source-run, stdlib-only (argparse). Mirrors the sports-skills pattern:
- `--json` for structured output (envelope: {"status": true, "data": ..., "message": ""})
- Human-readable text by default
- Graceful errors (no tracebacks), HR35 honest "NO DATA — PENDING" for missing data
- Windows-safe stdout reconfigure for UTF-8 glyphs

Usage:
    py -3.12 agent_cli.py <command> [--json] [--brain <path>] [opts]

Commands:
    stats          Brain overview (CLV by market/league/tier, gate, telemetry, outcomes, produced bets, last run)
    lookup <query> What did we predict for a team/fixture
    board [--date D] [--raw|--published]  Produced board JSON for a date (default: latest)
    clv [--by market|league|tier] [--phase P]  CLV breakdown
    gate           Phase-3 gate status + road-to-gate
    audit [--no-odds] [--league L]  League coverage audit (READY/BLOCKED per league)
    leagues        Whitelisted leagues + tier
    livescores [--league L] [--day D]  Live in-play scores for a league (default: today)
    schema         JSON-Schema tool definitions for agent tool-loading
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

# Windows cp1252 consoles: ensure UTF-8 so ✅/box glyphs never crash
with suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")

# --- Import pattern mirrors league_audit.py ---
# Insert repo root so `import brain`, `import engine`, `import webapp` work
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

# Season codes for the league audit — match league_audit.py defaults:
# fit on the completed 25-26 season, fixture-check the live 26-27 season.
FIT_SEASON = "2526"
FIXTURES_SEASON = "2627"

# Lazy imports inside command handlers to keep --help fast


def success(data: Any, message: str = "") -> dict:
    """Structured success envelope (mirrors sports-skills _response.success)."""
    return {"status": True, "data": data, "message": message}


def error(message: str, data: Any = None) -> dict:
    """Structured error envelope (mirrors sports-skills _response.error)."""
    return {"status": False, "data": data, "message": message}


def print_json(obj: dict) -> None:
    """Pretty-print JSON to stdout."""
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def print_text(text: str) -> None:
    """Print plain text to stdout."""
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def get_brain_path(args) -> Path:
    """Resolve brain path from --brain flag or default."""
    if args.brain:
        return Path(args.brain)
    from brain.store import DEFAULT_BRAIN_PATH

    return DEFAULT_BRAIN_PATH


def cmd_stats(args) -> int:
    """Brain overview: CLV by market/league/tier, gate, telemetry, outcomes, produced bets, last run."""
    brain_path = get_brain_path(args)
    if not brain_path.exists():
        msg = f"Brain not found at {brain_path}"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    from brain.report import render_stats
    from brain.store import Brain

    brain = Brain(brain_path)

    if args.json:
        # Structured: pull each section via Brain methods directly
        data = {
            "overview": brain.predictions_summary(),
            "clv_by_market": brain.clv_by_market(args.phase),
            "clv_by_league": brain.clv_by_league(args.phase),
            "clv_by_pool": brain.clv_by_pool(args.phase),
            "engine_clv": brain.engine_clv(args.phase),
            "calibration_by_market": brain.calibration_by_market(args.phase),
            "gate_status": brain.gate_status(),
            "leg_telemetry": brain.leg_telemetry(args.phase),
            "produced_bets": brain.produced_bets_summary(args.limit),
            "last_run": brain.last_run(),
        }
        print_json(success(data))
    else:
        # Human-readable: reuse the existing render_stats (covers overview + lookup style)
        # render_stats with empty arg gives overview
        text = render_stats(brain, "")
        print_text(text)
    return 0


def cmd_lookup(args) -> int:
    """What did we predict for a team/fixture."""
    brain_path = get_brain_path(args)
    if not brain_path.exists():
        msg = f"Brain not found at {brain_path}"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    from brain.report import render_stats
    from brain.store import Brain

    brain = Brain(brain_path)

    if args.json:
        # Structured: use predictions_for with the query as team/fixture
        # The query can be a team name, fixture, or date — we pass it to team/fixture
        # and let the DB's _fold() match do the work
        rows = brain.predictions_for(
            fixture=args.query,
            team=args.query,
            match_date=None,
            market=None,
            engine=None,
            run_id=None,
            limit=args.limit,
        )
        if not rows:
            print_json(success([], message="NO DATA — PENDING"))
        else:
            print_json(success(rows))
    else:
        # Human-readable: reuse render_stats with the query
        text = render_stats(brain, args.query)
        print_text(text)
    return 0


def cmd_board(args) -> int:
    """Produced board JSON for a date (default: latest)."""
    from webapp.schema import list_published_dates, read_payload, read_published

    # Resolve date
    if args.date:
        date_str = args.date
    else:
        dates = list_published_dates()
        if not dates:
            msg = "No published boards found"
            if args.json:
                print_json(error(msg))
            else:
                print_text(f"ERROR: {msg}")
            return 1
        date_str = dates[0]  # latest

    try:
        if args.raw:
            payload = read_payload(REPO_ROOT / "output" / "boards" / f"board_{date_str}.json")
        else:
            payload = read_published(date_str)
    except FileNotFoundError:
        msg = f"No board data for {date_str}"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    if args.json:
        print_json(success(payload))
    else:
        # Pretty-print the board
        print_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_clv(args) -> int:
    """CLV breakdown by market/league/pool."""
    by = args.by or "market"
    phase = args.phase

    if by not in ("market", "league", "pool"):
        msg = f"Unknown --by value: {by} (expected market|league|pool)"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    brain_path = get_brain_path(args)
    if not brain_path.exists():
        msg = f"Brain not found at {brain_path}"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    from brain.store import Brain

    brain = Brain(brain_path)

    if by == "market":
        data = brain.clv_by_market(phase)
    elif by == "league":
        data = brain.clv_by_league(phase)
    else:  # pool
        data = brain.clv_by_pool(phase)

    if args.json:
        print_json(success(data))
    else:
        if not data:
            print_text("NO DATA — PENDING")
        else:
            for row in data:
                if by == "market":
                    print_text(f"  {row['market']}: n={row['n']} mean_clv_pct={row['mean_clv_pct']:.2f}% beat_close={row['n_beat_close']}")
                elif by == "league":
                    print_text(f"  {row['league']}: n={row['n']} mean_clv_pct={row['mean_clv_pct']:.2f}%")
                elif by == "pool":
                    print_text(f"  {row['pool']}: n={row['n']} mean_clv_pct={row['mean_clv_pct']:.2f}%")
    return 0


def cmd_gate(args) -> int:
    """Phase-3 gate status + road-to-gate."""
    brain_path = get_brain_path(args)
    if not brain_path.exists():
        msg = f"Brain not found at {brain_path}"
        if args.json:
            print_json(error(msg))
        else:
            print_text(f"ERROR: {msg}")
        return 1

    from brain.store import Brain

    brain = Brain(brain_path)

    if args.json:
        data = {
            "gate_status": brain.gate_status(),
            "leg_telemetry": brain.leg_telemetry(args.phase),
        }
        print_json(success(data))
    else:
        gate = brain.gate_status()
        telemetry = brain.leg_telemetry(args.phase)
        print_text("=== PHASE-3 GATE STATUS ===")
        print_text(f"  Legs logged total: {gate.get('legs_logged_total', 0)}")
        print_text(f"  Legs with CLV: {gate.get('legs_with_clv', 0)}")
        print_text(f"  Gate requirement: {gate.get('gate_requirement', 'N/A')}")
        print_text(f"  Mean CLV: {gate.get('mean_clv_pct', 0):.2f}%")
        print_text(f"  Positive mean CLV: {gate.get('positive_mean_clv', False)}")
        print_text(f"  Gate met (pending architect signoff): {gate.get('gate_met_pending_architect_signoff', False)}")
        print_text(f"  Note: {gate.get('note', '')}")
        print_text("")
        print_text("=== LEG TELEMETRY ===")
        print_text(f"  Total legs: {telemetry.get('n_legs', 0)}")
        print_text(f"  With CLV: {telemetry.get('n_with_clv', 0)}")
        print_text(f"  Settled: {telemetry.get('n_settled', 0)}")
        print_text(f"  CLV capture rate: {telemetry.get('clv_capture_rate', 'N/A')}")
        print_text(f"  Legs per day: {telemetry.get('legs_per_day', 0)}")
        print_text(f"  CLV legs per day: {telemetry.get('clv_legs_per_day', 'N/A')}")
        print_text(f"  Days to gate: {telemetry.get('days_to_gate', 'N/A')}")
    return 0


def cmd_audit(args) -> int:
    """League coverage audit (READY/BLOCKED per league)."""
    # Import config first to load .env (exactly like league_audit.py); config.py
    # may not exist — league_audit handles that itself.
    with suppress(ImportError):
        import config  # noqa: F401

    from engine.leagues import WHITELISTED_LEAGUES
    from league_audit import audit

    leagues_to_audit = [args.league] if args.league else WHITELISTED_LEAGUES

    results = {}
    for league in leagues_to_audit:
        try:
            # league_audit.audit returns a per-league dict; READY = no blockers
            row = audit(league, FIT_SEASON, FIXTURES_SEASON, not args.no_odds)
            results[league] = {
                "ready": not row["blockers"],
                "deploy_eligible": row["deploy_eligible"],
                "history": row["history"],
                "fixtures": row["fixtures"],
                "odds": row["odds"],
                "names": row["names"],
                "blockers": row["blockers"],
            }
        except Exception as e:
            results[league] = {"ready": False, "blockers": [str(e)]}

    if args.json:
        print_json(success(results))
    else:
        for league, result in results.items():
            status = "READY" if result["ready"] else "BLOCKED"
            print_text(f"{league}: {status}")
            blockers = result.get("blockers", [])
            for b in blockers:
                print_text(f"  - {b}")
    return 0


def cmd_leagues(args) -> int:
    """Whitelisted leagues."""
    from engine.leagues import WHITELISTED_LEAGUES

    if args.json:
        data = [{"league": league} for league in WHITELISTED_LEAGUES]
        print_json(success(data))
    else:
        print_text(f"WHITELISTED LEAGUES ({len(WHITELISTED_LEAGUES)}):")
        for league in WHITELISTED_LEAGUES:
            print_text(f"  {league}")
    return 0


def cmd_livescores(args) -> int:
    """Live in-play scores for a league (default: today)."""
    from data.multi_source_concrete import get_live_scores
    from data.live_scores import LiveScore

    if args.league:
        leagues = [args.league]
    else:
        from engine.leagues import WHITELISTED_LEAGUES
        leagues = list(WHITELISTED_LEAGUES)

    day = args.day  # None -> today (source uses today by default)
    results: dict = {}

    for league in leagues:
        try:
            data = get_live_scores(league, day=day)
            scores: list[LiveScore] = data.get("scores", [])
            results[league] = {
                "source": data.get("source", "?"),
                "scores": [
                    {
                        "home": s.home_team,
                        "away": s.away_team,
                        "home_score": s.home_score,
                        "away_score": s.away_score,
                        "status": s.status,
                        "minute": s.minute,
                        "kickoff": s.kickoff.isoformat() if s.kickoff else None,
                    }
                    for s in scores
                ],
            }
        except Exception as e:
            results[league] = {"error": str(e)}

    if args.json:
        print_json(success(results))
    else:
        for league, data in results.items():
            print_text(f"\n=== {league} ===")
            if "error" in data:
                print_text(f"  ERROR: {data['error']}")
                continue
            scores = data.get("scores", [])
            if not scores:
                print_text("  NO DATA — PENDING")
                continue
            for s in scores:
                minute = f" ({s['minute']}')" if s.get("minute") else ""
                print_text(f"  {s['home']} {s['home_score']} - {s['away_score']} {s['away']} "
                           f"[{s['status']}{minute}]")
    return 0


def cmd_pipeline_status(args) -> int:
    """Show pipeline run status from Obsidian vault."""
    from pipeline_agent_bus import get_pipeline_status, list_recent_runs

    if args.json:
        if args.run_id:
            status = get_pipeline_status(args.run_id)
        else:
            runs = list_recent_runs(1)
            if not runs:
                print_json(success({"status": "no_runs_found", "runs": []}))
                return 0
            status = get_pipeline_status(runs[0])
        print_json(success(status))
    else:
        if args.run_id:
            status = get_pipeline_status(args.run_id)
        else:
            runs = list_recent_runs(1)
            if not runs:
                print_text("NO DATA — PENDING")
                return 0
            status = get_pipeline_status(runs[0])

        print_text(f"=== PIPELINE STATUS: {status['run_id']} ===")
        print_text(f"Complete: {status.get('complete', False)}")
        print_text("")
        for agent_num in range(1, 11):
            s = status["stages"].get(agent_num, {})
            name = s.get("name", f"agent{agent_num:02d}")
            completed = s.get("completed", False)
            ts = s.get("timestamp", "N/A")
            print_text(f"  Stage {agent_num:02d} ({name}): {'���' if completed else '���'} {ts}")
        print_text("")
        for handoff, h in status["handoffs"].items():
            completed = h.get("completed", False)
            ts = h.get("timestamp", "N/A")
            print_text(f"  Handoff {handoff}: {'���' if completed else '���'} {ts}")
    return 0


def cmd_vault_status(args) -> int:
    """Show Obsidian vault sync status and recent pipeline writes."""
    import os
    from pathlib import Path
    from datetime import datetime, timezone

    VAULT_ROOT = Path(os.environ.get("OLP_XDV_VAULT", r"C:\Users\Motunrayo\Documents\OLP_XDV_Vault"))
    HANDOFFS_DIR = VAULT_ROOT / "Pipeline Runs" / "Handoffs"
    STAGE_DIR = VAULT_ROOT / "Pipeline Runs" / "Stages"

    if args.json:
        data = {
            "vault_root": str(VAULT_ROOT),
            "handoffs_dir": str(HANDOFFS_DIR),
            "stage_dir": str(STAGE_DIR),
            "handoffs_dir_exists": HANDOFFS_DIR.exists(),
            "stage_dir_exists": STAGE_DIR.exists(),
        }
        if HANDOFFS_DIR.exists():
            handoff_files = sorted(HANDOFFS_DIR.glob("*.json"), reverse=True)
            data["recent_handoffs"] = [f.name for f in handoff_files[:10]]
            data["total_handoffs"] = len(handoff_files)
        if STAGE_DIR.exists():
            stage_files = sorted(STAGE_DIR.glob("*.json"), reverse=True)
            data["recent_stages"] = [f.name for f in stage_files[:10]]
            data["total_stages"] = len(stage_files)
        print_json(success(data))
    else:
        print_text(f"=== OBSIDIAN VAULT STATUS ===")
        print_text(f"Vault root: {VAULT_ROOT}")
        print_text(f"  Exists: {VAULT_ROOT.exists()}")
        print_text(f"")
        print_text(f"Handoffs dir: {HANDOFFS_DIR}")
        print_text(f"  Exists: {HANDOFFS_DIR.exists()}")
        if HANDOFFS_DIR.exists():
            handoff_files = sorted(HANDOFFS_DIR.glob("*.json"), reverse=True)
            print_text(f"  Total files: {len(handoff_files)}")
            if handoff_files:
                print_text(f"  Recent:")
                for f in handoff_files[:5]:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    print_text(f"    {f.name} ({mtime.isoformat()})")
        print_text(f"")
        print_text(f"Stages dir: {STAGE_DIR}")
        print_text(f"  Exists: {STAGE_DIR.exists()}")
        if STAGE_DIR.exists():
            stage_files = sorted(STAGE_DIR.glob("*.json"), reverse=True)
            print_text(f"  Total files: {len(stage_files)}")
            if stage_files:
                print_text(f"  Recent:")
                for f in stage_files[:5]:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    print_text(f"    {f.name} ({mtime.isoformat()})")
    return 0


def cmd_schema(args) -> int:
    """JSON-Schema tool definitions for agent tool-loading."""
    # Mirrors sports-skills cli.py _generate_schema pattern
    schema = {
        "name": "olp-xdv",
        "description": "OLP XDV read-only query surface for brain, CLV ledger, board, and league audit. Phase 3 live (2026-08-11) — read-only, capital authority is the Architect's.",
        "commands": [
            {
                "name": "stats",
                "description": "Brain overview (CLV by market/league/tier, gate, telemetry, outcomes, produced bets, last run)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                        "brain": {"type": "string", "description": "Override brain DB path"},
                        "phase": {"type": "string", "description": "Phase filter (default: phase2_paper)"},
                        "limit": {"type": "integer", "description": "Limit for produced bets (default: 30)"},
                    },
                },
            },
            {
                "name": "lookup",
                "description": "What did we predict for a team/fixture",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Team name, fixture, or date to look up"},
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                        "brain": {"type": "string", "description": "Override brain DB path"},
                        "limit": {"type": "integer", "description": "Max rows to return (default: 100)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "board",
                "description": "Produced board JSON for a date (default: latest)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: latest)"},
                        "raw": {"type": "boolean", "description": "Raw board file instead of published"},
                        "published": {"type": "boolean", "description": "Published/client-trimmed board (default)"},
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                    },
                },
            },
            {
                "name": "clv",
                "description": "CLV breakdown by market/league/tier",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "by": {"type": "string", "enum": ["market", "league", "pool"], "description": "Group by (default: market)"},
                        "phase": {"type": "string", "description": "Phase filter (default: phase2_paper)"},
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                        "brain": {"type": "string", "description": "Override brain DB path"},
                    },
                },
            },
            {
                "name": "gate",
                "description": "Phase-3 gate status + road-to-gate",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase": {"type": "string", "description": "Phase filter (default: phase2_paper)"},
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                        "brain": {"type": "string", "description": "Override brain DB path"},
                    },
                },
            },
            {
                "name": "audit",
                "description": "League coverage audit (READY/BLOCKED per league)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "league": {"type": "string", "description": "Specific league to audit (default: all whitelisted)"},
                        "no_odds": {"type": "boolean", "description": "Skip odds check (faster)"},
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                    },
                },
            },
            {
                "name": "leagues",
                "description": "Whitelisted leagues + tier",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json": {"type": "boolean", "description": "Output structured JSON"},
                    },
                },
            },
            {
                "name": "schema",
                "description": "JSON-Schema tool definitions for agent tool-loading",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json": {"type": "boolean", "description": "Output structured JSON (always true for schema)"},
                    },
                },
            },
        ],
    }
    print_json(success(schema))
    return 0


def _build_common(parser: argparse.ArgumentParser) -> None:
    """Attach the global flags to a parser (main or a subparser parent).

    These are added to every subparser via `parents=` so they work AFTER the
    command (e.g. `stats --json`), matching the sports-skills convention.
    """
    parser.add_argument("--json", action="store_true", help="Structured JSON output")
    parser.add_argument("--brain", type=str, help="Override brain DB path")
    parser.add_argument("--phase", type=str, default="phase2_paper",
                        help="Phase filter (default: phase2_paper)")
    parser.add_argument("--limit", type=int, default=100, help="Row limit (default: 100)")
    parser.add_argument("--run-id", type=str, help="Specific pipeline run ID")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _build_common(common)

    parser = argparse.ArgumentParser(
        prog="agent_cli",
        description="OLP XDV Agent CLI — read-only query surface for brain, CLV, board, audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  stats          Brain overview (CLV by market/league/tier, gate, telemetry, outcomes, produced bets, last run)
  lookup <query> What did we predict for a team/fixture
  board [--date D] [--raw|--published]  Produced board JSON for a date (default: latest)
  clv [--by market|league|tier] [--phase P]  CLV breakdown
  gate           Phase-3 gate status + road-to-gate
  audit [--no-odds] [--league L]  League coverage audit (READY/BLOCKED per league)
  leagues        Whitelisted leagues + tier
  pipeline-status  Show pipeline run status from Obsidian vault
  vault-status  Show Obsidian vault sync status and recent writes
  schema         JSON-Schema tool definitions for agent tool-loading

Global options (usable after any command):
  --json         Structured JSON output (envelope: {"status": true, "data": ..., "message": ""})
  --brain PATH   Override brain DB path (default: brain/store.DEFAULT_BRAIN_PATH)
  --phase PHASE  Phase filter for CLV/gate (default: phase2_paper)
  --limit N      Row limit for predictions/produced bets (default: 100)
  --run-id ID    Specific pipeline run ID (for pipeline-status)

Examples:
  py -3.12 agent_cli.py stats --json
  py -3.12 agent_cli.py lookup "Fenerbahçe" --json
  py -3.12 agent_cli.py board --date 2026-01-15 --raw --json
  py -3.12 agent_cli.py clv --by league --phase phase2_paper --json
  py -3.12 agent_cli.py gate --json
  py -3.12 agent_cli.py audit --no-odds --league "Danish Superliga" --json
  py -3.12 agent_cli.py leagues --json
  py -3.12 agent_cli.py pipeline-status --json
  py -3.12 agent_cli.py vault-status --json
  py -3.12 agent_cli.py schema --json
""",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # stats
    p_stats = subparsers.add_parser("stats", help="Brain overview", parents=[common])
    p_stats.set_defaults(func=cmd_stats)

    # lookup
    p_lookup = subparsers.add_parser("lookup", help="What did we predict for a team/fixture",
                                     parents=[common])
    p_lookup.add_argument("query", type=str, help="Team name, fixture, or date")
    p_lookup.set_defaults(func=cmd_lookup)

    # board
    p_board = subparsers.add_parser("board", help="Produced board JSON for a date", parents=[common])
    p_board.add_argument("--date", type=str, help="Date in YYYY-MM-DD (default: latest)")
    p_board.add_argument("--raw", action="store_true", help="Raw board file")
    p_board.add_argument("--published", action="store_true",
                         help="Published/client-trimmed board (default)")
    p_board.set_defaults(func=cmd_board)

    # clv
    p_clv = subparsers.add_parser("clv", help="CLV breakdown", parents=[common])
    p_clv.add_argument("--by", type=str, choices=["market", "league", "pool"], default="market",
                       help="Group by (default: market)")
    p_clv.set_defaults(func=cmd_clv)

    # gate
    p_gate = subparsers.add_parser("gate", help="Phase-3 gate status", parents=[common])
    p_gate.set_defaults(func=cmd_gate)

    # audit
    p_audit = subparsers.add_parser("audit", help="League coverage audit", parents=[common])
    p_audit.add_argument("--league", type=str, help="Specific league to audit")
    p_audit.add_argument("--no-odds", action="store_true", help="Skip odds check")
    p_audit.set_defaults(func=cmd_audit)

    # leagues
    p_leagues = subparsers.add_parser("leagues", help="Whitelisted leagues + tier", parents=[common])
    p_leagues.set_defaults(func=cmd_leagues)

    # livescores
    p_livescores = subparsers.add_parser("livescores", help="Live in-play scores for a league", parents=[common])
    p_livescores.add_argument("--league", type=str, help="Specific league (default: all whitelisted)")
    p_livescores.add_argument("--day", type=str, help="Day in YYYYMMDD format (default: today)")
    p_livescores.set_defaults(func=cmd_livescores)

    # pipeline-status
    p_pipeline = subparsers.add_parser("pipeline-status", help="Show pipeline run status from Obsidian vault", parents=[common])
    p_pipeline.set_defaults(func=cmd_pipeline_status)

    # vault-status
    p_vault = subparsers.add_parser("vault-status", help="Show Obsidian vault sync status and recent writes", parents=[common])
    p_vault.set_defaults(func=cmd_vault_status)

    # schema
    p_schema = subparsers.add_parser("schema", help="JSON-Schema tool definitions", parents=[common])
    p_schema.set_defaults(func=cmd_schema)

    return parser


def _json_requested() -> bool:
    """Whether --json appears in the raw argv (used when parse_args itself failed)."""
    return "--json" in sys.argv


def main() -> int:
    try:
        parser = build_parser()
        args = parser.parse_args()

        # Ensure we have a handler
        if not hasattr(args, "func"):
            parser.print_help()
            return 1

        return args.func(args)
    except KeyboardInterrupt:
        print_text("Interrupted")
        return 130
    except SystemExit:
        # argparse exits (e.g. missing command or bad flag) — surface as exit 2
        return 2
    except Exception as e:
        # Graceful error — no traceback (HR35: never fabricate, but we can
        # report the underlying error honestly)
        if _json_requested():
            print_json(error(f"{type(e).__name__}: {e}"))
        else:
            print_text(f"ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
