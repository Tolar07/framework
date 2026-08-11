"""Health monitor — self-triggering, self-healing awareness for the framework.

The daily run is a single point of health: if nothing fires it, or it fires
against a stale cache / low quota / broken brain, nothing notices until the
board is wrong. This monitor runs on ITS OWN schedule (Task Scheduler, e.g.
every 2h + before the 07:00 slot) and answers the questions the daily run
assumes are fine:

    1.  Phase guard            — is the paper-only capital block still in force?
    2.  Env completeness       — are the keys the pipeline needs actually set?
    3.  Brain health           — does brain/olp.db open, migrate, and hold model state?
    4.  CLV ledger             — does clv/clv_log.json parse and hold the canonical legs?
    5.  Odds quota             — how much of the free-tier monthly quota is left?
    6.  Cache freshness        — are the TTL caches within their max ages?
    7.  Last daily run         — did yesterday's/today's run complete AND deliver?
    8.  Web dashboard          — is the local server reachable?
    9.  Data-source circuits   — is any fallback source in circuit_open?

SELF-HEALING: a probe may FIX the thing it found rather than just report it —
the stale live-season results feed is re-downloaded so the 07:00 run settles
legs against current data, not last night's snapshot. A heal is logged and
counted, never silent.

ALERTING (best-effort Telegram): only STATE CHANGES alert. A problem that was
already reported at the last check does NOT re-alert — otherwise a week of
"quota low" would spam the phone every 2h. A NEW problem (or one that
resolved, or one still open after a long silence) alerts once. Same
never-raises discipline as the watchdog: the monitor must never crash the
scheduler.

HONESTY (HR35): every probe reports what it found — a missing file, a wrong
schema, a circuit open. No probe ever guesses a value it could not read; the
unreadable probe reports its own failure instead of fabricating a pass.

USAGE
    python monitor/health_monitor.py                  # one full check + heal
    python monitor/health_monitor.py --no-alert       # check + heal, no Telegram
    python monitor/health_monitor.py --state <path>   # custom state file (tests)
"""
from __future__ import annotations

import argparse
import datetime
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from brain.store import Brain  # noqa: E402
from clv.clv_logger import CLVLog  # noqa: E402
from monitor import run_watchdog  # noqa: E402
from output import notify  # noqa: E402
# Deterministic import order for a latent cycle: pipeline.odds does
# `from data.multi_source import SourceNoData` at line 41, but SourceNoData is
# only DEFINED at line 256 of data/multi_source.py. If odds is imported while
# multi_source is still mid-load, the name bind fails. Fully loading
# data.multi_source FIRST (this line) guarantees the symbol exists, so no
# later probe can hit the half-loaded state.
from data.multi_source import SourceNoData  # noqa: E402,F401  (force full load)

# State file: remembers what was last reported so alerts only fire on CHANGE.
DEFAULT_STATE = ROOT / "logs" / "health_state.json"

# A problem left unreported for this long re-alerts even if its state never
# changed (the reminder ring). Prevents an issue silently going stale forever.
RE_ALERT_AFTER_SECONDS = 26 * 3600  # ~daily reminder for an open issue

# Required env keys for a healthy pipeline. ODDS/TSDB feed the model; TELEGRAM
# is the delivery channel; API-FOOTBALL is the fallback history source. Each
# is verified SET (non-empty), never its secret value.
REQUIRED_ENV = ("ODDS_API_KEY", "THESPORTSDB_KEY", "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID", "API_FOOTBALL_KEY")

# Cache TTLs mirrored from the modules that own them — a probe must agree with
# the consumer or it will "fix" a cache the consumer just rejected, or worse
# accept one the consumer will throw away. These are the OWNERS' constants.
try:
    from data.football_data_source import (LIVE_SEASON_MAX_AGE_SECONDS,
                                           COMPLETED_SEASON_MAX_AGE_SECONDS,
                                           _season_is_live)
    from data.fixtures_source import FIXTURES_MAX_AGE_SECONDS
    _HAS_DATA_CONSTS = True
except Exception:  # pragma: no cover - imports can't fail in the real tree
    LIVE_SEASON_MAX_AGE_SECONDS = 6 * 3600
    COMPLETED_SEASON_MAX_AGE_SECONDS = 30 * 24 * 3600
    FIXTURES_MAX_AGE_SECONDS = 6 * 3600
    _HAS_DATA_CONSTS = False

    def _season_is_live(season: str) -> bool:
        return False

# Web dashboard liveness probe.
DASHBOARD_HOST, DASHBOARD_PORT = "127.0.0.1", 8088


# --------------------------------------------------------------------------
# Probe results
# --------------------------------------------------------------------------

class ProbeResult:
    """One probe's finding: name, level, message. Never fabricated."""
    __slots__ = ("name", "level", "message", "healed")

    def __init__(self, name: str, level: str, message: str, healed: bool = False):
        self.name = name
        self.level = level  # "ok" | "warn" | "critical"
        self.message = message
        self.healed = healed  # True if this check FIXED what it found

    def is_fine(self) -> bool:
        return self.level == "ok"

    def to_dict(self) -> dict:
        return {"name": self.name, "level": self.level,
                "message": self.message, "healed": self.healed}


def _ok(name: str, message: str) -> ProbeResult:
    return ProbeResult(name, "ok", message)


def _warn(name: str, message: str) -> ProbeResult:
    return ProbeResult(name, "warn", message)


def _crit(name: str, message: str, healed: bool = False) -> ProbeResult:
    return ProbeResult(name, "critical", message, healed=healed)


# --------------------------------------------------------------------------
# Individual probes
# --------------------------------------------------------------------------

def probe_phase() -> ProbeResult:
    """1. Is the paper-only capital block still in force?"""
    try:
        config.assert_paper_only(None)
        return _ok("phase", f"paper-only held ({config.PHASE_LABEL})")
    except Exception as e:
        return _crit("phase", f"CAPITAL BLOCK RAISED: {e}")


def probe_env() -> ProbeResult:
    """2. Are the keys the pipeline needs actually set (non-empty)?"""
    import os
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k, "").strip()]
    if missing:
        return _crit("env", "missing required keys: " + ", ".join(missing))
    return _ok("env", f"{len(REQUIRED_ENV)} required keys set")


def probe_brain() -> ProbeResult:
    """3. Does brain/olp.db open, migrate, and hold model state?"""
    db_path = ROOT / "brain" / "olp.db"
    if not db_path.exists():
        return _crit("brain", f"{db_path} missing — the brain has no memory "
                              f"yet; model fits rebuild from scratch every run")
    try:
        with Brain(db_path) as brain:
            version = brain.schema_version  # property, not a method
            models = brain.model_state_summary()
            if version < 5:
                return _crit("brain", f"schema v{version} behind the code's "
                                      f"latest — migration should have stepped it forward")
            if not models:
                return _warn("brain", f"schema v{version} OK but no fitted model state stored "
                                      f"— first run will rebuild from scratch")
            return _ok("brain", f"schema v{version}, {len(models)} model state(s)")
    except Exception as e:
        return _crit("brain", f"cannot open brain: {e}")


def probe_ledger() -> ProbeResult:
    """4. Does clv/clv_log.json parse and hold the canonical legs?"""
    log_path = ROOT / "clv" / "clv_log.json"
    if not log_path.exists():
        return _warn("ledger", f"{log_path} missing — no paper legs logged yet")
    try:
        log = CLVLog(log_path)
        return _ok("ledger", f"{len(log.legs)} paper leg(s)")
    except Exception as e:
        return _crit("ledger", f"clv_log.json unreadable: {e}")


def probe_quota() -> ProbeResult:
    """5. How much of the free-tier monthly odds quota is left?"""
    import pipeline.odds as odds
    try:
        used, remaining = odds.check_quota()
    except Exception as e:
        return _crit("quota", f"cannot probe quota: {e}")
    if remaining < odds.QUOTA_HARD_FLOOR:
        return _crit("quota", f"{remaining} requests left (hard floor "
                              f"{odds.QUOTA_HARD_FLOOR}) — the daily run may be "
                              f"unable to pull any odds")
    if remaining < odds.QUOTA_FLOOR:
        return _warn("quota", f"{remaining} requests left (floor {odds.QUOTA_FLOOR}) — "
                              f"below the guard that protects the deploy leagues")
    return _ok("quota", f"{remaining} requests left this cycle (used {used})")


def _live_season_code(today: datetime.date | None = None) -> str:
    """The season code football-data is publishing right now.

    '2627' spans Aug 2026 - Jul 2027. Today's year/month decides which season
    is live — same window rule as data.football_data_source._season_is_live.
    `today` is injectable for tests (date.today is immutable in CPython)."""
    today = today or datetime.date.today()
    start = today.year - 2000
    if today.month >= 8:
        end = today.year + 1 - 2000
    else:
        start = today.year - 1 - 2000
        end = today.year - 2000
    return f"{start:02d}{end:02d}"


def _heal_stale_live_csv(csv: Path, season: str) -> bool:
    """Re-download a stale LIVE-season results file.

    The live-season CSV is what legs settle against (the Phase-3 gate bug was
    a frozen snapshot); a stale one quietly settles against last night's data.
    `load_league` already re-fetches when the cache is over TTL and KEEPS the
    stale snapshot if the refresh fails — so the heal is simply calling it with
    the league the file belongs to, and letting the owner's own freshness +
    staleness-keeping semantics decide the outcome. Returns True only when the
    file is actually newer afterwards."""
    # Extra-code leagues (Ekstraklasa, Danish Superliga) are one file bundling
    # every season, so the "season" on the stem is really the file kind — the
    # refresh must be told the season that is live TODAY.
    refresh_season = _live_season_code() if csv.name.endswith("_all.csv") else season
    league = (csv.stem.replace("_all", "")
                     .replace(f"_{season}", "").replace("_", " "))
    before = csv.stat().st_mtime
    try:
        from data.football_data_source import load_league
        load_league(league, refresh_season, cache_dir=csv.parent)
    except Exception:
        return False  # refresh failed — owner kept the stale snapshot
    # load_league KEEPS the stale snapshot when the source has nothing new, so
    # a non-raising call is NOT proof of a heal — the file must be newer.
    return csv.stat().st_mtime > before


def probe_caches() -> ProbeResult:
    """6. Are the TTL caches within their owners' max ages?

    SELF-HEALING: a stale LIVE-season results file is re-downloaded rather
    than just reported — that is the file whose staleness cost the Phase-3
    gate its reachability. The heal is the owner's own refresh path, so it
    keeps the stale snapshot on failure and only counts as healed when the
    file is actually fresh afterwards."""
    cache_dir = ROOT / "data" / "cache"
    stale: list[str] = []
    healed = 0
    now = time.time()
    # Live-season results CSVs refresh every run — a stale one settles legs
    # against last night's snapshot, which is exactly the Phase-3 gate bug.
    results = cache_dir / "football_data" if (cache_dir / "football_data").exists() \
        else cache_dir
    for csv in sorted(results.glob("*.csv")):
        try:
            season = csv.stem.rsplit("_", 1)[-1]
        except ValueError:
            continue
        age = now - csv.stat().st_mtime
        if _season_is_live(season):
            if age > LIVE_SEASON_MAX_AGE_SECONDS:
                if _heal_stale_live_csv(csv, season):
                    healed += 1
                else:
                    stale.append(f"{csv.name} (live season, {int(age/3600)}h old)")
        elif age > COMPLETED_SEASON_MAX_AGE_SECONDS:
            stale.append(f"{csv.name} (completed season, {int(age/86400)}d old)")
    # Fixtures-from-odds cache (fixtures_source) — NOT healed: re-pulling the
    # odds feed spends the quota the monitor is supposed to protect.
    fo = cache_dir / "fixtures_from_odds"
    if fo.exists():
        for f in fo.glob("*.json"):
            age = now - f.stat().st_mtime
            if age > FIXTURES_MAX_AGE_SECONDS:
                stale.append(f"{f.name} (fixtures, {int(age/3600)}h old)")
    if healed:
        # Some live files healed; report the residual stale ones (if any).
        if stale:
            return _warn("caches", f"healed {healed} stale live-season file(s); "
                                   f"still stale: " + "; ".join(stale[:4]) +
                         (f" (+{len(stale)-4} more)" if len(stale) > 4 else ""))
        return ProbeResult("caches", "ok",
                           f"healed {healed} stale live-season file(s) "
                           f"(refresh succeeded)", healed=True)
    if stale:
        return _warn("caches", "; ".join(stale[:4]) +
                     (f" (+{len(stale)-4} more)" if len(stale) > 4 else ""))
    return _ok("caches", "all TTL caches within max age")


def probe_data_quality() -> ProbeResult:
    """6b. Are the cached results feeds complete, fresh, and duplicate-free?

    Complements probe_caches (which watches TTLs) with the PER-LEAGUE view:
    a whitelisted league with no results feed for the fit season is a coverage
    gap (its fixtures stay NO DATA — PENDING and the Phase 3 gate cannot fill
    itself), and a same-day same-pairing row twice in one season file is a
    feed error that would teach the engine one match twice. Delegates to
    monitor/data_quality.check(), which never raises — an unreadable cache is
    itself a finding, not a crash."""
    try:
        from monitor.data_quality import check
        findings = check()
    except Exception as e:
        return _crit("data_quality", f"cannot run data-quality check: {e}")
    if not findings:
        return _ok("data_quality", "all whitelisted leagues have fresh, "
                                   "duplicate-free results feeds")
    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    parts = errors + warns
    shown = parts[:2]
    msg = "; ".join(f"{f.league}: {f.problem}" for f in shown)
    if len(parts) > len(shown):
        msg += f" (+{len(parts) - len(shown)} more)"
    if errors:
        return _crit("data_quality", msg)
    return _warn("data_quality", msg)


def probe_last_run() -> ProbeResult:
    """7. When did the last daily run complete AND deliver?

    Scans back up to 4 days. Today's run may legitimately not have fired yet
    (the monitor can run before 07:00), so the check is "was there a recent
    delivered run", not "did today deliver" — a run that completed but did NOT
    deliver is a critical finding either way (run_daily raises on that)."""
    logs_dir = ROOT / "logs"
    today = datetime.date.today()
    # Most recent completed-and-delivered run, scanning newest first.
    for i in range(4):
        d = (today - datetime.timedelta(days=i)).isoformat()
        log_path = logs_dir / f"daily_{d}.log"
        if not log_path.exists():
            continue
        complete, reasons = run_watchdog.check_run_log(log_path)
        if complete:
            prefix = f"{d}: run complete and delivered"
            if i:
                prefix += f" (newest delivered run; today's not delivered yet)"
            return _ok("last_run", prefix)
        # A run that completed but did not deliver is itself a critical find.
        if "run completed OK" in log_path.read_text(encoding="utf-8",
                                                    errors="replace"):
            return _crit("last_run", f"{d}: run completed but did NOT deliver "
                                     f"to Telegram — {reasons[0] if reasons else 'no delivery line'}")
    return _crit("last_run", "no delivered daily run in the last 4 days")


def probe_dashboard() -> ProbeResult:
    """8. Is the local web dashboard reachable?"""
    try:
        s = socket.create_connection((DASHBOARD_HOST, DASHBOARD_PORT), timeout=2)
        s.close()
        return _ok("dashboard", f"server up on :{DASHBOARD_PORT}")
    except Exception:
        return _warn("dashboard", f"no server on {DASHBOARD_HOST}:{DASHBOARD_PORT} — "
                                  f"run webapp/server.py to view the board")


def probe_circuits() -> ProbeResult:
    """9. Is any fallback data source stuck in circuit_open?"""
    try:
        from data import multi_source_concrete as conc
        # initialize_multi_sources registers the shared fixtures/results/xg
        # sources into the global registry (idempotent — the registry dedupes
        # by name, so calling it again on a fresh process is the normal path).
        try:
            conc.initialize_multi_sources()
        except Exception:
            pass  # already initialized, or a source that needs a key we lack
        report = conc.get_all_health()
        sources = report.get("sources", {})
        if not sources:
            return _warn("circuits", "no multi-sources registered")
        open_sources = [
            f"{name}/{s['name']}"
            for name, ms in sources.items()
            for s in (ms or {}).get("sources", [])
            if s.get("circuit_open")
        ]
        if open_sources:
            return _warn("circuits", "circuit_open: " + ", ".join(open_sources))
        n = sum(len((ms or {}).get("sources", [])) for ms in sources.values())
        return _ok("circuits", f"{n} source(s) across {len(sources)} group(s) healthy")
    except Exception as e:
        return _warn("circuits", f"cannot inspect sources: {e}")


ALL_PROBES = (
    ("phase", probe_phase),
    ("env", probe_env),
    ("brain", probe_brain),
    ("ledger", probe_ledger),
    ("quota", probe_quota),
    ("caches", probe_caches),
    ("data_quality", probe_data_quality),
    ("last_run", probe_last_run),
    ("dashboard", probe_dashboard),
    ("circuits", probe_circuits),
)


# --------------------------------------------------------------------------
# State-aware alerting
# --------------------------------------------------------------------------

def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1), encoding="utf-8")


def _states_match(probe_name: str, level: str) -> str:
    """Returns a stable key describing a problem state (or None when fine)."""
    if level == "ok":
        return ""
    return f"{probe_name}:{level}"


def _should_alert(probe_name: str, level: str, prev_state: dict,
                  prev_at: float, now: float) -> bool:
    """Alert ONLY on state change: new problem, resolved problem, or an open
    problem that has been silent past RE_ALERT_AFTER_SECONDS.

    `prev_state` is {probe_name: previous_key} — "" means the probe was fine
    last check. `prev_at` is when the previous state was first recorded."""
    key = f"{probe_name}:{level}"
    prev = prev_state.get(probe_name, "")
    if level == "ok":
        # Alert on RESOLUTION only if the previous state was a problem.
        return prev != "" and prev != key
    if prev == key:
        # Same problem — alert again only after the reminder silence,
        # measured from when it FIRST appeared.
        return (now - prev_at) > RE_ALERT_AFTER_SECONDS
    return True  # new problem (or different severity)


def _alert_text(results: list[ProbeResult], changed: list[ProbeResult]) -> str:
    head = "⚠ OLP XDV HEALTH — changes to report"
    lines = [head]
    for r in changed:
        tag = "HEALED" if r.healed else r.level.upper()
        lines.append(f"  [{tag}] {r.name}: {r.message}")
    bad = [r for r in results if not r.is_fine()]
    if len(bad) > len(changed):
        lines.append(f"  …and {len(bad) - len(changed)} unchanged issue(s) still open")
    lines.append("")
    lines.append("Full check: run 'python monitor/health_monitor.py'")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main check
# --------------------------------------------------------------------------

def run_check(state_path: Path = DEFAULT_STATE, alert: bool = True,
              now: float | None = None) -> tuple[list[ProbeResult], bool]:
    """Run every probe, apply heals, alert on state changes.

    Returns (results, any_alerted). Never raises — a crashing monitor is the
    same failure mode as a crashing daily run, and it exists to catch those.

    A "change" is: a probe newly failing, a probe that was failing now
    resolved, or a probe that has been failing for over RE_ALERT_AFTER_SECONDS
    (the reminder ring). A probe that keeps failing check-to-check does NOT
    re-alert — that is what makes a 2-hourly monitor bearable."""
    now = now if now is not None else time.time()
    state = _load_state(state_path)
    results = [probe() for _, probe in ALL_PROBES]
    changed: list[ProbeResult] = []

    for r in results:
        prev = state.get(r.name, "")          # "" = was fine
        prev_at = state.get(f"{r.name}_at", 0)
        key = _states_match(r.name, r.level)
        # Decide on the PREVIOUS state, with the previous first-seen time, so
        # the reminder ring measures from when the issue FIRST appeared.
        if _should_alert(r.name, r.level, {r.name: prev}, prev_at, now):
            changed.append(r)
        # Record the new state; keep the ORIGINAL first-seen time unless the
        # state actually changed (a re-raised issue restarts its clock).
        state[r.name] = key
        state[f"{r.name}_at"] = int(prev_at) if (prev == key and prev_at) else int(now)

    _save_state(state_path, state)

    alerted = False
    if changed and alert:
        try:
            ok, _ = notify.send_alert(_alert_text(results, changed))
            alerted = ok
        except Exception:
            alerted = False  # monitor must never crash the scheduler
    return results, alerted


def render_results(results: list[ProbeResult]) -> str:
    out: list[str] = []
    for r in results:
        mark = {"ok": "✓", "warn": "⚠", "critical": "✗"}.get(r.level, "?")
        healed = "  [HEALED]" if r.healed else ""
        out.append(f"{mark} {r.name:<10} {r.message}{healed}")
    n_bad = sum(1 for r in results if not r.is_fine())
    out.append("")
    if n_bad:
        out.append(f"{n_bad} issue(s) found — see above.")
    else:
        out.append("All systems nominal.")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OLP XDV health monitor")
    ap.add_argument("--no-alert", action="store_true",
                    help="check + heal without Telegram alerts")
    ap.add_argument("--state", default=None, help="custom state file path")
    a = ap.parse_args()
    state_path = Path(a.state) if a.state else DEFAULT_STATE
    results, _ = run_check(state_path=state_path, alert=not a.no_alert)
    print(render_results(results))
    sys.exit(0 if all(r.is_fine() for r in results) else 2)
