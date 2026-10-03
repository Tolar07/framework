"""Tests for data/retry.py — the shared retry + circuit-breaker layer.

No network: requests is patched with a fake transport. Proves:
  1. Exponential backoff on transient failures (429, 5xx), then success.
  2. Deterministic 4xx is NOT retried (wastes no quota).
  3. Circuit breaker opens after N failures and refuses calls while OPEN.
  4. Breaker half-opens after cooldown to probe recovery.
  5. Breaker recovers to CLOSED on a successful probe.
"""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import retry as rt  # noqa: E402

BREAKER_NAME = "test_breaker"
# Fresh breaker per test to avoid state bleed across sections.
def _fresh_breaker():
    rt.BREAKERS.pop(BREAKER_NAME, None)
    return rt.get_breaker(BREAKER_NAME)


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")
    def json(self):
        return self._payload


def _patch_transport(sequence):
    """Fake requests.request returning each response in `sequence` in order."""
    it = iter(sequence)

    def fake_request(*a, **k):
        try:
            return next(it)
        except StopIteration:
            return _Resp(200)
    return patch("data.retry.requests.request", side_effect=fake_request)


# --- 1. transient 429 then success -> retried, no error -----------------------
calls = {"n": 0}

def _flaky_429(*a, **k):
    calls["n"] += 1
    return _Resp(429) if calls["n"] < 3 else _Resp(200)

with patch("data.retry.requests.request", side_effect=_flaky_429), \
        patch("data.retry._sleep_backoff"):
    resp = rt.get("https://example.com/x")
assert calls["n"] == 3, f"two retries then success: {calls['n']}"
assert resp.status_code == 200
print("1. transient 429 -> exponential backoff retries, then succeeds: OK")

# --- 2. 5xx server error -> retried ------------------------------------------
calls = {"n": 0}

def _flaky_500(*a, **k):
    calls["n"] += 1
    return _Resp(503) if calls["n"] < 2 else _Resp(200)

with patch("data.retry.requests.request", side_effect=_flaky_500), \
        patch("data.retry._sleep_backoff"):
    resp = rt.get("https://example.com/y")
assert calls["n"] == 2, f"one retry then success: {calls['n']}"
print("2. transient 5xx -> retried: OK")

# --- 3. deterministic 404 -> NOT retried (wastes no quota) --------------------
calls = {"n": 0}

def _perm_404(*a, **k):
    calls["n"] += 1
    return _Resp(404)

with patch("data.retry.requests.request", side_effect=_perm_404), \
        patch("data.retry._sleep_backoff"):
    try:
        rt.get("https://example.com/nope")
        raise SystemExit("404 must raise")
    except Exception:
        pass
assert calls["n"] == 1, f"404 must be a single call, got {calls['n']}"
print("3. deterministic 4xx -> no retry (single call): OK")

# --- 4. circuit breaker opens after failure_threshold -------------------------
_fresh_breaker()
breaker = rt.get_breaker(BREAKER_NAME)
with patch("data.retry.requests.request", side_effect=_perm_404), \
        patch("data.retry._sleep_backoff"):
    for _ in range(breaker.failure_threshold + 1):
        try:
            rt.get_protected("https://example.com/z", BREAKER_NAME)
        except Exception:
            pass
assert breaker.state == "OPEN", f"breaker must be OPEN, is {breaker.state}"
print("4. breaker OPENS after consecutive failures: OK")

# --- 5. OPEN breaker refuses calls immediately (no transport hit) -------------
calls = {"n": 0}

def _should_not_be_called(*a, **k):
    calls["n"] += 1
    return _Resp(200)

with patch("data.retry.requests.request", side_effect=_should_not_be_called):
    try:
        rt.get_protected("https://example.com/refused", BREAKER_NAME)
        raise SystemExit("OPEN breaker must refuse the call")
    except RuntimeError as e:
        assert "OPEN" in str(e)
assert calls["n"] == 0, "refused call must not reach the transport"
print("5. OPEN breaker refuses calls before the network: OK")

# --- 6. after cooldown, breaker half-opens and probes -------------------------
breaker._opened_at = time.monotonic() - breaker.cooldown_seconds - 1
assert breaker.state == "HALF_OPEN", f"after cooldown must be HALF_OPEN: {breaker.state}"

# probe fails -> back to OPEN
with patch("data.retry.requests.request", side_effect=_perm_404), \
        patch("data.retry._sleep_backoff"):
    try:
        rt.get_protected("https://example.com/probe1", BREAKER_NAME)
    except Exception:
        pass
assert breaker.state == "OPEN", "failed probe must reopen the breaker"
print("6. failed HALF_OPEN probe -> back to OPEN: OK")

# cooldown again, probe succeeds -> CLOSED
breaker._opened_at = time.monotonic() - breaker.cooldown_seconds - 1
with patch("data.retry.requests.request", return_value=_Resp(200)):
    resp = rt.get_protected("https://example.com/probe2", BREAKER_NAME)
assert breaker.state == "CLOSED", f"successful probe must close the breaker: {breaker.state}"
assert resp.status_code == 200
print("7. successful HALF_OPEN probe -> breaker CLOSED: OK")

print("\n✅ ALL RETRY-MODULE TESTS PASSED")
