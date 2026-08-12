"""api_football_plan probe tests (Architect 2026-08-12).

The plan probe is the GATE that lifts the free-plan guards (2024 history cap,
today±1 odds window, stale plan-error caches). It must fail CLOSED: a missing
key, a network failure, or an unparseable response all read as Free, so a
transient error can never silently open the current-season path.

The /status shape is response.subscription.plan (VERIFIED live 2026-08-12:
"Free"), with response.account.plan.name as the documented dashboard shape.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.api_football_plan as plan_mod


class _Resp:
    def __init__(self, payload):
        self._payload = payload
    def json(self):
        return self._payload


def _sub_response(plan_name: str) -> _Resp:
    """The /status shape — response.subscription.plan (verified live)."""
    return _Resp({"response": {"subscription": {"plan": plan_name,
                                                "end": "2027-08-03T00:00:00+00:00"}}})


def _with_isolated_cache():
    """Point the plan cache at a fresh temp dir so tests never read the real
    probe result (which reflects the .env key, not the mock)."""
    tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_plan_"))
    return mock.patch.object(plan_mod, "PLAN_CACHE_PATH", tmp / "plan.json")


def _fresh_cache():
    """Force a stale cache so every test re-probes (a stale cache is treated
    as absent and re-probed — same fail-closed rule as production)."""
    return mock.patch.object(plan_mod, "PLAN_TTL_SECONDS", -1)


# --- 1. paid response flips the gate OPEN ------------------------------------
with _with_isolated_cache(), _fresh_cache(), \
        mock.patch.object(plan_mod, "_key", return_value="paid-key"), \
        mock.patch.object(plan_mod, "get_protected", return_value=_sub_response("Standard")):
    assert plan_mod.is_paid_plan() is True, "Standard must be paid"
    assert plan_mod.plan_name() == "Standard"
print("1. paid response -> is_paid_plan() True: OK")

# --- 2. free response keeps the gate CLOSED ----------------------------------
with _with_isolated_cache(), _fresh_cache(), \
        mock.patch.object(plan_mod, "_key", return_value="free-key"), \
        mock.patch.object(plan_mod, "get_protected", return_value=_sub_response("Free")):
    assert plan_mod.is_paid_plan() is False, "Free must stay closed"
print("2. free response -> is_paid_plan() False: OK")

# --- 3. network failure fails CLOSED (never opens the gate) ------------------
with _with_isolated_cache(), _fresh_cache(), \
        mock.patch.object(plan_mod, "_key", return_value="key"), \
        mock.patch.object(plan_mod, "get_protected",
                          side_effect=RuntimeError("down")):
    assert plan_mod.is_paid_plan() is False, "network failure must fail closed"
    assert plan_mod.plan_name() == "Free", "honest default is Free"
print("3. network failure -> fail CLOSED (Free): OK")

# --- 4. missing key fails CLOSED ---------------------------------------------
with _with_isolated_cache(), mock.patch.object(plan_mod, "_key",
                                               return_value=None):
    assert plan_mod.is_paid_plan() is False, "no key must fail closed"
print("4. missing key -> fail CLOSED: OK")

# --- 5. unparseable response shape fails CLOSED ------------------------------
with _with_isolated_cache(), _fresh_cache(), \
        mock.patch.object(plan_mod, "_key", return_value="key"), \
        mock.patch.object(plan_mod, "get_protected",
                          return_value=_Resp({"response": {}})):
    assert plan_mod.is_paid_plan() is False, "no plan field must fail closed"
print("5. unparseable shape -> fail CLOSED: OK")

# --- 6. cached plan is served, and a stale cache re-probes -------------------
# A fresh paid cache is served without network; a stale cache is ignored and
# re-probed (the gate is re-checked, never trusted from a week-old read).
tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_plan_"))
cache_path = tmp / "plan.json"
cache_path.write_text(json.dumps({"plan": "Pro", "probed_at": time.time()}),
                      encoding="utf-8")
with mock.patch.object(plan_mod, "PLAN_CACHE_PATH", cache_path), \
        mock.patch.object(plan_mod, "PLAN_TTL_SECONDS", 1000), \
        mock.patch.object(plan_mod, "get_protected",
                          side_effect=AssertionError("must not probe")):
    assert plan_mod.is_paid_plan() is True, "fresh cache served, no network"
# stale cache -> ignored, re-probed
cache_path.write_text(json.dumps({"plan": "Pro", "probed_at": 0.0}),
                      encoding="utf-8")
with mock.patch.object(plan_mod, "PLAN_CACHE_PATH", cache_path), \
        mock.patch.object(plan_mod, "get_protected",
                          return_value=_sub_response("Free")):
    assert plan_mod.is_paid_plan() is False, "stale cache re-probed"
print("6. cache TTL: fresh served, stale re-probed: OK")

print(f"\napi_football_plan_test: ALL 6 PASSED")
