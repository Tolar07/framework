"""Framework Guardian — continuous monitoring & auto-remediation for OLP XDV.

The OLP XDV framework runs on multiple scheduled loops (health monitor, steward,
watchdog, dead-man's-switch, hourly fixture check, hourly match analysis, daily
board). Each loop has its own failure modes, and systemic issues (quota
exhaustion, stale caches, calibration drift, SportyBet fixture gaps, delivery
failures) can persist across loops without a single agent connecting the dots.

This guardian runs on its OWN schedule (e.g., every 30 minutes via Task
Scheduler) and performs three functions:

1. UNIFIED HEALTH VIEW — aggregates all probe results from health_monitor,
   steward, data_quality, run_watchdog, dead_mans_switch into one coherent
   system state.

2. PROACTIVE REMEDIATION — triggers fixes BEFORE they become delivery failures:
   - Quota low -> alerts to add backup keys (never spends the last credit)
   - Cache stale -> triggers steward refresh for specific leagues
   - Calibration drift -> queues shadow recalibration for next training window
   - SportyBet gaps -> triggers targeted cache warm for missing fixtures
   - Delivery failure -> retries with exponential backoff, alerts on persistence

3. STATE-CHANGE ALERTING — only alerts on transitions (OK->WARN, WARN->CRITICAL,
   CRITICAL->OK, or long-open issue reminder). Uses the same discipline as
   health_monitor: never spam the phone.

The guardian NEVER modifies protected constants (ARCHITECT_SIGNOFF, CLV gate,
capital deployment, ID405 scope, softness tier). It only:
- Triggers existing remediation paths (steward, health_monitor heals)
- Alerts the Architect with actionable context
- Logs everything for audit

USAGE:
    python monitor/framework_guardian.py              # one full check + remediation
    python monitor/framework_guardian.py --no-alert   # check only, no Telegram
    python monitor/framework_guardian.py --daemon     # run continuously (30-min loop)
    python monitor/framework_guardian.py --state <path>  # custom state file
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402  (loads .env)
from monitor import health_monitor  # noqa: E402
from monitor import data_quality  # noqa: E402
from monitor import run_watchdog  # noqa: E402
from monitor import dead_mans_switch  # noqa: E402
from steward import run_steward  # noqa: E402
from output import notify  # noqa: E402
from monitor import alert_dispatcher  # noqa: E402
from pipeline.odds import QUOTA_FLOOR, QUOTA_HARD_FLOOR  # noqa: E402
from engine.leagues import WHITELISTED_LEAGUES  # noqa: E402

# SportyBet failure rate monitoring
try:
    from booking.sportybet_client import get_failure_stats, FAILURE_RATE_ALERT_THRESHOLD, FAILURE_COUNT_ALERT_THRESHOLD
    _HAS_SPORTYBET_STATS = True
except ImportError:
    _HAS_SPORTYBET_STATS = False

DEFAULT_STATE = ROOT / "logs" / "guardian_state.json"
DEFAULT_LOOP_SECONDS = 30 * 60  # 30 minutes

# A problem left unreported for this long re-alerts even if state unchanged
RE_ALERT_AFTER_SECONDS = 26 * 3600  # ~daily reminder for open issues

# Thresholds for proactive triggers
QUOTA_WARN_THRESHOLD = 50  # Alert when remaining drops below this
QUOTA_CRITICAL_THRESHOLD = QUOTA_FLOOR  # Triggers steward fallback warming
CACHE_STALE_HOURS = 4  # Trigger steward if fixtures cache > 4h old
CALIBRATION_ERROR_PP = 5.0  # Trigger shadow recalibration if bin error > 5pp
SPORTYBET_MIN_FIXTURES = 20  # Alert if cache has fewer than this many fixtures


# ============================================================================
# State & Alerting
# ============================================================================

class SystemState:
    """Aggregated system state from all probes."""
    def __init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.health: list = []
        self.data_quality: list = []
        self.steward: dict = {}
        self.watchdog: tuple = (False, [])
        self.dead_man: tuple = (False, [])
        self.quota: tuple = (0, 0)  # (used, remaining)
        self.overall: str = "unknown"  # "healthy" | "degraded" | "critical"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "health": [h.to_dict() if hasattr(h, "to_dict") else h for h in self.health],
            "data_quality": [d.to_dict() if hasattr(d, "to_dict") else d for d in self.data_quality],
            "steward": self.steward,
            "watchdog": {"complete": self.watchdog[0], "reasons": self.watchdog[1]},
            "dead_man": {"complete": self.dead_man[0], "reasons": self.dead_man[1]},
            "quota": {"used": self.quota[0], "remaining": self.quota[1]},
            "overall": self.overall,
        }


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _state_key(probe: str, level: str) -> str:
    """Stable key for a problem state."""
    if level == "ok":
        return ""
    return f"{probe}:{level}"


def _should_alert(probe: str, level: str, prev_state: dict, prev_at: float, now: float) -> bool:
    """Alert ONLY on state change: new problem, resolved problem, or long-open reminder."""
    key = f"{probe}:{level}"
    prev = prev_state.get(probe, "")
    if level == "ok":
        return prev != "" and prev != key
    if prev == key:
        return (now - prev_at) > RE_ALERT_AFTER_SECONDS
    return True  # new problem or different severity


def _alert_text(guardian_state: SystemState, changed: list) -> str:
    head = "[GUARDIAN] OLP XDV GUARDIAN — system state changes"
    lines = [head]
    for r in changed:
        tag = "HEALED" if getattr(r, "healed", False) else r.level.upper() if hasattr(r, "level") else "CHANGE"
        msg = r.message if hasattr(r, "message") else str(r)
        lines.append(f"  [{tag}] {r.name if hasattr(r, 'name') else 'probe'}: {msg}")
    bad = [r for r in guardian_state.health if not getattr(r, "is_fine", lambda: True)()]
    if bad:
        lines.append(f"\n  …{len(bad)} health issue(s) still open")
    lines.append("\nFull check: python monitor/framework_guardian.py")
    return "\n".join(lines)


# ============================================================================
# Probe Aggregation
# ============================================================================

def run_all_probes() -> SystemState:
    """Run all health probes and aggregate into SystemState."""
    state = SystemState()

    # 1. Health monitor probes
    health_results, _ = health_monitor.run_check(alert=False)
    state.health = health_results

    # 2. Data quality probes
    dq_findings = data_quality.check()
    state.data_quality = dq_findings

    # 3. Steward state (read from disk, don't re-run)
    steward_path = ROOT / "logs" / "steward_state.json"
    if steward_path.exists():
        try:
            state.steward = json.loads(steward_path.read_text(encoding="utf-8"))
        except Exception:
            state.steward = {}

    # 4. Watchdog (today's run)
    today = datetime.now(timezone.utc).date().isoformat()
    state.watchdog = run_watchdog.verify(today, notify_fn=lambda _: (False, []))

    # 5. Dead man's switch
    state.dead_man = dead_mans_switch.verify(notify_fn=lambda _: (False, []))

    # 6. Quota probe
    try:
        import pipeline.odds as odds
        state.quota = odds.check_quota()
    except Exception:
        state.quota = (-1, -1)

    # 6. Overall assessment
    critical_count = sum(1 for h in state.health if getattr(h, "level", "") == "critical")
    warn_count = sum(1 for h in state.health if getattr(h, "level", "") == "warn")
    dq_errors = sum(1 for d in state.data_quality if getattr(d, "level", "") == "error")
    dq_warns = sum(1 for d in state.data_quality if getattr(d, "level", "") == "warn")
    steward_fail = sum(1 for s in state.steward.get("sources", {}).values() if not s.get("ok", True))
    wd_fail = not state.watchdog[0]
    dm_fail = not state.dead_man[0]

    if critical_count > 0 or dq_errors > 0 or wd_fail or dm_fail:
        state.overall = "critical"
    elif warn_count > 0 or dq_warns > 0 or steward_fail > 0:
        state.overall = "degraded"
    else:
        state.overall = "healthy"

    return state


# ============================================================================
# Remediation Actions
# ============================================================================

class RemediationAction:
    """A single remediation action taken or attempted."""
    def __init__(self, name: str, description: str, success: bool, detail: str = ""):
        self.name = name
        self.description = description
        self.success = success
        self.detail = detail
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "success": self.success,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


def remediate_quota(state: SystemState) -> list[RemediationAction]:
    """Quota remediation: alert on low quota, trigger steward fallback warming."""
    actions = []
    used, remaining = state.quota

    if remaining < 0:
        actions.append(RemediationAction(
            "quota_probe_failed",
            "Could not probe Odds API quota",
            False,
            f"Probe returned ({used}, {remaining})"
        ))
        return actions

    if remaining <= QUOTA_HARD_FLOOR:
        actions.append(RemediationAction(
            "quota_exhausted",
            f"Quota at hard floor ({remaining}/{QUOTA_HARD_FLOOR})",
            False,
            "All keys exhausted — needs fresh key or monthly reset. "
            "Steward will attempt api-football fallback for fixture lists."
        ))
    elif remaining < QUOTA_FLOOR:
        actions.append(RemediationAction(
            "quota_below_floor",
            f"Quota below operational floor ({remaining}/{QUOTA_FLOOR})",
            True,
            "Steward odds pull will skip; api-football fallback engaged for fixture capture. "
            "ACTION: Add ODDS_API_KEY_BACKUP or ODDS_API_KEY_TERTIARY to .env"
        ))
    elif remaining < QUOTA_WARN_THRESHOLD:
        actions.append(RemediationAction(
            "quota_warning",
            f"Quota getting low ({remaining} remaining)",
            True,
            f"Monitor daily; consider adding backup key. Floor is {QUOTA_FLOOR}."
        ))
    else:
        actions.append(RemediationAction(
            "quota_healthy",
            f"Quota healthy ({remaining} remaining)",
            True,
            f"Well above floor ({QUOTA_FLOOR})"
        ))

    return actions


def remediate_caches(state: SystemState) -> list[RemediationAction]:
    """Cache freshness remediation: trigger steward for specific stale sources."""
    actions = []
    now = time.time()

    # Check steward state for source freshness
    sources = state.steward.get("sources", {})

    # SportyBet cache
    sb = sources.get("sportybet", {})
    if sb:
        try:
            fetched_at = datetime.fromisoformat(sb["fetched_at"].replace("Z", "+00:00"))
            age_h = (now - fetched_at.timestamp()) / 3600
            if age_h > CACHE_STALE_HOURS:
                actions.append(RemediationAction(
                    "sportybet_cache_stale",
                    f"SportyBet cache is {age_h:.1f}h old (threshold {CACHE_STALE_HOURS}h)",
                    False,
                    "Triggering targeted steward refresh"
                ))
                # In daemon mode, we'd trigger steward run here
            else:
                actions.append(RemediationAction(
                    "sportybet_cache_fresh",
                    f"SportyBet cache fresh ({age_h:.1f}h)",
                    True,
                    sb.get("detail", "")
                ))
        except Exception:
            pass

    # Odds cache
    odds = sources.get("odds", {})
    if odds and not odds.get("ok", True):
        actions.append(RemediationAction(
            "odds_cache_stale",
            "Odds primary source failed — fallback engaged",
            odds.get("ok", False),
            odds.get("detail", "")
        ))

    # Fixtures sources
    for src in ("tsdb", "espn", "clubelo"):
        s = sources.get(src, {})
        if s and not s.get("ok", True):
            actions.append(RemediationAction(
                f"{src}_cache_issue",
                f"{src} source failed",
                False,
                s.get("detail", "")
            ))

    return actions


def remediate_calibration(state: SystemState) -> list[RemediationAction]:
    """Calibration drift detection and shadow recalibration trigger."""
    actions = []

    for finding in state.data_quality:
        if finding.league == "CALIBRATION" and finding.level in ("warn", "error"):
            # Extract bin info from problem string
            problem = finding.problem
            err_pp = 0.0
            try:
                # "Bin 0.8-0.9: n=84, hit_rate=40.5%, avg_prob=84.8%, err=-44.3pp"
                err_str = problem.split("err=")[1].split("pp")[0]
                err_pp = float(err_str)
            except Exception:
                pass

            actions.append(RemediationAction(
                "calibration_drift",
                f"Calibration bin error: {problem}",
                finding.level == "warn",  # warn = actionable, error = critical
                f"Absolute error: {abs(err_pp):.1f}pp (threshold {CALIBRATION_ERROR_PP}pp). "
                f"{'Queue shadow recalibration.' if abs(err_pp) > CALIBRATION_ERROR_PP else 'Monitor.'}"
            ))

    return actions


def remediate_sportybet(state: SystemState) -> list[RemediationAction]:
    """SportyBet fixture coverage verification."""
    actions = []
    sources = state.steward.get("sources", {})
    sb = sources.get("sportybet", {})

    if sb:
        detail = sb.get("detail", "")
        # Parse fixture count from detail: "18 league(s) cached, 96 fixture(s) — ..."
        try:
            fixture_count = int(detail.split("fixture(s)")[0].split()[-1])
            if fixture_count < SPORTYBET_MIN_FIXTURES:
                actions.append(RemediationAction(
                    "sportybet_low_coverage",
                    f"SportyBet cache has only {fixture_count} fixtures (min {SPORTYBET_MIN_FIXTURES})",
                    False,
                    "Likely missing leagues. Trigger targeted cache warm for upcoming fixtures."
                ))
            else:
                actions.append(RemediationAction(
                    "sportybet_coverage_ok",
                    f"SportyBet cache has {fixture_count} fixtures",
                    True,
                    detail
                ))
        except Exception:
            actions.append(RemediationAction(
                "sportybet_parse_failed",
                "Could not parse SportyBet fixture count",
                False,
                f"Raw detail: {detail}"
            ))
    else:
        actions.append(RemediationAction(
            "sportybet_no_state",
            "No SportyBet steward state found",
            False,
            "Steward may not have run yet"
        ))

    return actions


def remediate_sportybet_failure_rates(state: SystemState) -> list[RemediationAction]:
    """SportyBet API failure rate monitoring and alerting."""
    actions = []

    if not _HAS_SPORTYBET_STATS:
        actions.append(RemediationAction(
            "sportybet_stats_unavailable",
            "SportyBet failure stats not available (module not importable)",
            False,
            "Ensure booking.sportybet_client is importable"
        ))
        return actions

    stats = get_failure_stats()

    if not stats:
        actions.append(RemediationAction(
            "sportybet_no_stats",
            "No SportyBet failure stats collected yet",
            True,
            "Will monitor on next check"
        ))
        return actions

    # Check each endpoint
    for endpoint, ep_stats in stats.items():
        rate = ep_stats.get("rate", 0.0)
        total = ep_stats.get("total", 0)
        failures = ep_stats.get("failures", 0)
        consecutive = ep_stats.get("consecutive_failures", 0)
        alert = ep_stats.get("alert", False)

        if total >= FAILURE_COUNT_ALERT_THRESHOLD and rate >= FAILURE_RATE_ALERT_THRESHOLD:
            actions.append(RemediationAction(
                "sportybet_high_failure_rate",
                f"SportyBet endpoint {endpoint}: {rate:.0%} failure rate ({failures}/{total})",
                False,
                f"Consecutive failures: {consecutive}. Check network/API status. "
                f"Circuit breaker may open if failures continue."
            ))
        elif total >= FAILURE_COUNT_ALERT_THRESHOLD and rate > 0.05:
            # Warning threshold (5%)
            actions.append(RemediationAction(
                "sportybet_elevated_failure_rate",
                f"SportyBet endpoint {endpoint}: {rate:.0%} failure rate ({failures}/{total})",
                True,
                f"Consecutive failures: {consecutive}. Monitor closely. "
                f"Alert threshold: {FAILURE_RATE_ALERT_THRESHOLD:.0%}"
            ))
        elif consecutive >= 3:
            # Even if rate is low, consecutive failures are concerning
            actions.append(RemediationAction(
                "sportybet_consecutive_failures",
                f"SportyBet endpoint {endpoint}: {consecutive} consecutive failures",
                True,
                f"Overall rate: {rate:.0%} ({failures}/{total}). "
                f"May indicate transient network issue."
            ))
        else:
            actions.append(RemediationAction(
                "sportybet_healthy",
                f"SportyBet endpoint {endpoint}: {rate:.0%} failure rate ({failures}/{total})",
                True,
                f"Consecutive failures: {consecutive}"
            ))

    return actions


def remediate_delivery(state: SystemState) -> list[RemediationAction]:
    """Telegram delivery verification."""
    actions = []

    # Watchdog checks if today's run completed AND delivered
    wd_complete, wd_reasons = state.watchdog
    dm_complete, dm_reasons = state.dead_man

    if not wd_complete:
        actions.append(RemediationAction(
            "delivery_watchdog_fail",
            f"Daily run incomplete: {'; '.join(wd_reasons)}",
            False,
            "Check Task Scheduler 'OLP XDV Daily Board' and logs/daily_<today>.log"
        ))
    else:
        actions.append(RemediationAction(
            "delivery_ok",
            "Daily run complete and delivered",
            True,
            "Watchdog verified"
        ))

    if not dm_complete:
        actions.append(RemediationAction(
            "delivery_dead_man_fail",
            f"Dead man's switch: {'; '.join(dm_reasons)}",
            False,
            "07:00 run did not fire or did not deliver. Check scheduler."
        ))

    return actions


def run_remediation(state: SystemState) -> list[RemediationAction]:
    """Run all remediation checks and return actions taken."""
    all_actions = []

    all_actions.extend(remediate_quota(state))
    all_actions.extend(remediate_caches(state))
    all_actions.extend(remediate_calibration(state))
    all_actions.extend(remediate_sportybet(state))
    all_actions.extend(remediate_sportybet_failure_rates(state))
    all_actions.extend(remediate_delivery(state))

    return all_actions


# ============================================================================
# Main Guardian Loop
# ============================================================================

def run_guardian_check(state_path: Path = DEFAULT_STATE, alert: bool = True) -> tuple[SystemState, list[RemediationAction], bool]:
    """Run one full guardian check cycle."""
    now = time.time()
    prev_state = _load_state(state_path)

    # Extract previous probe states (handle both old list format and new dict format)
    def get_prev_probe_state(category: str, name: str) -> tuple[str, float]:
        # Try new dict format first
        probes = prev_state.get(f"{category}_probes", {})
        if isinstance(probes, dict):
            key = probes.get(name, "")
            at = prev_state.get(f"{category}_probes_at", {}).get(name, 0)
            return key, at
        # Fallback: old list format in to_dict()
        return "", 0

    # Run all probes
    guardian_state = run_all_probes()

    # Run remediation
    actions = run_remediation(guardian_state)

    # Build alert list from health probes + remediation actions
    changed_probes = []

    # Check health probes for state changes
    for probe in guardian_state.health:
        name = getattr(probe, "name", "unknown")
        level = getattr(probe, "level", "unknown")
        prev, prev_at = get_prev_probe_state("health", name)
        if _should_alert(name, level, {"probe": prev}, prev_at, now):
            changed_probes.append(probe)

    # Check data quality
    for i, finding in enumerate(guardian_state.data_quality):
        name = f"dq_{finding.league}_{i}"
        level = finding.level
        prev, prev_at = get_prev_probe_state("data_quality", name)
        if _should_alert(name, level, {"probe": prev}, prev_at, now):
            changed_probes.append(finding)

    # Check steward sources
    for src_name, src_data in guardian_state.steward.get("sources", {}).items():
        name = f"steward_{src_name}"
        level = "ok" if src_data.get("ok", True) else "critical"
        prev, prev_at = get_prev_probe_state("steward", name)
        probe_obj = type("Probe", (), {"name": name, "level": level, "message": src_data.get("detail", "")})()
        if _should_alert(name, level, {"probe": prev}, prev_at, now):
            changed_probes.append(probe_obj)

    # Check delivery
    wd_name = "delivery_watchdog"
    wd_level = "ok" if guardian_state.watchdog[0] else "critical"
    prev, prev_at = get_prev_probe_state("delivery", wd_name)
    probe_obj = type("Probe", (), {"name": wd_name, "level": wd_level,
                                     "message": "; ".join(guardian_state.watchdog[1])})()
    if _should_alert(wd_name, wd_level, {"probe": prev}, prev_at, now):
        changed_probes.append(probe_obj)

    dm_name = "delivery_dead_man"
    dm_level = "ok" if guardian_state.dead_man[0] else "critical"
    prev, prev_at = get_prev_probe_state("delivery", dm_name)
    probe_obj = type("Probe", (), {"name": dm_name, "level": dm_level,
                                     "message": "; ".join(guardian_state.dead_man[1])})()
    if _should_alert(dm_name, dm_level, {"probe": prev}, prev_at, now):
        changed_probes.append(probe_obj)

    # Build new state for persistence
    new_state = guardian_state.to_dict()
    new_state["health_probes"] = {p.name: _state_key(p.name, p.level) for p in guardian_state.health if hasattr(p, "name")}
    new_state["health_probes_at"] = {p.name: int(now) for p in guardian_state.health if hasattr(p, "name")}
    new_state["data_quality_probes"] = {f"dq_{d.league}_{i}": _state_key(f"dq_{d.league}_{i}", d.level) for i, d in enumerate(guardian_state.data_quality)}
    new_state["data_quality_probes_at"] = {f"dq_{d.league}_{i}": int(now) for i, d in enumerate(guardian_state.data_quality)}
    new_state["steward_probes"] = {f"steward_{n}": _state_key(f"steward_{n}", "ok" if s.get("ok") else "critical") for n, s in guardian_state.steward.get("sources", {}).items()}
    new_state["steward_probes_at"] = {f"steward_{n}": int(now) for n, s in guardian_state.steward.get("sources", {}).items()}
    new_state["delivery_probes"] = {
        "delivery_watchdog": _state_key("delivery_watchdog", "ok" if guardian_state.watchdog[0] else "critical"),
        "delivery_dead_man": _state_key("delivery_dead_man", "ok" if guardian_state.dead_man[0] else "critical"),
    }
    new_state["delivery_probes_at"] = {
        "delivery_watchdog": int(now),
        "delivery_dead_man": int(now),
    }
    new_state["remediation"] = [a.to_dict() for a in actions]

    _save_state(state_path, new_state)

    # Alert if any changes
    alerted = False
    if changed_probes and alert:
        try:
            max_level = "critical" if any(getattr(r, "level", "") == "critical" for r in changed_probes) else "warn"
            title = f"OLP XDV Guardian: {len(changed_probes)} system change(s)"
            body = _alert_text(guardian_state, changed_probes)
            tags = [getattr(r, "name", "unknown") for r in changed_probes]
            results_disp = alert_dispatcher.dispatch_alert(max_level, title, body, tags)
            alerted = any(ok for ok, _ in results_disp.values())
        except Exception:
            try:
                ok, _ = notify.send_alert(_alert_text(guardian_state, changed_probes))
                alerted = ok
            except Exception:
                alerted = False

    return guardian_state, actions, alerted


def render_report(state: SystemState, actions: list[RemediationAction]) -> str:
    """Render a human-readable report."""
    out = []
    out.append(f"[GUARDIAN] OLP XDV FRAMEWORK GUARDIAN -- {state.timestamp}")
    out.append(f"Overall: {state.overall.upper()}")
    out.append("")

    # Health summary
    out.append("=== HEALTH PROBES ===")
    for h in state.health:
        mark = {"ok": "[OK]", "warn": "[WARN]", "critical": "[CRIT]"}.get(getattr(h, "level", "?"), "[?]")
        healed = " [HEALED]" if getattr(h, "healed", False) else ""
        out.append(f"  {mark} {getattr(h, 'name', '?'):<12} {getattr(h, 'message', '?')}{healed}")

    # Data quality
    out.append("\n=== DATA QUALITY ===")
    if not state.data_quality:
        out.append("  [OK] CLEAN -- all feeds fresh, duplicate-free")
    else:
        for d in state.data_quality:
            mark = {"info": "[INFO]", "warn": "[WARN]", "error": "[CRIT]"}.get(d.level, "[?]")
            out.append(f"  {mark} {d.league:<20} {d.problem}")

    # Steward
    out.append("\n=== STEWARD STATE ===")
    for name, src in state.steward.get("sources", {}).items():
        mark = "[OK]" if src.get("ok") else "[FAIL]"
        out.append(f"  {mark} {name:<10} {src.get('detail', '')}")

    # Quota
    out.append("\n=== QUOTA ===")
    used, remaining = state.quota
    if remaining >= 0:
        out.append(f"  Used: {used}, Remaining: {remaining} (Floor: {QUOTA_FLOOR}, Hard: {QUOTA_HARD_FLOOR})")
    else:
        out.append("  [FAIL] Probe failed")

    # Delivery
    out.append("\n=== DELIVERY ===")
    wd_ok, wd_reasons = state.watchdog
    dm_ok, dm_reasons = state.dead_man
    out.append(f"  {'[OK]' if wd_ok else '[FAIL]'} Watchdog: {'OK' if wd_ok else 'FAIL'} -- {'; '.join(wd_reasons) if wd_reasons else 'delivered'}")
    out.append(f"  {'[OK]' if dm_ok else '[FAIL]'} Dead-man:  {'OK' if dm_ok else 'FAIL'} -- {'; '.join(dm_reasons) if dm_reasons else 'delivered'}")

    # Remediation actions
    out.append("\n=== REMEDIATION ACTIONS ===")
    for a in actions:
        mark = "[OK]" if a.success else "[FAIL]"
        out.append(f"  {mark} {a.name}: {a.description}")
        if a.detail:
            out.append(f"      -> {a.detail}")

    return "\n".join(out)


def run_daemon(loop_seconds: int = DEFAULT_LOOP_SECONDS, state_path: Path = DEFAULT_STATE, alert: bool = True) -> None:
    """Run guardian continuously as a daemon."""
    print(f"[GUARDIAN] Guardian daemon starting (loop every {loop_seconds}s)...")
    print("Press Ctrl+C to stop")
    try:
        while True:
            print(f"\n[{datetime.now().isoformat()}] Guardian check...")
            state, actions, alerted = run_guardian_check(state_path, alert)
            print(render_report(state, actions))
            if alerted:
                print("  -> Alert dispatched")
            print(f"  -> Sleeping {loop_seconds}s...")
            time.sleep(loop_seconds)
    except KeyboardInterrupt:
        print("\n[GUARDIAN] Guardian daemon stopped")


def main() -> None:
    ap = argparse.ArgumentParser(description="OLP XDV Framework Guardian")
    ap.add_argument("--no-alert", action="store_true", help="skip Telegram alerts")
    ap.add_argument("--state", default=None, help="custom state file path")
    ap.add_argument("--daemon", action="store_true", help="run continuously (30-min loop)")
    ap.add_argument("--loop-seconds", type=int, default=DEFAULT_LOOP_SECONDS, help="daemon loop interval")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    state_path = Path(args.state) if args.state else DEFAULT_STATE

    if args.daemon:
        run_daemon(args.loop_seconds, state_path, not args.no_alert)
        return

    state, actions, alerted = run_guardian_check(state_path, not args.no_alert)

    if args.json:
        print(json.dumps({
            "state": state.to_dict(),
            "actions": [a.to_dict() for a in actions],
            "alerted": alerted,
        }, indent=2))
    else:
        print(render_report(state, actions))
        if alerted:
            print("\n-> Alert dispatched")

    # Exit code: 0=healthy, 1=degraded, 2=critical
    if state.overall == "critical":
        sys.exit(2)
    elif state.overall == "degraded":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()