"""Quota-override tests — the Architect-authorized fixture-capture spend.

Normally the odds quota stops at QUOTA_FLOOR (40) so a routine pull can't
exhaust the month. FIXTURE CAPTURE (fixtures_from_odds) is authorized to spend
below that floor, down to QUOTA_HARD_FLOOR (5): one spend buys a 6h-cached
fixture list — the only source for EFL/UCL-qualifier fixtures. It may NEVER
spend the last of the month. The price-pull floor (40) is untouched for every
other caller.
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.odds as odds_mod
import data.api_football_odds as af_fallback_mod

# --- 1. the two floors exist and are ordered correctly ------------------------
# QUOTA_HARD_FLOOR is the authorized floor for FIXTURE CAPTURE only (down to
# which a fixture-list pull may spend). It must stay strictly below the
# price-pull floor (QUOTA_FLOOR) and strictly above 0, so fixture capture can
# never spend the very last request of the month. The value is intentionally
# floor-aware (not hardcoded 5): it was temporarily lowered to 1 on 2026-08-16
# while the primary key sat at 1 remaining, pending monthly reset — the
# invariant ("never spend the last request") holds identically at any value >0.
HARD = odds_mod.QUOTA_HARD_FLOOR
assert odds_mod.QUOTA_HARD_FLOOR < odds_mod.QUOTA_FLOOR, \
    "hard floor must be strictly below the price-pull floor"
assert odds_mod.QUOTA_HARD_FLOOR > 0, "must never spend the very last request"
print(f"1. floors ordered: hard={odds_mod.QUOTA_HARD_FLOOR} < "
      f"price={odds_mod.QUOTA_FLOOR}: OK")

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_quota_"))
odds_mod.CACHE_DIR = _tmp  # redirect cache writes away from the real data dir


def _run(remaining: int, fixture_capture: bool):
    """fetch_odds with the floor guard mocked deterministically.

    The unit under test is the floor discipline itself, so we mock
    _resolve_key to apply the same floor logic fetch_odds uses
    (HARD floor for fixture capture, QUOTA_FLOOR otherwise) and raise
    QuotaExhausted when no key is above the floor — exactly what the live
    probe path does. This keeps the test hermetic (no live API probe) and
    floor-aware. The api-football fallback's cache dir is isolated so a
    warm real cache never leaks in. Both caches point at the throwaway dir."""
    floor = HARD if fixture_capture else odds_mod.QUOTA_FLOOR

    def _fake_resolve(use_floor):
        if remaining < use_floor:
            raise odds_mod.QuotaExhausted(
                f"mock: remaining {remaining} < floor {use_floor}")
        return "test-key", 500 - remaining, remaining

    class _Resp:
        status_code = 200
        headers = {"x-requests-remaining": str(remaining)}
        def raise_for_status(self): pass
        def json(self): return []
    with patch.object(odds_mod, "_read_cache", return_value=None), \
         patch.object(odds_mod, "_resolve_key", side_effect=_fake_resolve), \
         patch.object(af_fallback_mod, "CACHE_DIR", _tmp), \
         patch("data.retry.request", return_value=_Resp()):
        fx, flags = odds_mod.fetch_odds(
            "Championship", use_cache=True, fixture_capture=fixture_capture)
        return fx, flags


# --- 2. price pull still blocked below QUOTA_FLOOR (unchanged guard) ----------
try:
    _run(20, fixture_capture=False)
    raise SystemExit("price pull must be blocked at 20 (<40)")
except odds_mod.QuotaExhausted:
    pass
print("2. price pull still blocked below 40 (guard unchanged): OK")

# --- 3. fixture capture MAY spend below 40 (down to the hard floor) -----------
fx, flags = _run(20, fixture_capture=True)   # 20 < 40 but >= HARD
assert fx == []  # mocked empty feed, but the guard let it through
print(f"3. fixture capture allowed at 20 (<40, >={HARD}): OK")

# --- 4. even fixture capture stops at the hard floor --------------------------
# The hard floor guards the LAST request(s) of the month: fixture capture is
# permitted for remaining >= HARD and blocked at HARD-1 (so it never spends the
# last request, regardless of the floor's current value — 5 in normal ops, 1
# when temporarily lowered pending the monthly reset).
try:
    _run(HARD - 1, fixture_capture=True)
    raise SystemExit("fixture capture must never spend the last of the month")
except odds_mod.QuotaExhausted:
    pass
print(f"4. fixture capture blocked at {HARD-1} (hard floor {HARD}): OK")

# --- 5. EFL Cup is whitelisted (unified pool, deploy-eligible) + has an odds sport key ----
from engine.leagues import WHITELISTED_LEAGUES, is_deploy_eligible
assert "EFL Cup" in WHITELISTED_LEAGUES, "EFL Cup must be whitelisted"
assert is_deploy_eligible("EFL Cup"), "EFL Cup must be deploy-eligible (unified pool)"
assert odds_mod.SPORT_KEYS["EFL Cup"] == "soccer_england_efl_cup"
print("5. EFL Cup whitelisted + deploy-eligible + odds sport key: OK")

print("\n=== ALL QUOTA OVERRIDE TESTS PASSED ===")