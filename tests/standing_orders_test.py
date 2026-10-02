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
assert slate.DEPLOY_POOL_CAP is None or slate.DEPLOY_POOL_CAP >= 100, \
    "Order 5: every in-band fixture is a deploy single (Architect 2026-10-02)"
from output.produce_bet import _split_sizes
assert all(4 <= x <= 5 for x in _split_sizes(78, 4, 5)) and sum(_split_sizes(78, 4, 5)) == 78, \
    "Order 5: accas are 4-5 legs and cover every pick"

# 6. Delivery schedule
wf = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
assert '"47 20 * * *"' in wf and '"47 5 * * *"' in wf, "Order 6: ~10 PM + ~7 AM Lagos runs"
assert "--only-production --heartbeat" in wf, "Order 6: production board + daily heartbeat"
assert "date -u -d tomorrow" in wf, "Order 6: evening run builds the next day's board"
assert "sent_${T}_${SLOT}" in wf, "Order 6: each day's board is sent once per slot (no duplicates)"
assert "if: failure()" in wf, "Order 6: failure alert"

# 7. Coverage
for lg in ("UEFA Nations League", "League One", "League Two", "National League", "FA Cup"):
    assert lg in SPORTYBET_TOURNAMENT_ID, f"Order 7: {lg} must be covered"
assert len(SPORTYBET_TOURNAMENT_ID) >= 21, "Order 7: 16 leagues + UNL + English lower tiers + FA Cup"

# 10. Alternative markets open; nothing dropped (market-implied fallback)
for k in (mkt.DC_1X, mkt.DC_X2, mkt.DC_12, mkt.OVER_15, mkt.UNDER_15,
          mkt.OVER_35, mkt.UNDER_35, mkt.BTTS_YES, mkt.BTTS_NO):
    assert k in mkt.DEPLOYABLE, f"Order 10: {k} must be deployable"
from engine.market_implied import implied_probs
from pipeline.odds import FixtureOdds, MarketQuote
q = lambda x: MarketQuote(price=x)
fx = FixtureOdds(league="FA Cup", home_team="A", away_team="B", kickoff_utc="",
                 home=q(2.0), draw=q(3.4), away=q(3.6), over25=q(1.8), under25=q(1.95),
                 over15=q(1.25), under15=q(3.6), over35=q(3.0), under35=q(1.36),
                 btts_yes=q(1.7), btts_no=q(2.0))
ip = implied_probs(fx)
assert ip is not None and abs(ip.p_home + ip.p_draw + ip.p_away - 1) < 1e-9, \
    "Order 10: unrated fixtures are priced market-implied, margin removed"
fx.btts_no = MarketQuote()
assert implied_probs(fx) is None, "Order 9/10: a missing price is never filled with a guess"
assert mkt.settle(mkt.DC_1X, 1, 1) and not mkt.settle(mkt.DC_12, 1, 1)
for lg in SPORTYBET_TOURNAMENT_ID:
    assert slate.is_whitelisted(lg), f"Order 7: {lg} must be whitelisted"

# 11. Consensus tiers
assert (slate.AGREE_PP, slate.BANKER_MIN) == (0.07, 0.70), "Order 11: BANKER = agree within 7pp, >=70%"
assert slate.TIER_RANK["BANKER"] < slate.TIER_RANK["SAFE"] < slate.TIER_RANK["SPLIT"]
from engine.market_implied import market_prob
fx.btts_no = MarketQuote(price=2.0)
assert abs(market_prob(mkt.DC_1X, fx) - (ip.p_home + ip.p_draw)) < 1e-9

# 12. Full market ladder
from engine import full_markets as fm
assert {11, 16, 19, 20, 31, 547, 548} <= set(fm.LADDER_MARKET_IDS), "Order 12: full ladder fetched"
ah = fm.rule_for(16, "hcp=1", "Home (+1.0)")
assert (ah(0, 1), ah(0, 2), ah(1, 1)) == ("push", "lose", "win"), "Order 12: AH settles correctly"
assert fm.settle_key(fm.key(11, "", "Home"), 1, 1) is None, "Order 12: a void is not a win"
assert fm.LINE_TOLERANCE == 0.08

# 13. Recency-weighted domestic models
import orchestrator
assert orchestrator.RECENCY_HALF_LIFE_DAYS == 240.0, "Order 13: half-life 240 days"
assert orchestrator.next_season_code("2526") == "2627"

# 14/15. BOOK tier, certainty and 50%+ accas
assert "BOOK" in slate.TIER_RANK and slate.CERTAINTY_HIGH_PP == 0.03
from types import SimpleNamespace as _NS
from output import produce_bet as pb
_legs = []
for i, (p, c) in enumerate([(0.82, "HIGH"), (0.81, "HIGH"), (0.81, "HIGH"),
                            (0.95, "LOW"), (0.70, "MEDIUM"), (0.70, "MEDIUM"), (0.70, "MEDIUM")]):
    _legs.append(_NS(probs=object(), certainty=c, best_market=f"m{i}", best_model_prob=p,
                     fixture=f"T{i} v U{i} (X)"))
_s3 = pb._build_safe3(_legs)
assert len(_s3) == 1 and all(l[0].certainty == "HIGH" for l in _s3[0][1]), \
    "Order 15: 50%+ accas use high-certainty legs only and stop below 50%"
assert _s3[0][2] >= 0.50

print("standing_orders_test: OK — all Architect standing orders hold")
