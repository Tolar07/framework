"""
Guards the Architect's standing orders (STANDING_ORDERS.md). If any of these
fails, a change has reverted an order the Architect set — restore the order;
do not edit this test unless the Architect has changed the order.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import markets as mkt
from engine import slate
from pipeline.odds_sportybet import SPORTYBET_TOURNAMENT_ID

# 1. Phase 3
assert config.PHASE == 3 and config.CAPITAL_ENABLED, "Order 1: framework is Phase 3"

# 2. All markets open
assert mkt.BLOCKED == {}, f"Order 2: no market may be blocked, found {list(mkt.BLOCKED)}"
assert slate.BLOCKED_DEPLOY_MARKETS == {}, "Order 2: no market may be blocked (slate)"
for k in (mkt.HOME, mkt.DRAW, mkt.AWAY, mkt.OVER_25, mkt.UNDER_25):
    assert k in mkt.DEPLOYABLE, f"Order 2: {k} must be deployable"

# 3. Odds band
assert (slate.DEPLOY_ODDS_MIN, slate.DEPLOY_ODDS_MAX, slate.DEPLOY_ODDS_SAFE) == (1.20, 2.00, 1.50), \
    "Order 3: band is 1.20-2.00, safest 1.50"
assert slate.in_deploy_band(2.00) and not slate.in_deploy_band(2.01)
assert slate.in_deploy_band(1.20) and not slate.in_deploy_band(1.19)

# 4. Winnable picks only
assert slate.DEPLOY_MIN_MODEL_PROB == 0.50, "Order 4: deploy picks must be >= 50% model"

# 5. ID402 cap
assert slate.DEPLOY_POOL_CAP == 6, "Order 5: max 6 deploy singles"

# 6. Delivery schedule
wf = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
assert '"47 20 * * *"' in wf and '"47 5 * * *"' in wf, "Order 6: ~10 PM + ~7 AM Lagos runs"
assert "--only-production --heartbeat" in wf, "Order 6: production board + daily heartbeat"
assert "--next-day" in wf, "Order 6: evening run builds the next day's board"
assert "if: failure()" in wf, "Order 6: failure alert"

# 7. Coverage
assert len(SPORTYBET_TOURNAMENT_ID) == 17 and "UEFA Nations League" in SPORTYBET_TOURNAMENT_ID, \
    "Order 7: 16 leagues + UEFA Nations League"
for lg in SPORTYBET_TOURNAMENT_ID:
    assert slate.is_whitelisted(lg), f"Order 7: {lg} must be whitelisted"

print("standing_orders_test: OK — all Architect standing orders hold")
