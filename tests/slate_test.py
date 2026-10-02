import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.slate import (is_whitelisted, is_deploy_eligible, classify,
                          build_deploy_shortlist, DEPLOY_POOL_CAP, WHITELIST_LEAGUES,
                          in_deploy_band, DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX)
from engine.mes import trigger_price, mes_numeric
from dataclasses import dataclass

# --- whitelist / eligibility (softness tiering RETIRED — all whitelisted
#     leagues are equally deploy-eligible) ---
assert is_whitelisted("Eredivisie") is True
assert is_whitelisted("Not A Real League") is False
# every whitelisted league is deploy-eligible now, incl. former "scan-only" ones
assert is_deploy_eligible("Eredivisie") is True
assert is_deploy_eligible("Premier League") is True       # was tier D — now eligible
assert is_deploy_eligible("Championship") is True         # was tier C — now eligible
assert is_deploy_eligible("Not A Real League") is False   # HR34 default-ban

c = classify("Not A Real League")
assert c.scan_eligible is False and c.deploy_eligible is False, \
    "HR34: an unratified league is neither scan- nor deploy-eligible"
c2 = classify("Ekstraklasa")
assert c2.scan_eligible is True and c2.deploy_eligible is True
assert not hasattr(c2, "tier"), "SlateDecision must no longer carry a softness tier"
print("Whitelist eligibility (no tiers): OK")

# --- ID402 pool cap + conviction ranking ---
@dataclass
class FakeCandidate:
    probs: object = None
    form_support: float = 0.0

# The shortlist honours whatever cap the Architect sets (2026-10-02: lifted to
# 1000 — every in-band fixture), with no tier filtering.
candidates = [FakeCandidate() for _ in range(8)]
shortlist = build_deploy_shortlist(candidates)
assert len(shortlist) == (len(candidates) if DEPLOY_POOL_CAP is None
                          else min(len(candidates), DEPLOY_POOL_CAP))
print(f"ID402 pool cap: {len(candidates)} candidates -> {len(shortlist)} (cap={DEPLOY_POOL_CAP}) OK")

# higher model conviction ranks first
class P:
    def __init__(self, ph):
        self.p_home, self.p_draw, self.p_away = ph, (1 - ph) / 2, (1 - ph) / 2
        self.p_over_15 = 0.5; self.p_btts_yes = 0.5
hi, lo = FakeCandidate(probs=P(0.80)), FakeCandidate(probs=P(0.40))
assert build_deploy_shortlist([lo, hi])[0] is hi, "higher conviction must rank first"
print("Conviction ranking (no league tiering): OK")

# --- HR30 MES trigger price (unchanged) ---
tp = trigger_price(0.60)
assert abs(tp - 1.667) < 0.01, f"breakeven price for 60% should be ~1.667, got {tp}"
tp_buffered = trigger_price(0.60, edge_buffer_pct=5)
assert tp_buffered > tp
assert trigger_price(0) is None and trigger_price(None) is None and trigger_price(1.5) is None
mes_val = mes_numeric(0.60, 1.80)
assert abs(mes_val - 0.08) < 0.001
assert mes_numeric(0.60, None) is None
print("HR30 MES trigger price + numeric: OK")

# --- deploy odds band (Architect: max 2.00, floor 1.20) ---
assert DEPLOY_ODDS_MIN == 1.20 and DEPLOY_ODDS_MAX == 2.00
assert in_deploy_band(1.20) and in_deploy_band(1.50) and in_deploy_band(2.00)
assert not in_deploy_band(1.19), "below the 1.20 floor is out of band"
assert not in_deploy_band(2.01), "above the 2.00 ceiling is out of band"
assert not in_deploy_band(2.40) and not in_deploy_band(7.0)
assert not in_deploy_band(None), "no price is never in band (HR35)"
print(f"Deploy odds band [{DEPLOY_ODDS_MIN:.2f}, {DEPLOY_ODDS_MAX:.2f}]: OK")

print("\n✅ ALL SLATE/MES TESTS PASSED")
