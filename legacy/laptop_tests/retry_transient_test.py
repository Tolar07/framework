"""Auto-retry tests — _retry_transient in run_daily.

A transient network blip (connection reset, DNS, timeout) must be retried once
so it does not degrade the board to NO DATA — PENDING. Only transient
exceptions are retried: quota exhaustion, logic errors and any other failure
pass straight through to the caller's own guard."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_daily import _retry_transient

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_retry_"))
_runlog = _tmp / "daily_test.log"
_runlog.write_text("", encoding="utf-8")


# --- 1. transient error -> retried once, then succeeds ------------------------
calls = {"n": 0}
def flaky():
    calls["n"] += 1
    if calls["n"] == 1:
        raise TimeoutError("connection reset")
    return "ok"
r = _retry_transient(flaky, "test", _runlog, delay=0)
assert r == "ok" and calls["n"] == 2, f"must retry once then succeed: {calls}"
assert "retrying once" in _runlog.read_text(encoding="utf-8")
print("1. transient -> one retry, succeeds: OK")

# --- 2. persistent transient -> raises (caller's guard takes over) ------------
calls = {"n": 0}
def fail2():
    calls["n"] += 1
    raise OSError("dns failure")
try:
    _retry_transient(fail2, "test", _runlog, delay=0)
    raise SystemExit("should have raised")
except OSError:
    assert calls["n"] == 2, f"exactly one retry: {calls}"
print("2. persistent transient -> exactly one retry then raises: OK")

# --- 3. non-transient (logic error) -> NO retry, passes through ---------------
calls = {"n": 0}
def logic():
    calls["n"] += 1
    raise ValueError("bad data")
try:
    _retry_transient(logic, "test", _runlog, delay=0)
    raise SystemExit("should have raised")
except ValueError:
    assert calls["n"] == 1, f"logic error must not retry: {calls}"
print("3. logic error passes through, no retry: OK")

# --- 4. success first time -> single call, no log entry ----------------------
calls = {"n": 0}
def ok():
    calls["n"] += 1
    return "ok"
assert _retry_transient(ok, "test", _runlog) == "ok" and calls["n"] == 1
print("4. normal success -> single call: OK")

# --- 5. requests connection error (the real-world class) ----------------------
import requests
calls = {"n": 0}
def reqfail():
    calls["n"] += 1
    raise requests.exceptions.ConnectionError("refused")
try:
    _retry_transient(reqfail, "test", _runlog, delay=0)
except requests.exceptions.ConnectionError:
    assert calls["n"] == 2
print("5. requests.ConnectionError -> one retry then raises: OK")

print("\n✅ ALL RETRY TESTS PASSED")
