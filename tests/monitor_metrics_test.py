"""Prometheus exposition tests for monitor/metrics.py.

Pure collectors — no HTTP. The module globals (state file / boards dir / brain
DB) are patched to throwaway paths so the assertions are deterministic, then
one live check runs against the real repo DB if it exists.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import metrics

_tmp = Path(tempfile.mkdtemp(prefix="olp_metrics_test_"))


def _write_state(payload: dict) -> Path:
    p = _tmp / "health_state.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _metric_lines(text: str, name: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.startswith(name)]


def _name(ln: str) -> str:
    """Metric name = the token before any '{' label set."""
    return ln.split("{", 1)[0].split()[0]


def _typed_once(text: str) -> bool:
    """Every metric name gets exactly one # TYPE line (Prometheus rejects
    repeated types for the same metric)."""
    names = {_name(ln) for ln in text.splitlines() if ln.startswith("olp_")}
    for n in names:
        types = [ln for ln in text.splitlines()
                 if ln in (f"# TYPE {n} gauge", f"# TYPE {n} counter")]
        assert len(types) == 1, f"metric {n} typed {len(types)} times"
    return True


# --- severity grading from health_state values --------------------------------
_state = _write_state({
    "quota": "quota:critical",
    "caches": "caches:warn",
    "env": "ok",
    "phase": "",
    "unknown_thing": "zzz",
    "last_run_at": 0,
})
with patch.object(metrics, "HEALTH_STATE", _state), \
     patch.object(metrics, "BOARDS_DIR", _tmp / "empty"), \
     patch.object(metrics, "BRAIN_DB", _tmp / "missing.db"):
    text = metrics.collect_metrics()
    assert "olp_health_severity{name=\"quota\"} 3" in text, text
    assert "olp_health_severity{name=\"caches\"} 2" in text, text
    assert "olp_health_severity{name=\"env\"} 1" in text, text
    assert "olp_health_severity{name=\"phase\"} 0" in text, text
    assert "olp_health_severity{name=\"unknown_thing\"} 0" in text, text
    assert 'olp_health_state_info{name="quota",state="quota:critical"} 1' in text
    # the "_at" timestamp key is not a health signal (skipped entirely)
    assert not _metric_lines(text, "olp_health_state_info{name=\"last_run_at\"")
    assert _metric_lines(text, "olp_health_state_info"), "state info missing"
print("severity grading + state info: OK")


# --- boards count -------------------------------------------------------------
_boards = _tmp / "published"
_boards.mkdir(exist_ok=True)
for d in ("2026-08-07", "2026-08-08", "2026-08-09"):
    (_boards / f"board_{d}.json").write_text("{}", encoding="utf-8")
with patch.object(metrics, "BOARDS_DIR", _boards), \
     patch.object(metrics, "BRAIN_DB", _tmp / "missing.db"), \
     patch.object(metrics, "HEALTH_STATE", _tmp / "nope.json"):
    text = metrics.collect_metrics()
    assert "olp_boards_published_total 3" in text, text
    # missing health_state -> zero-value info, not a crash
    assert 'olp_health_state_info{name="none",state="no-state-file"}' in text
print("board count + missing-state fallback: OK")


# --- missing brain DB -> -1 requirement (never a 'met' 0) ---------------------
with patch.object(metrics, "BRAIN_DB", _tmp / "does-not-exist.db"), \
     patch.object(metrics, "BOARDS_DIR", _tmp / "empty"), \
     patch.object(metrics, "HEALTH_STATE", _tmp / "nope.json"):
    text = metrics.collect_metrics()
    assert "olp_phase3_gate_requirement -1" in text, text
    assert "olp_phase3_gate_met_pending_architect_signoff 0" in text
print("missing brain -> requirement -1 (unknown, not met): OK")


# --- one TYPE line per metric name -------------------------------------------
with patch.object(metrics, "BOARDS_DIR", _boards), \
     patch.object(metrics, "BRAIN_DB", _tmp / "does-not-exist.db"), \
     patch.object(metrics, "HEALTH_STATE", _state):
    assert _typed_once(metrics.collect_metrics())
print("every metric typed exactly once: OK")


# --- label escaping: a quote in a state value must not break the format ------
_q = _write_state({"flag": 'say "hi" ok'})
with patch.object(metrics, "HEALTH_STATE", _q), \
     patch.object(metrics, "BOARDS_DIR", _tmp / "empty"), \
     patch.object(metrics, "BRAIN_DB", _tmp / "nope.db"):
    text = metrics.collect_metrics()
    assert 'olp_health_severity{name="flag"} 1' in text  # 'ok' still graded
    assert 'state="say \\"hi\\" ok"' in text, text
print("label escaping: OK")


# --- live brain check (real DB present in the repo) ---------------------------
if metrics.BRAIN_DB.exists():
    with patch.object(metrics, "BOARDS_DIR", _tmp / "empty"), \
         patch.object(metrics, "HEALTH_STATE", _tmp / "nope.json"):
        text = metrics.collect_metrics()
        assert "olp_phase3_gate_requirement 30" in text, text
        assert _metric_lines(text, "olp_phase3_legs_logged_total"), \
            "live gate metrics missing"
    print("live brain gate metrics: OK")
else:
    print("SKIP live brain check (no brain/olp.db on this box)")

print("\n[OK] ALL MONITOR METRICS TESTS PASSED")
