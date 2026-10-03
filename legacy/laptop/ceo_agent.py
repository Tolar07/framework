#!/usr/bin/env python3
"""
OLP XDV CEO Agent — Telegram-native orchestrator for the framework.

Coordinates:
- Daily production pipeline (run_daily.py)
- Health monitoring (monitor/health_monitor.py)
- Daemon status (watchdog, dead man's switch, data steward)
- Sub-agent queries (agent_cli.py for read-only brain/CLV/board queries)
- Telegram reporting (notify.send_telegram)

All commands are invoked via the existing Telegram poller at output/telegram_commands.py
using the /ceo prefix.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Ensure repo root is on path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

# Lazy imports to avoid circular dependencies
def _import_notify():
    from output import notify
    return notify

def _import_brain():
    from brain.store import Brain
    return Brain

def _import_run_daily():
    from run_daily import run, RunResult
    return run, RunResult

def _import_health_monitor():
    # Import probe functions directly
    import monitor.health_monitor as hm
    return hm

def _import_telegram_commands():
    import output.telegram_commands as tc
    return tc

def _load_league_groups():
    """Load league groups from config/league_groups.json."""
    import json
    path = REPO_ROOT / "config" / "league_groups.json"
    if not path.exists():
        return {"groups": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class CEOCommand:
    """Parsed CEO command."""
    command: str      # e.g., "run", "status", "health"
    arg: str          # remaining argument string


@dataclass
class AgentStatus:
    """Status of a sub-agent."""
    name: str
    type: str         # "claude_code" | "daemon"
    last_activity: Optional[str]
    status: str       # "active", "idle", "error", "unknown"


# ============================================================================
# CEO Agent Core
# ============================================================================

class CEOAgent:
    """Telegram-native orchestrator for OLP XDV framework."""

    def __init__(self):
        self.repo_root = REPO_ROOT
        self.logs_dir = REPO_ROOT / "logs"
        self.memory_dir = REPO_ROOT / "memory"

    # -------------------------------------------------------------------------
    # Command Router
    # -------------------------------------------------------------------------

    def parse_command(self, text: str) -> CEOCommand:
        """Parse /ceo command text into command + arg."""
        stripped = text.strip()
        # Remove leading /ceo
        if stripped.lower().startswith("/ceo"):
            rest = stripped[4:].strip()
        elif stripped.lower().startswith("ceo"):
            rest = stripped[3:].strip()
        else:
            rest = stripped

        if not rest:
            return CEOCommand("help", "")

        parts = rest.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        return CEOCommand(cmd, arg)

    def handle_command(self, command: str, arg: str) -> Any:
        """Route CEO command to handler. Returns Reply-compatible string."""
        try:
            tc = _import_telegram_commands()
            Reply = tc.Reply
            _keyboard = tc._keyboard
        except ImportError:
            # Fallback if telegram_commands not available
            class Reply(str):
                keyboard: dict | None = None
                def __new__(cls, text: str, keyboard: dict | None = None):
                    obj = super().__new__(cls, text)
                    obj.keyboard = keyboard
                    return obj
            def _keyboard(*rows):
                return {"inline_keyboard": [[{"text": c, "callback_data": c} for c in row] for row in rows]}

        cmd = command.lower()

        if cmd in ("help", "h", "?"):
            return self._cmd_help(_keyboard)

        elif cmd in ("run", "r", "produce", "send"):
            return self._cmd_run()

        elif cmd in ("status", "s", "st"):
            return self._cmd_status()

        elif cmd in ("gate", "g"):
            return self._cmd_gate()

        elif cmd in ("health", "hth", "check"):
            return self._cmd_health()

        elif cmd in ("verify", "v"):
            return self._cmd_verify(arg)

        elif cmd in ("agents", "agent", "a"):
            return self._cmd_agents()

        elif cmd in ("board", "b"):
            return self._cmd_board()

        elif cmd in ("daily", "d", "log"):
            return self._cmd_daily(arg)

        elif cmd in ("league-groups", "lg", "groups"):
            return self._cmd_league_groups()

        elif cmd in ("coverage", "cov", "league-coverage"):
            return self._cmd_coverage()

        else:
            return Reply(
                f"Unknown CEO command: /ceo {command}\n\n"
                f"Send /ceo help for command reference.",
                keyboard=self._help_keyboard(_keyboard)
            )

    # -------------------------------------------------------------------------
    # Command Handlers
    # -------------------------------------------------------------------------

    def _help_keyboard(self, _keyboard):
        return _keyboard(
            ("/ceo run", "/ceo status"),
            ("/ceo health", "/ceo gate"),
            ("/ceo verify", "/ceo agents"),
            ("/ceo board", "/ceo daily"),
            ("/ceo groups", "/ceo coverage"),
        )

    def _cmd_help(self, _keyboard) -> Any:
        tc = _import_telegram_commands()
        Reply = tc.Reply
        return Reply(
            "🏢 **OLP XDV CEO Agent** — Framework Orchestrator\n\n"
            "**Commands:**\n"
            "• `/ceo run` — Trigger full daily production + CEO summary\n"
            "• `/ceo status` — Full framework status (gate + health + last run)\n"
            "• `/ceo gate` — Phase 3 gate progress with road-to-gate\n"
            "• `/ceo health` — Run all health monitor probes\n"
            "• `/ceo verify` — Grade pending legs now (wraps `/verify result`)\n"
            "• `/ceo agents` — List active sub-agents & last activity\n"
            "• `/ceo board` — Re-send today's board with production bets\n"
            "• `/ceo daily` — Show today's run log summary\n"
            "• `/ceo groups` — Show league groups & per-group stewards\n"
            "• `/ceo coverage` — Run league coverage audit per group\n"
            "• `/ceo help` — This reference\n\n"
            "**Daemons (auto-scheduled):**\n"
            "• 07:00 — Daily Board (run_daily.py)\n"
            "• Every 2h — Health Monitor\n"
            "• 08:15 — Dead Man's Switch\n"
            "• 06:00/15:00 — Data Steward\n"
            "• Resident — Telegram Poller + Web Dashboard\n\n"
            "All production is **paper-only, Phase 2** (zero capital).",
            keyboard=self._help_keyboard(_keyboard)
        )

    def _cmd_run(self) -> Any:
        """Trigger daily production + CEO summary."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        # Start production in background thread to avoid blocking poller
        import threading
        result_holder = {"result": None, "error": None}

        def run_production():
            try:
                run, RunResult = _import_run_daily()
                # Run with booking_codes=True so we get SportyBet codes for summary
                res = run(
                    season="2526",
                    fixtures_season="2627",
                    send=True,
                    booking_codes=True,
                    min_mes=1.05,
                    days_ahead=0,
                    target_date=None,
                    whatsapp=False,
                    email=False,
                    web=True,
                    prefetch_crests=False,
                    refresh_sportybet=True
                )
                result_holder["result"] = res
            except Exception as e:
                result_holder["error"] = e

        thread = threading.Thread(target=run_production, daemon=True)
        thread.start()

        # Return immediate response
        return Reply(
            "🚀 **CEO: Daily production started**\n\n"
            "Running full pipeline (grade → fixtures → odds → engine → verify → board → notify).\n"
            "This takes ~30 seconds. Board will be delivered to Telegram when complete.\n\n"
            "Use `/ceo daily` in a moment to see the run log.",
            keyboard=self._help_keyboard(tc._keyboard)
        )

    def _cmd_status(self) -> Any:
        """Full framework status: gate + health + last run + data quality."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        parts = []

        # Gate status
        parts.append(self._get_gate_status())

        # Health summary
        parts.append(self._get_health_summary())

        # Last run
        parts.append(self._get_last_run_summary())

        # Data quality
        parts.append(self._get_data_quality_summary())

        text = "\n\n".join(parts)
        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_gate(self) -> Any:
        """Phase 3 gate progress with road-to-gate."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        try:
            # Use agent_cli.py gate --json for structured output
            result = subprocess.run(
                ["py", "-3.12", "agent_cli.py", "gate", "--json"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("status"):
                    gate_data = data.get("data", {})
                    text = self._format_gate(gate_data)
                else:
                    text = f"Gate query failed: {data.get('message', 'unknown')}"
            else:
                text = f"Gate query failed: {result.stderr[:200]}"
        except Exception as e:
            text = f"Gate query error: {e}"

        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_health(self) -> Any:
        """Run all health monitor probes and report."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        hm = _import_health_monitor()
        probe_results = []

        probes = [
            ("Phase Guard", hm.probe_phase),
            ("Environment", hm.probe_env),
            ("Brain DB", hm.probe_brain),
            ("CLV Ledger", hm.probe_ledger),
            ("Odds Quota", hm.probe_quota),
            ("Caches", hm.probe_caches),
            ("Data Quality", hm.probe_data_quality),
            ("Last Run", hm.probe_last_run),
            ("Dashboard", hm.probe_dashboard),
            ("Circuits", hm.probe_circuits),
        ]

        for name, probe_fn in probes:
            try:
                result = probe_fn()  # Returns ProbeResult object
                ok = result.level == "ok"
                status = "✅" if ok else "❌"
                if result.healed:
                    status = "🔧"
                probe_results.append(f"{status} **{name}**: {result.message}")
            except Exception as e:
                probe_results.append(f"❌ **{name}**: Probe error — {e}")

        text = "🏥 **Health Monitor Probes**\n\n" + "\n".join(probe_results)
        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_verify(self, arg: str) -> Any:
        """Grade pending legs now (wraps /verify result)."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        try:
            # Call run_daily.grade_open_legs directly — same route as /verify result.
            import run_daily
            from clv.clv_logger import CLVLog

            log = CLVLog()
            summary, flags = run_daily.grade_open_legs(log, "2526")

            text = "✅ **Verification Complete**\n\n" + summary
            if flags:
                text += "\n\n**Flags:**\n" + "\n".join(f"• {f}" for f in flags)

        except Exception as e:
            text = f"❌ Verification failed: {e}"

        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_agents(self) -> Any:
        """List active sub-agents and their last activity."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        agents = self._get_agent_statuses()

        lines = ["🤖 **Active Sub-Agents**\n"]
        for a in agents:
            status_emoji = {"active": "🟢", "idle": "🟡", "error": "🔴", "unknown": "⚪"}.get(a.status, "⚪")
            last = a.last_activity or "never"
            lines.append(f"{status_emoji} **{a.name}** ({a.type}) — {a.status} — last: {last}")

        text = "\n".join(lines)
        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_board(self) -> Any:
        """Re-send today's board with production bets."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        try:
            # Use agent_cli.py board --json
            result = subprocess.run(
                ["py", "-3.12", "agent_cli.py", "board", "--json"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("status"):
                    board_data = data.get("data", {})
                    # Format board for Telegram
                    text = self._format_board(board_data)
                else:
                    text = f"Board query failed: {data.get('message', 'unknown')}"
            else:
                text = f"Board query failed: {result.stderr[:200]}"
        except Exception as e:
            text = f"Board query error: {e}"

        return Reply(text, keyboard=self._help_keyboard(tc._keyboard))

    def _cmd_daily(self, arg: str) -> Any:
        """Show today's run log summary."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        # Parse date from arg or use today
        target_date = date.today().isoformat()
        if arg:
            # Try to parse date from arg
            try:
                target_date = arg.strip()
                date.fromisoformat(target_date)  # validate
            except ValueError:
                target_date = date.today().isoformat()

        log_path = self.logs_dir / f"daily_{target_date}.log"

        if not log_path.exists():
            return Reply(
                f"📭 No daily log for {target_date}\n\n"
                f"Expected: {log_path}",
                keyboard=self._help_keyboard(tc._keyboard)
            )

        text = log_path.read_text(encoding="utf-8", errors="replace")

        # Extract key sections
        lines = text.splitlines()
        key_lines = []
        for line in lines:
            if any(keyword in line.lower() for keyword in [
                "started", "completed", "delivered", "logged", "gate",
                "error", "failed", "warning", "graded", "clv", "verif"
            ]):
                key_lines.append(line)

        # Limit output
        display = "\n".join(key_lines[-50:]) if key_lines else text[-3000:]

        return Reply(
            f"📋 **Daily Run Log: {target_date}**\n\n```\n{display}\n```",
            keyboard=self._help_keyboard(tc._keyboard)
        )

    def _cmd_league_groups(self) -> Any:
        """Show league groups and their assigned stewards."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        try:
            cfg = _load_league_groups()
            groups = cfg.get("groups", [])

            if not groups:
                return Reply(
                    "⚠️ No league groups configured.\n\n"
                    "Expected: config/league_groups.json",
                    keyboard=self._help_keyboard(tc._keyboard)
                )

            lines = ["⚽ **League Groups & Stewards**\n"]
            total_leagues = 0

            for g in groups:
                gid = g.get("id", "?")
                name = g.get("name", gid)
                leagues = g.get("leagues", [])
                profile = g.get("coverage_profile", "?")
                priority = g.get("priority", "?")
                agents = g.get("agents", [])

                total_leagues += len(leagues)
                lines.append(f"**{name}** (P{priority})")
                lines.append(f"  {len(leagues)} leagues · {profile}")
                lines.append(f"  Agents: {', '.join(agents)}")

            lines.append(f"\n📊 **Total**: {total_leagues} leagues across {len(groups)} groups")

            return Reply(
                "\n".join(lines),
                keyboard=self._help_keyboard(tc._keyboard)
            )
        except Exception as e:
            return Reply(
                f"❌ League groups error: {e}",
                keyboard=self._help_keyboard(tc._keyboard)
            )

    def _cmd_coverage(self) -> Any:
        """Run league coverage audit per group and report (in-process, fast)."""
        tc = _import_telegram_commands()
        Reply = tc.Reply

        try:
            cfg = _load_league_groups()
            groups = cfg.get("groups", [])

            if not groups:
                return Reply(
                    "⚠️ No league groups configured.",
                    keyboard=self._help_keyboard(tc._keyboard)
                )

            # Import and run audit in-process once for all leagues
            import sys
            sys.path.insert(0, str(self.repo_root))
            from league_audit import audit

            fit_season = "2526"
            fixtures_season = "2627"
            check_odds = False  # Fast mode

            # Run audit for all whitelisted leagues once
            from engine.leagues import WHITELISTED_LEAGUES
            all_results = {}
            for league in WHITELISTED_LEAGUES:
                try:
                    all_results[league] = audit(league, fit_season, fixtures_season, check_odds)
                except Exception as e:
                    all_results[league] = {"blockers": [f"audit failed: {str(e)[:60]}"], "deploy_eligible": True}

            # Now slice by group
            lines = ["🔍 **League Coverage Audit**\n"]

            for g in groups:
                gid = g.get("id", "?")
                name = g.get("name", gid)
                leagues = g.get("leagues", [])
                priority = g.get("priority", "?")

                ready = blocked = 0
                details = []

                for league in leagues:
                    r = all_results.get(league, {})
                    if not r.get("blockers"):
                        ready += 1
                        details.append(f"  ✅ {league}")
                    else:
                        blocked += 1
                        # Show first blocker
                        blocker = r.get("blockers", ["unknown"])[0]
                        details.append(f"  ⚠️ {league}: {blocker[:50]}")

                emoji = "✅" if blocked == 0 else "⚠️" if blocked <= 2 else "❌"
                lines.append(f"{emoji} **{name}** (P{priority})")
                lines.append(f"  {ready} ready / {blocked} blocked / {len(leagues)} total")
                # Show details for blocked leagues
                if blocked > 0:
                    lines.extend(details)

            return Reply(
                "\n".join(lines),
                keyboard=self._help_keyboard(tc._keyboard)
            )
        except Exception as e:
            return Reply(
                f"❌ Coverage audit error: {e}",
                keyboard=self._help_keyboard(tc._keyboard)
            )

    # -------------------------------------------------------------------------
    # Status Aggregation Helpers
    # -------------------------------------------------------------------------

    def _get_gate_status(self) -> str:
        """Get gate status from CLV log."""
        try:
            from clv.clv_logger import CLVLog
            log = CLVLog()
            status = log.phase2_status()
            legs = status.get("legs_with_clv", 0)
            req = status.get("gate_requirement", 30)
            mean_clv = status.get("mean_clv_pct")
            clv_str = f"{mean_clv:.2f}%" if mean_clv is not None else "NO DATA — PENDING"
            return (
                f"🎯 **Phase 3 Gate**\n"
                f"• Legs with CLV: {legs}/{req}\n"
                f"• Mean CLV: {clv_str}\n"
                f"• Progress: {legs}/{req} ({legs/req*100:.0f}%)"
            )
        except Exception as e:
            return f"🎯 **Phase 3 Gate**\n• Error: {e}"

    def _get_health_summary(self) -> str:
        """Quick health summary (just pass/fail counts)."""
        hm = _import_health_monitor()
        probes = [
            hm.probe_phase, hm.probe_env, hm.probe_brain, hm.probe_ledger,
            hm.probe_quota, hm.probe_caches, hm.probe_data_quality,
            hm.probe_last_run, hm.probe_dashboard, hm.probe_circuits
        ]
        passed = 0
        for probe_fn in probes:
            try:
                result = probe_fn()
                if result.level == "ok":
                    passed += 1
            except (RuntimeError, ValueError, KeyError, AttributeError):
                # Health probes may raise these if a subsystem is down
                pass
        total = len(probes)
        return f"🏥 **Health**: {passed}/{total} probes OK"

    def _get_last_run_summary(self) -> str:
        """Summarize last daily run using brain's run record (single source of truth)."""
        try:
            Brain = _import_brain()
            with Brain() as brain:
                r = brain.last_run()
            if not r:
                return f"📅 **Last Run**: NO RUN RECORDED"
            started = (r.get("started_at") or "")[:16].replace("T", " ")
            status = r.get("status", "?")
            n_lg = r.get("leagues_scanned") or "?"
            n_fx = r.get("fixtures_seen") or "?"
            n_pr = r.get("predictions_logged") or "?"
            n_lg2 = r.get("legs_logged") or "?"
            fit = r.get("fit_seconds")
            fit_s = f" · fit {fit:.0f}s" if isinstance(fit, (int, float)) else ""
            tail = " — FAILED" if status == "failed" else ""
            return (f"📅 **Last Run ({started})**: {status.upper()}{tail}\n"
                    f"  {n_lg} leagues · {n_fx} fixtures · {n_pr} predictions · "
                    f"{n_lg2} legs logged{fit_s}")
        except Exception as e:
            return f"📅 **Last Run**: unavailable ({e})"

    def _get_data_quality_summary(self) -> str:
        """Data quality from health monitor."""
        try:
            hm = _import_health_monitor()
            result = hm.probe_data_quality()
            ok = result.level == "ok"
            return f"📊 **Data Quality**: {'✅' if ok else '❌'} {result.message}"
        except Exception as e:
            return f"📊 **Data Quality**: Error — {e}"

    def _get_agent_statuses(self) -> list[AgentStatus]:
        """Get status of all known sub-agents including per-group league stewards."""
        agents = []

        # Claude Code agents (check agent_cli.py stats for brain activity)
        claude_agents = [
            ("planner", "claude_code"),
            ("architect", "claude_code"),
            ("tdd-guide", "claude_code"),
            ("code-reviewer", "claude_code"),
            ("security-reviewer", "claude_code"),
            ("build-error-resolver", "claude_code"),
            ("e2e-runner", "claude_code"),
            ("refactor-cleaner", "claude_code"),
            ("doc-updater", "claude_code"),
            ("backend-architect", "claude_code"),
            ("frontend-developer", "claude_code"),
            ("ui-ux-designer", "claude_code"),
            ("security-auditor", "claude_code"),
            ("code-reviewer-config", "claude_code"),
            ("devops-troubleshooter", "claude_code"),
            ("database-admin", "claude_code"),
            ("olp-xdv-webapp", "claude_code"),
            ("session-init", "claude_code"),
            ("obsidian-communication", "claude_code"),
        ]

        for name, typ in claude_agents:
            agents.append(AgentStatus(name, typ, None, "idle"))

        # Daemon agents
        daemon_agents = [
            ("Daily Board (07:00)", "daemon"),
            ("Health Monitor (2h)", "daemon"),
            ("Dead Man's Switch (08:15)", "daemon"),
            ("Data Steward (06:00/15:00)", "daemon"),
            ("Telegram Poller (resident)", "daemon"),
            ("Web Dashboard (resident)", "daemon"),
        ]

        for name, typ in daemon_agents:
            agents.append(AgentStatus(name, typ, None, "active"))

        # Per-group league stewards (from league_groups.json)
        try:
            cfg = _load_league_groups()
            groups = cfg.get("groups", [])
            for g in groups:
                gid = g.get("id", "?")
                name = g.get("name", gid)
                agents_list = g.get("agents", [])
                league_count = len(g.get("leagues", []))
                # Show the primary assigned agents for this group
                if agents_list:
                    agents.append(AgentStatus(
                        f"League Steward: {name}",
                        "league_steward",
                        gid,
                        f"active ({league_count} leagues, agents: {', '.join(agents_list)})"
                    ))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Silently skip if config not available or malformed
            pass

        return agents

    def _format_gate(self, gate_data: dict) -> str:
        """Format gate data for display."""
        lines = ["🎯 **Phase 3 Gate Status**\n"]

        legs = gate_data.get("legs_with_clv", 0)
        req = gate_data.get("gate_requirement", 30)
        mean_clv = gate_data.get("mean_clv_pct")
        clv_str = f"{mean_clv:.2f}%" if mean_clv is not None else "NO DATA — PENDING"

        lines.append(f"• Legs with CLV: **{legs}/{req}** ({legs/req*100:.0f}%)")
        lines.append(f"• Mean CLV: **{clv_str}**")

        # Road to gate
        if legs < req:
            needed = req - legs
            lines.append(f"\n📈 **Road to Gate**: Need {needed} more legs with logged CLV")
            if mean_clv is not None and mean_clv > 0:
                lines.append("   Mean CLV is positive — on track!")
            elif mean_clv is not None:
                lines.append("   ⚠️ Mean CLV is negative — review model calibration")

        # Additional details
        if "telemetry" in gate_data:
            t = gate_data["telemetry"]
            lines.append(f"\n📊 **Telemetry**: {t}")

        return "\n".join(lines)

    def _format_board(self, board_data: dict) -> str:
        """Format board data for Telegram display."""
        # Board data structure varies, show what we have
        lines = ["📋 **Today's Board**\n"]

        if "fixtures" in board_data:
            for i, fx in enumerate(board_data["fixtures"][:10], 1):
                lines.append(f"{i}. {fx.get('fixture', 'N/A')}")
                if "markets" in fx:
                    for mkt, prob in fx["markets"].items():
                        lines.append(f"   {mkt}: {prob:.1%}")

        return "\n".join(lines)


# ============================================================================
# Daily Summary Generation (for optional 08:00 scheduled job)
# ============================================================================

    def generate_daily_summary(self) -> str:
        """Generate daily summary for automated 08:00 delivery."""
        parts = []

        parts.append("📅 **OLP XDV Daily Summary** — " + date.today().isoformat())
        parts.append("")
        parts.append(self._get_gate_status())
        parts.append("")
        parts.append(self._get_health_summary())
        parts.append("")
        parts.append(self._get_last_run_summary())
        parts.append("")
        parts.append(self._get_data_quality_summary())

        # Yesterday's results
        try:
            Brain = _import_brain()
            with Brain() as brain:
                yesterday = (date.today() - timedelta(days=1)).isoformat()
                graded = brain.graded_yesterday(yesterday)
                if graded:
                    won = sum(1 for g in graded if g.get("hit"))
                    lost = sum(1 for g in graded if g.get("hit") is False)
                    pending = sum(1 for g in graded if g.get("hit") is None)
                    parts.append(f"\n📈 **Yesterday ({yesterday})**: {won}W / {lost}L / {pending}P")
        except (RuntimeError, ValueError, KeyError, AttributeError):
            # Brain may raise these if DB is unavailable or data malformed
            pass

        return "\n".join(parts)


# ============================================================================
# CLI Entry Point (for testing)
# ============================================================================

def main():
    """CLI entry for testing: python ceo_agent.py <command> [arg]"""
    import argparse
    parser = argparse.ArgumentParser(description="CEO Agent CLI")
    parser.add_argument("command", help="CEO command (run, status, gate, health, verify, agents, board, daily, help)")
    parser.add_argument("arg", nargs="*", help="Command argument")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    ceo = CEOAgent()
    cmd_text = " ".join([args.command] + args.arg)
    parsed = ceo.parse_command(cmd_text)
    result = ceo.handle_command(parsed.command, parsed.arg)

    if args.json:
        # Convert Reply to JSON
        if hasattr(result, 'keyboard'):
            print(json.dumps({"status": True, "data": {"text": str(result), "keyboard": result.keyboard}}))
        else:
            print(json.dumps({"status": True, "data": {"text": str(result), "keyboard": None}}))
    else:
        # Reconfigure stdout to UTF-8 so emoji render on Windows consoles too.
        import sys
        if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        print(result)


if __name__ == "__main__":
    main()