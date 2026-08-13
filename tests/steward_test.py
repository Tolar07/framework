"""Data Steward pass tests (Architect 2026-08-12).

The steward is the "always fetch the data the board needs" agent: a one-shot
best-effort pass that warms every source ahead of the 07:00 run. It must
never crash the scheduler — a source failure is a FLAG in steward_state.json,
and a source going red alerts once (state-change only).

The handlers are mocked here (no network, no Playwright); the harness under
test is run() itself: state shape, per-source failure as a flag, alert on
first-red only, and the state file round-trip.
"""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

# Fix __file__ when running via exec
if '__file__' not in globals():
    __file__ = r'c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\tests\steward_test.py'

sys.path.insert(0, str(Path(__file__).parent.parent))

import steward.run_steward as st


def _isolate():
    tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_steward_"))
    return (mock.patch.object(st, "STATE_PATH", tmp / "state.json"),
            mock.patch.object(st, "LOG_PATH", tmp / "steward.log"))


def _ok():
    return True, "fine"


def _fail():
    return False, "boom"


def _all_ok():
    return {name: (True, "fine") for name in (
        "sportybet", "odds", "af_odds", "tsdb", "espn", "clubelo", "fdc")}


# --- 1. a full pass writes state with per-source fetched_at + ok -------------
with mock.patch.object(st, "_st_sportybet", return_value=_ok()), \
     mock.patch.object(st, "_st_odds", return_value=(True, "fine", [])), \
     mock.patch.object(st, "_st_af_odds", return_value=_ok()), \
     mock.patch.object(st, "_st_tsdb", return_value=_ok()), \
     mock.patch.object(st, "_st_espn", return_value=_ok()), \
     mock.patch.object(st, "_st_clubelo", return_value=_ok()), \
     mock.patch.object(st, "_st_fdc", return_value=_ok()), \
     mock.patch.object(st, "_should_alert", return_value=False):
    state_patch, log_patch = _isolate()
    with state_patch, log_patch:
        state = st.run(alert=True)
        for name, s in state["sources"].items():
            assert s["ok"] is True, f"{name} should be ok"
            assert s["fetched_at"], f"{name} missing fetched_at"
        assert state["fixtures_season"] == "2627"
        # state file round-trips
        on_disk = json.loads(st.STATE_PATH.read_text(encoding="utf-8"))
        assert on_disk["sources"]["sportybet"]["ok"] is True
print("1. pass writes state, per-source fetched_at + ok, file round-trip: OK")

# --- 2. a source failure is a flag, not a crash ------------------------------
with mock.patch.object(st, "_st_sportybet", side_effect=RuntimeError("playwright down")), \
     mock.patch.object(st, "_st_odds", return_value=(True, "fine", [])), \
     mock.patch.object(st, "_st_af_odds", return_value=_ok()), \
     mock.patch.object(st, "_st_tsdb", return_value=_ok()), \
     mock.patch.object(st, "_st_espn", return_value=_ok()), \
     mock.patch.object(st, "_st_clubelo", return_value=_ok()), \
     mock.patch.object(st, "_st_fdc", return_value=_ok()), \
     mock.patch.object(st, "_should_alert", return_value=False):
    state_patch, log_patch = _isolate()
    with state_patch, log_patch:
        state = st.run(alert=True)  # must not raise
        assert state["sources"]["sportybet"]["ok"] is False
        assert "unhandled" in state["sources"]["sportybet"]["detail"]
        assert all(s["ok"] for n, s in state["sources"].items() if n != "sportybet")
print("2. a source failure lands as a flag, never a crash: OK")

# --- 3. alert fires on FIRST red only (state-change discipline) --------------
# State/log persist across the three passes so the second pass sees the first
# pass's red state — that is exactly what prevents daily re-alert spam.
calls: list[str] = []
state_patch, log_patch = _isolate()
_others = {"_st_odds": (True, "fine", []), "_st_af_odds": _ok(),
           "_st_tsdb": _ok(), "_st_espn": _ok(), "_st_clubelo": _ok(),
           "_st_fdc": _ok()}


def fake_alert(body, **kw):
    calls.append(body)
    return True, []


with mock.patch.object(st, "_st_sportybet", return_value=_fail()), \
     mock.patch.object(st, "_st_odds", return_value=_others["_st_odds"]), \
     mock.patch.object(st, "_st_af_odds", return_value=_ok()), \
     mock.patch.object(st, "_st_tsdb", return_value=_ok()), \
     mock.patch.object(st, "_st_espn", return_value=_ok()), \
     mock.patch.object(st, "_st_clubelo", return_value=_ok()), \
     mock.patch.object(st, "_st_fdc", return_value=_ok()), \
     state_patch, log_patch, mock.patch(
            "output.notify.send_alert", side_effect=fake_alert):
    st.run(alert=True)   # first pass: sportybet went red -> alert
assert len(calls) == 1 and "sportybet" in calls[0], "first red must alert"

# Second pass, still red: NO new alert (already-reported issue stays quiet).
with mock.patch.object(st, "_st_sportybet", return_value=_fail()), \
     mock.patch.object(st, "_st_odds", return_value=_others["_st_odds"]), \
     mock.patch.object(st, "_st_af_odds", return_value=_ok()), \
     mock.patch.object(st, "_st_tsdb", return_value=_ok()), \
     mock.patch.object(st, "_st_espn", return_value=_ok()), \
     mock.patch.object(st, "_st_clubelo", return_value=_ok()), \
     mock.patch.object(st, "_st_fdc", return_value=_ok()), \
     state_patch, log_patch, mock.patch(
            "output.notify.send_alert", side_effect=fake_alert):
    st.run(alert=True)
assert len(calls) == 1, "an already-red source must NOT re-alert"

# Third pass, sportybet recovers: no alert (resolution is not a problem).
with mock.patch.object(st, "_st_sportybet", return_value=_ok()), \
     mock.patch.object(st, "_st_odds", return_value=_others["_st_odds"]), \
     mock.patch.object(st, "_st_af_odds", return_value=_ok()), \
     mock.patch.object(st, "_st_tsdb", return_value=_ok()), \
     mock.patch.object(st, "_st_espn", return_value=_ok()), \
     mock.patch.object(st, "_st_clubelo", return_value=_ok()), \
     mock.patch.object(st, "_st_fdc", return_value=_ok()), \
     state_patch, log_patch, mock.patch(
            "output.notify.send_alert", side_effect=fake_alert):
    st.run(alert=True)
assert len(calls) == 1, "resolution must not alert (it is not red)"
print("3. state-change alert: first red only, no re-alert, no resolve-alert: OK")

print(f"\nsteward_test: ALL 3 PASSED")
