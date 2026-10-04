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

# 16-18. Results loop, team news, market anchor
assert (ROOT / ".github/workflows/news.yml").exists(), "Order 17: pre-kickoff check scheduled"
assert "output/picks" in wf, "Order 16: picks ledger is persisted"
assert slate.MODEL_WEIGHT == 0.25, "Order 18: chance = 75% market + 25% model"

# 19. xG blend for the top 5 leagues
from engine import xg_model
import numpy as _np
assert set(xg_model.UNDERSTAT) == {"Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"}
_xr = xg_model.XGRatings([{"date": "2026-09-0%d" % i, "home": h, "away": a, "xh": 2.0, "xa": 0.5}
                          for i, (h, a) in enumerate([("A", "B"), ("B", "A"), ("A", "B"),
                                                      ("B", "A"), ("A", "B"), ("B", "A")], 1)],
                         "2026-10-01")
_m = _xr.matrix("A", "B")
assert _m is not None and abs(_m.sum() - 1) < 1e-9, "Order 19: xG grid is a probability grid"

# 20. Closing-line value capture
import news_check as _nc
assert _nc.CLOSE_WINDOW_MIN == 35, "Order 20: closing price within 35 min of kickoff"

# 21. Staking tied to proven edge
from engine import staking as _st
assert (_st.MAX_STAKE, _st.STOP_UNITS) == (2.0, 6.0), "Order 21: stake cap 2%, stop-loss 6 units"
assert _st.SLIP_STAKES == {"safe3": 0.5, "accas": 0.25, "megas": 0.1}

# 22. Automatic learning from results
from engine import learning as _lr
assert (_lr.MIN_N, _lr.SHRINK, _lr.MAX_SHIFT) == (10, 30, 0.10), \
    "Order 22: 10+ results per segment, shrink 30, shift capped at 10 pts"

# 23. AI Survivor lineage
from engine import survivor as _sv
assert (_sv.OFFSPRING_PER_WIN, _sv.MAX_LINEAGES, _sv.STAKE) == (2, 16, 1.0), \
    "Order 23: win -> 2 offspring, max 16 lineages, stake 1"
_p = {"lineages": [_sv._lineage(bankroll=5)], "last_bred_date": None}
_sv.apply_result(_p, {"lineage_id": _p["lineages"][0]["lineage_id"], "price": 1.4}, "LOSS")
assert not _p["lineages"][0]["alive"], "Order 23: one loss is extinction"

# 24. Value-aware picks + automatic news swap
import run_daily as _rd
assert (_rd.EV_PREF_PP, _rd.NEWS_SWAP_PP) == (0.02, 0.06), \
    "Order 24: value within 2 pts of the top chance; news swap within 6 pts"

# 25. Price drift guard
import news_check as _nc2
assert (_rd.DRIFT_DEMOTE, _nc2.DRIFT_ALERT) == (0.05, 0.05), \
    "Order 25: a pick drifting out 5%+ is demoted (refresh) and alerted (pre-kickoff)"

# 27. Free multi-source verification (fixture check + price check)
import inspect as _insp
from data import espn_fixtures as _espn
from verification.id403 import SOURCE_TRUST as _trust
from pipeline import odds_verify as _ov
_rd_src = _insp.getsource(_rd)
assert "fixture_check.check_board(board)" in _rd_src, \
    "Order 27: every board fixture is checked against ESPN + football-data"
assert "odds_verify.check_prices(" in _rd_src, \
    "Order 27: every SportyBet price on the board's day gets the price check"
assert _trust["espn.com"] in ("T1", "T2") and _trust["football-data.co.uk"] in ("T1", "T2"), \
    "Order 27: ESPN and football-data are trusted (T1/T2) fixture sources"
assert _ov.PRICE_CHECK_TOLERANCE_PP == 5.0, "Order 27: price check = margin-free, 5 pts"
assert "environ" not in _insp.getsource(_espn), \
    "Order 27: ESPN's public scoreboard needs no key (no paid API)"

# 28. Country + league on every pick
from engine import competitions as _cp
for lg in set(slate.WHITELIST_LEAGUES) | set(SPORTYBET_TOURNAMENT_ID):
    assert lg in _cp.COMPETITIONS, f"Order 28: {lg} needs a country + league label"
assert _cp.label("La Liga 2").startswith("Spain · La Liga 2"), "Order 28: club = country · league"
assert _cp.label("UEFA Nations League") == "UEFA Nations League", \
    "Order 28: national teams show the competition"
assert _cp.label("Unknown Cup") == "Unknown Cup", "Order 28: never a guessed country"
from engine.dixon_coles import FixtureProbabilities as _FP
from verification.id403 import VerificationResult as _VR, Tier as _T
_v = _VR(tier=_T.SINGLE_SOURCE, value=1.9, factors={"independent_domains": ["x"]}, note="")
_fp = lambda h, a: _FP(home_team=h, away_team=a, lambda_home=1.6, lambda_away=1.1, p_home=0.6,
                       p_draw=0.2, p_away=0.2, p_over_15=0.78, p_over_25=0.55, p_over_35=0.32,
                       p_btts_yes=0.58)
_b28 = pb.render_canonical_board(
    "Mode A", "Phase 3", ["La Liga 2"], 0, None, [],
    [pb.BoardFixture("Sociedad B v Granada (La Liga 2)", _fp("Sociedad B", "Granada"), _v,
                     on_deploy_shortlist=True, best_price=1.33),
     pb.BoardFixture("Greece v Germany (UEFA Nations League)", _fp("Greece", "Germany"), _v,
                     on_deploy_shortlist=True, best_price=1.21)])
_t1, _t2 = _b28.split("TABLE 2 · ")[0], _b28.split("TABLE 2 · ")[1].split("TABLE 3A")[0]
for _part, _name in ((_t1, "TABLE 1"), (_t2, "TABLE 2")):
    assert "Country · League" in _part and "Spain · La Liga 2" in _part, \
        f"Order 28: {_name} shows each pick's country + league"
_t3 = _b28.split("TABLE 3 · ACCA ROUTE")[1]
assert "Sociedad B v Granada (" in _t3 and "Spain · La Liga 2" in _t3 \
    and "Greece v Germany (\U0001F3C6 UEFA Nations League)" in _t3, \
    "Order 28: every acca leg and THE PICK name the competition"

# 29. bet365 board, to the Architect only
from output import bet365_board as _b365
assert _b365.bet365_name(fm.key(34, "", "No"), "A", "B") is None, \
    "Order 29: bet365 offers no 'win to nil — no'"
assert _b365.deploy_at(0.95) == slate.DEPLOY_ODDS_MIN, "Order 29: deploy-at never below 1.20"
assert "bet365_board.render(" in _rd_src and "TELEGRAM_OWNER_CHAT_ID" in _rd_src, \
    "Order 29: built in the same run, sent on its own to the Architect"
assert "TELEGRAM_OWNER_CHAT_ID" in wf, "Order 29: the owner chat reaches the daily run"

print("standing_orders_test: OK — all Architect standing orders hold")
