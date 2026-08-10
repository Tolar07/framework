"""Tests for the unified league pool (ID402 softness tiers removed 2026-08-10).

Every whitelisted league is ONE pool — no tier ranking, no deploy cap, no
scan-only classification. softness_tier() returns "ONE" for whitelisted leagues,
"?" otherwise (kept as back-compat storage slot).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import engine.softness as softness
from engine.softness import (softness_tier, is_deploy_eligible, classify,
                             build_deploy_shortlist, WHITELISTED_LEAGUES, ONE_POOL)
from engine.mes import trigger_price, mes_numeric
from dataclasses import dataclass

# --- Unified pool: every whitelisted league returns "ONE" ---
for lg in WHITELISTED_LEAGUES:
    assert softness_tier(lg) == ONE_POOL, f"{lg!r} should be in the unified pool"
    assert is_deploy_eligible(lg) is True, f"{lg!r} should be deploy-eligible"
    c = classify(lg)
    assert c.scan_eligible is True, f"{lg!r} should be scan-eligible"
    assert c.deploy_eligible is True, f"{lg!r} should be deploy-eligible"
    assert c.tier == ONE_POOL, f"{lg!r} tier should be '{ONE_POOL}'"

# Unknown league returns "?" and is excluded (HR34)
assert softness_tier("Not A Real League") == "?"
assert is_deploy_eligible("Not A Real League") is False
c = classify("Not A Real League")
assert c.scan_eligible is False, "HR34: an unratified league must never be scan-eligible"
assert c.deploy_eligible is False, "HR34: an unratified league must never be deploy-eligible"
assert c.tier == "?"

print("Unified pool gating: all 17 whitelisted leagues = 'ONE', deploy-eligible, no cap; unknown = '?' excluded: OK")

# --- ID402 pool cap REMOVED: no cap on deploy shortlist ---
@dataclass
class FakeCandidate:
    softness_tier: str

# 15 candidates (more than old cap of 6) -> all 15 shortlisted
candidates = [FakeCandidate(softness_tier=ONE_POOL) for _ in range(15)]
shortlist = build_deploy_shortlist(candidates)
assert len(shortlist) == 15, f"no cap: expected 15, got {len(shortlist)}"
print(f"No pool cap: 15 candidates -> {len(shortlist)} shortlisted: OK")

# --- HR30 MES trigger price ---
tp = trigger_price(0.60)
assert abs(tp - 1.667) < 0.01, f"breakeven price for 60% should be ~1.667, got {tp}"
print(f"Trigger price for 60% model prob: {tp} (breakeven, no margin) OK")

tp_buffered = trigger_price(0.60, edge_buffer_pct=5)
assert tp_buffered > tp, "a positive edge buffer should raise the required price"
print(f"Trigger price with 5% edge buffer: {tp_buffered} OK")

assert trigger_price(0) is None
assert trigger_price(None) is None
assert trigger_price(1.5) is None  # invalid probability > 1
print("Trigger price refuses invalid probabilities (never fabricates): OK")

mes_val = mes_numeric(0.60, 1.80)
assert abs(mes_val - 0.08) < 0.001, f"EV at 60% and 1.80 odds should be +8%, got {mes_val}"
assert mes_numeric(0.60, None) is None, "MES must be None (not 0 or a guess) when odds aren't ARCHITECT-FED yet"
print(f"MES numeric (60% @ 1.80): {mes_val:+.2%} EV OK")

print("\n=== ALL SOFTNESS/MES TESTS PASSED ===")