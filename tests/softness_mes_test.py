import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.softness import softness_tier, is_deploy_eligible, classify, build_deploy_shortlist, DEPLOY_POOL_CAP
from engine.mes import trigger_price, mes_numeric
from dataclasses import dataclass

# --- softness tiers ---
assert softness_tier("Eredivisie") == "A"
assert softness_tier("Scottish Premiership") == "B"
assert softness_tier("Premier League") == "D"
assert softness_tier("Not A Real League") == "?"

assert is_deploy_eligible("Eredivisie") is True
assert is_deploy_eligible("Scottish Premiership") is True
assert is_deploy_eligible("Premier League") is False   # D tier — scan-only despite being a big league
assert is_deploy_eligible("Championship") is False      # C tier — scan-only

c = classify("Not A Real League")
assert c.scan_eligible is False, "HR34: an unratified league must never scan-eligible"
print("Softness tier gating: OK")

# --- ID402 pool cap ---
@dataclass
class FakeCandidate:
    softness_tier: str

# 8 deploy-eligible candidates should cap at 6 (ID402 hard cap)
candidates = [FakeCandidate(softness_tier="A") for _ in range(8)]
shortlist = build_deploy_shortlist(candidates)
assert len(shortlist) == DEPLOY_POOL_CAP == 6
print(f"ID402 pool cap: {len(candidates)} candidates -> {len(shortlist)} shortlisted (cap={DEPLOY_POOL_CAP}) OK")

# A scan-only (tier C) candidate must never appear in the shortlist even if included
mixed = [FakeCandidate(softness_tier="A"), FakeCandidate(softness_tier="C"),
         FakeCandidate(softness_tier="B")]
shortlist2 = build_deploy_shortlist(mixed)
assert all(c.softness_tier in ("A", "B") for c in shortlist2)
assert len(shortlist2) == 2
print("Tier C excluded from deploy shortlist: OK")

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

print("\n✅ ALL SOFTNESS/MES TESTS PASSED")
