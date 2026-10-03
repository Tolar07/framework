"""Prometheus text-exposition metrics for the web dashboard.

Served read-only at ``/metrics`` (see webapp/server.py). No client library —
the output is plain Prometheus exposition text, so any scrape target or
``curl localhost:8088/metrics`` works. Every collector fails soft: a missing
brain DB, a missing ``health_state.json``, or an empty boards dir never blocks
a scrape — it reports the zero we can actually observe (HR35: never a guess).

Naming follows the Prometheus convention: ``olp_<noun>_<unit>`` gauges,
``olp_<noun>_total`` counters, ``olp_<noun>_info`` label sets.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAIN_DB = ROOT / "brain" / "olp.db"
BOARDS_DIR = ROOT / "output" / "boards" / "published"
HEALTH_STATE = ROOT / "logs" / "health_state.json"

# Process birth — uptime is measured since the metrics module first loaded.
_STARTED = time.time()

# Severity keyword -> gauge value. Health_state values are short free-form
# strings like "quota:critical" or "ok"; we look for a keyword anywhere in the
# value so "caches:warn" grades 2 and "quota:critical" grades 3.
_SEVERITY = (("critical", 3), ("error", 3), ("failed", 3), ("stale", 2),
             ("warn", 2), ("ok", 1))


def _severity_of(text: str) -> int:
    low = text.lower()
    for token, sev in _SEVERITY:
        if token in low:
            return sev
    return 0


def _esc(s: str) -> str:
    """Escape a label value for exposition text (backslash + double quote)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _num(v: object) -> float:
    """Coerce a scraped value to a float Prometheus can parse; never NaN."""
    try:
        f = float(v)  # type: ignore[arg-type]
        return f if f == f else 0.0  # NaN guard
    except (TypeError, ValueError):
        return 0.0


def _metric(name: str, kind: str, help_: str, value: object,
            labels: dict | None = None) -> str:
    """One typed metric: HELP + TYPE + data line (TYPE/HELP deduped upstream)."""
    label_str = "".join(f'{k}="{_esc(v)}"' for k, v in (labels or {}).items())
    line = f"{name}{{{label_str}}} {_num(value):g}" if label_str \
        else f"{name} {_num(value):g}"
    return "\n".join((f"# HELP {name} {help_}", f"# TYPE {name} {kind}", line))


def _health_info() -> str:
    """Per-key health_state.json info + a severity gauge so dashboards can
    threshold without scraping label values."""
    out: list[str] = []
    try:
        state = json.loads(HEALTH_STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        state = {}
    except (OSError, json.JSONDecodeError):
        state = {"read_error": "json-decode-failed"}
    for name, raw in sorted(state.items()):
        if name.endswith("_at"):  # timestamps are not health signals
            continue
        text = str(raw or "")
        sev = _severity_of(text)
        out.append(
            f'olp_health_state_info{{name="{_esc(name)}",state="{_esc(text)}"}} 1'
        )
        out.append(f'olp_health_severity{{name="{_esc(name)}"}} {sev:g}')
    if not out:
        out.append('olp_health_state_info{name="none",state="no-state-file"} 1')
    return "\n".join(out)


def _boards_published() -> str:
    """Count of published board files on disk — the client-facing artifact."""
    try:
        n = sum(1 for _ in BOARDS_DIR.glob("board_*.json"))
    except OSError:
        n = 0
    return _metric("olp_boards_published_total", "counter",
                   "Number of published client boards.", n)


_GATE_HELP = {
    "legs": "Paper legs logged to the ledger.",
    "clv": "Logged legs that earned a closing line.",
    "req": "Legs-with-CLV needed to clear the Phase-3 gate.",
    "met": "1 when the leg-count and mean-CLV bar is met (pre-signoff).",
    "mean": "Mean paper CLV across logged legs, percent.",
}


def _gate() -> str:
    """Phase-3 gate trajectory, mirrored from the brain SQL (same fields as
    clv_log.json). When the brain DB is unreachable the requirement reports
    -1 (unknown) — never 0, which would read as 'gate already met'."""
    try:
        from brain.store import Brain

        with Brain(BRAIN_DB, read_only=True) as b:
            g: dict = b.gate_status()
    except Exception:
        return "\n".join([
            _metric("olp_phase3_legs_logged_total", "gauge", _GATE_HELP["legs"], 0),
            _metric("olp_phase3_legs_with_clv_total", "gauge", _GATE_HELP["clv"], 0),
            _metric("olp_phase3_gate_requirement", "gauge", _GATE_HELP["req"], -1),
            _metric("olp_phase3_gate_met_pending_architect_signoff", "gauge",
                    _GATE_HELP["met"], 0),
        ])
    out = [
        _metric("olp_phase3_legs_logged_total", "gauge", _GATE_HELP["legs"],
                g.get("legs_logged_total")),
        _metric("olp_phase3_legs_with_clv_total", "gauge", _GATE_HELP["clv"],
                g.get("legs_with_clv")),
        _metric("olp_phase3_gate_requirement", "gauge", _GATE_HELP["req"],
                g.get("gate_requirement")),
        _metric("olp_phase3_gate_met_pending_architect_signoff", "gauge",
                _GATE_HELP["met"],
                1 if g.get("gate_met_pending_architect_signoff") else 0),
    ]
    mc = g.get("mean_clv_pct")
    if mc is not None:  # no data point = unknown, do not fabricate a value
        out.append(_metric("olp_phase3_mean_clv_pct", "gauge",
                           _GATE_HELP["mean"], round(mc, 3)))
    return "\n".join(out)


def _last_run_age() -> str:
    """Seconds since the monitor's last heartbeat (health_state last_run_at).
    -1 means the monitor has never written a heartbeat, which is itself the
    alarm: the watchdog is down."""
    ts = 0.0
    try:
        state = json.loads(HEALTH_STATE.read_text(encoding="utf-8"))
        ts = _num(state.get("last_run_at"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        ts = 0.0
    if not ts:
        return _metric("olp_last_run_age_seconds", "gauge",
                       "Seconds since the monitor heartbeat.", -1)
    return _metric("olp_last_run_age_seconds", "gauge",
                   "Seconds since the monitor heartbeat.",
                   max(0.0, time.time() - ts))


def collect_metrics() -> str:
    """Render the full exposition payload for one scrape.

    Each metric name is typed exactly once (the multi-label health/sector
    collectors carry their own TYPE lines before the first data line).
    """
    blocks = [
        _metric("olp_web_up", "gauge", "1 if this process is serving.", 1),
        "",
        _boards_published(),
        "",
        _gate(),
        "",
        _last_run_age(),
        "",
        _metric("olp_process_uptime_seconds", "gauge",
                "Seconds this process has served.",
                round(time.time() - _STARTED, 0)),
        "",
        "# HELP olp_health_state_info Per-component health from health_state.",
        "# TYPE olp_health_state_info gauge",
        "# HELP olp_health_severity Numeric severity (0..3) per component.",
        "# TYPE olp_health_severity gauge",
        _health_info(),
    ]
    return "\n".join(blocks) + "\n"


def main() -> None:
    """CLI scrape target for a shell pipeline (curl-style without HTTP)."""
    import sys

    sys.stdout.write(collect_metrics())


if __name__ == "__main__":
    main()
