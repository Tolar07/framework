"""Health-monitor tests: alert-on-change, resolution, reminder ring, heal honesty.

The monitor is the self-triggering watchdog — it runs on ITS OWN schedule and
answers questions the daily run assumes are fine. These tests pin the two
things that matter most:

1. ALERT ONLY ON CHANGE. A problem that keeps failing check-to-check must NOT
   spam Telegram every 2 hours; a NEW problem, a RESOLVED problem, and an open
   problem past the reminder ring all alert exactly once.
2. HEALS ARE HONEST. The stale-live-CSV heal only counts as a heal when the
   file is actually newer afterwards — `load_league` keeps a stale snapshot
   when the source has nothing new, and that must not be reported as a heal.

HR35 throughout: a probe reports what it found; no probe fabricates a pass.
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import monitor.health_monitor as hm

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_health_"))


# --- 1. state machine: new problem alerts -------------------------------------
st = {}
r = hm._should_alert("quota", "critical", {"quota": ""}, 0, 1000.0)
assert r is True, "new problem must alert"
print("1. new problem alerts: OK")

# --- 2. same problem, next check: SILENT (no spam) ----------------------------
r = hm._should_alert("quota", "critical", {"quota": "quota:critical"}, 500.0,
                     1000.0)
assert r is False, "unchanged problem must NOT re-alert"
print("2. unchanged problem stays silent: OK")

# --- 3. past the reminder ring: alerts again -----------------------------------
_ring = hm.RE_ALERT_AFTER_SECONDS
r = hm._should_alert("quota", "critical", {"quota": "quota:critical"}, 0.0,
                     _ring + 60.0)
assert r is True, "open problem past RE_ALERT_AFTER_SECONDS must re-alert"
r = hm._should_alert("quota", "critical", {"quota": "quota:critical"}, 0.0,
                     _ring - 60.0)
assert r is False, "open problem inside the ring stays silent"
print("3. reminder ring re-alerts an open problem: OK")

# --- 4. resolution alerts exactly once -----------------------------------------
r = hm._should_alert("quota", "ok", {"quota": "quota:critical"}, 500.0, 1000.0)
assert r is True, "resolution (was failing, now ok) must alert"
r = hm._should_alert("quota", "ok", {"quota": "quota:ok"}, 500.0, 1000.0)
assert r is False, "was-ok stays silent"
print("4. resolution alerts once, stays silent after: OK")

# --- 5. severity escalation is a change (warn -> critical) ---------------------
r = hm._should_alert("quota", "critical", {"quota": "quota:warn"}, 500.0, 1000.0)
assert r is True, "warn -> critical is a state change"
print("5. severity escalation alerts: OK")

# --- 6. _states_match gives stable keys -----------------------------------------
assert hm._states_match("x", "ok") == ""
assert hm._states_match("x", "warn") == "x:warn"
print("6. state keys stable: OK")


# --- 7. run_check state file round-trip + change detection ----------------------
def fake_probes():
    """A probe that flips: first check critical, then ok."""
    state = {"first": True}

    def _probe():
        if state["first"]:
            state["first"] = False
            return hm._crit("flaky", "something broke")
        return hm._ok("flaky", "fixed now")

    return _probe


orig = hm.ALL_PROBES
try:
    hm.ALL_PROBES = (("flaky", fake_probes()),)
    sp = _tmp / "state.json"
    # check 1: fails -> alert would fire
    results, alerted = hm.run_check(state_path=sp, alert=False, now=1000.0)
    assert any(not r.is_fine() for r in results)
    st = hm._load_state(sp)
    assert st.get("flaky") == "flaky:critical"
    # check 2: ok now -> state file records the resolution
    results2, _ = hm.run_check(state_path=sp, alert=False, now=2000.0)
    assert all(r.is_fine() for r in results2)
    st2 = hm._load_state(sp)
    assert st2.get("flaky") == ""
    print("7. run_check updates state file through a change: OK")
finally:
    hm.ALL_PROBES = orig


# --- 8. heal honesty: a NON-refreshing file is NOT a heal -----------------------
import data.football_data_source as fds
_csv = _tmp / "Fake_League_all.csv"


def _fake_load_league_stale(league, season, cache_dir=None):
    """Owner keeps the stale snapshot (source has nothing new): file unchanged."""
    return [], []


def _fake_load_league_refresh(league, season, cache_dir=None):
    """A real download: the file is rewritten, mtime moves."""
    _csv.write_text("fresher", encoding="utf-8")
    return [], []


orig_load = fds.load_league
try:
    _csv.write_text("stale", encoding="utf-8")
    fds.load_league = _fake_load_league_stale
    healed = hm._heal_stale_live_csv(_csv, "all")
    assert healed is False, "no-change must NOT be reported as a heal"
    fds.load_league = _fake_load_league_refresh
    time.sleep(0.05)
    healed2 = hm._heal_stale_live_csv(_csv, "all")
    assert healed2 is True, "a refresh that moves mtime IS a heal"
    print("8. heal honesty: no-change is not a heal, change is: OK")
finally:
    fds.load_league = orig_load


# --- 9. live season code window --------------------------------------------------
import datetime
# 2026-08 -> season 2627 (Aug YY .. Jul ZZ+1)
assert hm._live_season_code(datetime.date(2026, 8, 1)) == "2627"
# 2026-02 (Feb, before Aug) -> still 2526
assert hm._live_season_code(datetime.date(2026, 2, 1)) == "2526"
# 2027-01 -> 2627 (window runs to Jul 2027)
assert hm._live_season_code(datetime.date(2027, 1, 15)) == "2627"
print("9. live season code window correct: OK")


print("\n✅ ALL HEALTH-MONITOR TESTS PASSED")
