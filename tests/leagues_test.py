"""Tests for the unified league pool (ID402 softness tiers removed 2026-08-11).

Every whitelisted league is ONE pool — no tier ranking, no deploy cap, no
scan-only classification. `is_deploy_eligible()` is the single gate: a league
on the ID401 whitelist is deploy-eligible; anything else is excluded (HR34).
"""
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.leagues import WHITELISTED_LEAGUES, build_deploy_shortlist, is_deploy_eligible
from engine.mes import mes_numeric, trigger_price

# --- Unified pool: every whitelisted league is deploy-eligible ---
for lg in WHITELISTED_LEAGUES:
    assert is_deploy_eligible(lg) is True, f"{lg!r} should be deploy-eligible"

# Unknown league excluded (HR34)
assert is_deploy_eligible("Not A Real League") is False

print(f"Unified pool gating: all {len(WHITELISTED_LEAGUES)} whitelisted "
      "leagues deploy-eligible; unknown excluded: OK")

# --- No pool cap: build_deploy_shortlist returns everything gate-cleared ---
@dataclass
class FakeCandidate:
    pass

# 15 candidates (more than old cap of 6) -> all 15 shortlisted
candidates = [FakeCandidate() for _ in range(15)]
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

print("\n=== ALL LEAGUES/MES TESTS PASSED ===")
