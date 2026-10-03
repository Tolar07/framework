"""League coverage monitor — per-group data/odds availability tracker.

Runs a quota-free (``--no-odds``) league audit, slices results by the groups
in ``config/league_groups.json``, and alerts on **regressions** — a league
that was READY at the last check and is now BLOCKED.  Like the health monitor,
it never raises: a failure is reported, not crashed on.

USAGE
    python monitor/league_coverage_monitor.py                  # full check + alert
    python monitor/league_coverage_monitor.py --no-alert        # check, no Telegram
    python monitor/league_coverage_monitor.py --state <path>    # custom state file
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# cp1252-safe stdout (Windows console can't encode Divisió, Urvalsdeild, Štip, etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

from engine.leagues import WHITELISTED_LEAGUES  # noqa: E402
from league_audit import audit  # noqa: E402

STATE_PATH = ROOT / "output" / "league_coverage_state.json"
FIT_SEASON = "2526"
FIXTURES_SEASON = "2627"


# ---------------------------------------------------------------------------
# State persistence (same pattern as health_monitor)
# ---------------------------------------------------------------------------

def _load_state(path: Path) -> dict:
    """Load previous coverage state for regression detection."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict, path: Path) -> None:
    """Persist current coverage state for next run's regression check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Core audit
# ---------------------------------------------------------------------------

def run_audit() -> dict[str, dict]:
    """Run the in-process league audit (no odds, quota-free) for all
    whitelisted leagues.  Returns ``{league_name: audit_row}``."""
    results: dict[str, dict] = {}
    for league in WHITELISTED_LEAGUES:
        try:
            results[league] = audit(
                league, FIT_SEASON, FIXTURES_SEASON, check_odds=False
            )
        except Exception as e:
            results[league] = {
                "league": league,
                "blockers": [f"audit crashed: {str(e)[:60]}"],
                "deploy_eligible": league in WHITELISTED_LEAGUES,
            }
    return results


def _slice_by_group(
    results: dict[str, dict], groups: list[dict]
) -> list[dict]:
    """Slice audit results by league group for summary reporting."""
    group_summaries: list[dict] = []
    for g in groups:
        gid = g.get("id", "?")
        name = g.get("name", gid)
        leagues = g.get("leagues", [])
        priority = g.get("priority", "?")

        ready = blocked = 0
        blocked_leagues: list[dict] = []
        for league in leagues:
            r = results.get(league, {})
            if not r.get("blockers"):
                ready += 1
            else:
                blocked += 1
                blocked_leagues.append({
                    "league": league,
                    "blockers": r.get("blockers", []),
                })

        group_summaries.append({
            "group_id": gid,
            "group_name": name,
            "priority": priority,
            "ready": ready,
            "blocked": blocked,
            "total": len(leagues),
            "blocked_leagues": blocked_leagues,
        })
    return group_summaries


def _detect_regressions(
    current: dict[str, dict], previous: dict[str, dict]
) -> list[str]:
    """Return league names that were READY before but are BLOCKED now."""
    regressions: list[str] = []
    for league, row in current.items():
        was_ready = not previous.get(league, {}).get("blockers")
        is_blocked = bool(row.get("blockers"))
        if was_ready and is_blocked:
            regressions.append(league)
    return regressions


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

def _format_alert(
    summaries: list[dict],
    regressions: list[str],
    total_ready: int,
    total_leagues: int,
) -> str:
    """Format the coverage report for Telegram."""
    lines = ["🔍 **League Coverage Monitor**\n"]

    # Overall
    pct = total_ready / total_leagues * 100 if total_leagues else 0
    lines.append(f"Overall: {total_ready}/{total_leagues} READY ({pct:.0f}%)")

    # Regressions
    if regressions:
        lines.append(f"\n⚠️ **REGRESSIONS** ({len(regressions)}):")
        for r in regressions:
            lines.append(f"  • {r}")
    else:
        lines.append("\n✅ No regressions since last check")

    # Per-group summary (show blocked count only)
    lines.append("\n**Per Group:**")
    for g in summaries:
        emoji = "✅" if g["blocked"] == 0 else "⚠️" if g["blocked"] <= 2 else "❌"
        lines.append(
            f"  {emoji} {g['group_name']} (P{g['priority']}): "
            f"{g['ready']}/{g['total']} ready"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check(state_path: Path | None = None, alert: bool = True) -> dict:
    """Run a full coverage check.  Returns a summary dict (for callers
    like the CEO agent).  Never raises."""
    state_path = state_path or STATE_PATH

    # Load groups
    groups_path = ROOT / "config" / "league_groups.json"
    if not groups_path.exists():
        return {"error": "config/league_groups.json not found"}
    groups = json.loads(groups_path.read_text(encoding="utf-8")).get("groups", [])

    # Run audit
    results = run_audit()

    # Slice by group
    summaries = _slice_by_group(results, groups)

    # Detect regressions
    previous = _load_state(state_path)
    regressions = _detect_regressions(results, previous)

    # Totals
    total_ready = sum(1 for r in results.values() if not r.get("blockers"))
    total_leagues = len(results)

    # Save state (store just ready/blocked per league, not full audit)
    state_out = {
        league: {"ready": not r.get("blockers"), "blockers": r.get("blockers", [])}
        for league, r in results.items()
    }
    _save_state(state_out, state_path)

    # Build summary
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_ready": total_ready,
        "total_leagues": total_leagues,
        "regressions": regressions,
        "groups": summaries,
    }

    # Alert
    if alert:
        try:
            from output import notify
            text = _format_alert(summaries, regressions, total_ready, total_leagues)
            notify.send_telegram(text)
        except Exception:
            pass  # Best-effort, never crash

    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="League coverage monitor")
    ap.add_argument("--no-alert", action="store_true", help="Skip Telegram alert")
    ap.add_argument("--state", type=str, default=None, help="Custom state file path")
    a = ap.parse_args()

    state_path = Path(a.state) if a.state else None
    summary = check(state_path=state_path, alert=not a.no_alert)

    if "error" in summary:
        print(f"❌ {summary['error']}")
        return

    # Print summary to stdout
    print(f"League Coverage Monitor — {summary['timestamp']}")
    print(f"  Ready: {summary['total_ready']}/{summary['total_leagues']}")
    if summary["regressions"]:
        print(f"  REGRESSIONS ({len(summary['regressions'])}):")
        for r in summary["regressions"]:
            print(f"    • {r}")
    else:
        print("  No regressions")
    print()
    for g in summary["groups"]:
        emoji = "✅" if g["blocked"] == 0 else "⚠️" if g["blocked"] <= 2 else "❌"
        print(f"  {emoji} {g['group_name']} (P{g['priority']}): "
              f"{g['ready']}/{g['total']} ready, {g['blocked']} blocked")


if __name__ == "__main__":
    main()
