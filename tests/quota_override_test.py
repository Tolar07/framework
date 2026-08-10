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

# --- 1. the two floors exist and are ordered correctly ------------------------
assert odds_mod.QUOTA_HARD_FLOOR < odds_mod.QUOTA_FLOOR, \
    "hard floor must be strictly below the price-pull floor"
assert odds_mod.QUOTA_HARD_FLOOR > 0, "must never spend the very last request"
print(f"1. floors ordered: hard={odds_mod.QUOTA_HARD_FLOOR} < "
      f"price={odds_mod.QUOTA_FLOOR}: OK")

_tmp = Path(tempfile.mkdtemp(prefix="olp_xdv_quota_"))
odds_mod.CACHE_DIR = _tmp  # redirect cache writes away from the real data dir


def _run(remaining: int, fixture_capture: bool):
    """fetch_odds with a mocked quota + HTTP layer. Returns True if it fetched,
    raises QuotaExhausted if the guard blocked it."""
    class _Resp:
        status_code = 200
        headers = {"x-requests-remaining": str(remaining)}
        def raise_for_status(self): pass
        def json(self): return []
    with patch.object(odds_mod, "_read_cache", return_value=None), \
         patch.object(odds_mod, "_get_key", return_value="test-key"), \
         patch.object(odds_mod, "check_quota",
                      return_value=(500 - remaining, remaining)), \
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
fx, flags = _run(20, fixture_capture=True)   # 20 < 40 but > 5
assert fx == []  # mocked empty feed, but the guard let it through
print("3. fixture capture allowed at 20 (<40, >5): OK")

# --- 4. even fixture capture stops at the hard floor --------------------------
try:
    _run(3, fixture_capture=True)
    raise SystemExit("fixture capture must never spend the last of the month")
except odds_mod.QuotaExhausted:
    pass
print("4. fixture capture blocked at 3 (hard floor 5): OK")

# --- 5. EFL Cup is whitelisted (unified pool = "ONE", deploy-eligible) + has an odds sport key ----
from engine.softness import WHITELISTED_LEAGUES, softness_tier, ONE_POOL
assert "EFL Cup" in WHITELISTED_LEAGUES, "EFL Cup must be whitelisted"
assert softness_tier("EFL Cup") == ONE_POOL, f"EFL Cup should be '{ONE_POOL}', got {softness_tier('EFL Cup')}"
assert odds_mod.SPORT_KEYS["EFL Cup"] == "soccer_england_efl_cup"
print("5. EFL Cup whitelisted (unified pool 'ONE') + deploy-eligible + odds sport key: OK")

print("\n=== ALL QUOTA OVERRIDE TESTS PASSED ===")