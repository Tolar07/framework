"""
Guards the Architect's standing orders (STANDING_ORDERS.md). If any of these
fails, a change has reverted an order the Architect set — restore the order;
do not edit this test unless the Architect has changed the order.
"""
import os as _os
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
    "Order 5: groups never exceed their cap and cover every leg"

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
assert (_lr.MIN_N, _lr.MIN_DAYS, _lr.Z_MIN, _lr.SHRINK, _lr.MAX_SHIFT) == (50, 5, 2.0, 30, 0.10), \
    "Order 22: 50+ results over 5+ match days and a 2-sd gap, shrink 30, shift capped at 10 pts"

# 23. AI Survivor lineage
from engine import survivor as _sv
assert (_sv.OFFSPRING_PER_WIN, _sv.MAX_LINEAGES, _sv.STAKE) == (2, 16, 1.0), \
    "Order 23: win -> 2 offspring, max 16 lineages, stake 1"
_p = {"lineages": [_sv._lineage(bankroll=5)], "last_bred_date": None}
_sv.apply_result(_p, {"lineage_id": _p["lineages"][0]["lineage_id"], "price": 1.4}, "LOSS")
assert not _p["lineages"][0]["alive"], "Order 23: one loss is extinction"
assert (_sv.MIN_CHANCE, _sv.OK_CERTAINTY) == (0.80, ("HIGH", "MEDIUM")), \
    "Order 23: lineage bar — 80%+ chance, HIGH/MEDIUM certainty, else the lineage waits"

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
_bf28 = [pb.BoardFixture("Sociedad B v Granada (La Liga 2)", _fp("Sociedad B", "Granada"), _v,
                         on_deploy_shortlist=True, best_price=1.33),
         pb.BoardFixture("Greece v Germany (UEFA Nations League)", _fp("Greece", "Germany"), _v,
                         on_deploy_shortlist=True, best_price=1.21)]
_bf28[0].kickoff_utc = "2026-10-04T16:30:00.000Z"      # SportyBet's format
_bf28[1].kickoff_utc = None                            # no source gave a time
_b28 = pb.render_canonical_board("Mode A", "Phase 3", ["La Liga 2"], 0, None, [], _bf28)
# Kickoff time on every pick, Lagos time (Architect 2026-09-19: "the country and the time")
assert pb.kickoff(_bf28[0]) == "17:30" and pb.kickoff(_bf28[1]) == "PENDING", \
    "Order 28: kickoff in Lagos time; PENDING when no source gave one (HR35)"
_late = pb.BoardFixture("X v Y (La Liga 2)", None, _v)
_late.kickoff_utc = "2026-10-04T23:30:00Z"
assert pb.kickoff(_late) == "00:30", "Order 28: Lagos is UTC+1 all year"
_late.kickoff_utc = "2026-10-04"
assert pb.kickoff(_late) == "PENDING", "Order 28: a date without a time is not a kickoff time"
assert "KO = kickoff, Lagos time (WAT)" in _b28
_t1, _t2 = _b28.split("TABLE 2 · ")[0], _b28.split("TABLE 2 · ")[1].split("TABLE 3A")[0]
for _part, _name in ((_t1, "TABLE 1"), (_t2, "TABLE 2")):
    assert "Country · League" in _part and "Spain · La Liga 2" in _part, \
        f"Order 28: {_name} shows each pick's country + league"
    _rows = _part.split("\n")
    assert any(r.startswith("KO ") for r in _rows) \
        and any(r.startswith("17:30 ") and "Sociedad B v Granada" in r for r in _rows) \
        and any(r.startswith("PENDING ") and "Greece v Germany" in r for r in _rows), \
        f"Order 28: {_name} shows each kickoff"
_t3 = _b28.split("TABLE 3 · ACCA ROUTE")[1]
assert "Sociedad B v Granada (" in _t3 and "Spain · La Liga 2" in _t3 \
    and "Greece v Germany (\U0001F3C6 UEFA Nations League)" in _t3, \
    "Order 28: every acca leg and THE PICK name the competition"
assert "• 17:30 Sociedad B v Granada (" in _t3, "Order 28: acca legs show the kickoff"

# 29. bet365 board, to the Architect only
from output import bet365_board as _b365
assert _b365.bet365_name(fm.key(34, "", "No"), "A", "B") is None, \
    "Order 29: bet365 offers no 'win to nil — no'"
assert _b365.deploy_at(0.95) == slate.DEPLOY_ODDS_MIN, "Order 29: deploy-at never below 1.20"
assert "bet365_board.render(" in _rd_src and "TELEGRAM_OWNER_CHAT_ID" in _rd_src, \
    "Order 29: built in the same run, sent on its own to the Architect"
assert "TELEGRAM_OWNER_CHAT_ID" in wf, "Order 29: the owner chat reaches the daily run"
_b365_block = _rd_src.split("# bet365 BOARD (standing order 29)")[1].split("# HEARTBEAT")[0]
assert "chat_id=owner_chat" in _b365_block and 'environ.get("TELEGRAM_SUBSCRIBER' not in _b365_block, \
    "Order 29: the bet365 board goes to the Architect's own chat only, never a subscriber"

# 33. Subscribers get everything the Architect gets except the bet365 board
from output import notify as _nt33
for _wfn in ("daily.yml", "news.yml", "supervisor.yml", "watchdog.yml", "weekly.yml"):
    assert "TELEGRAM_SUBSCRIBER_CHAT_IDS" in \
        (ROOT / ".github/workflows" / _wfn).read_text(encoding="utf-8"), \
        f"Order 33: the subscriber secret reaches {_wfn}"
assert "${TELEGRAM_SUBSCRIBER_CHAT_IDS//,/ }" in wf and "-o /dev/null" in wf, \
    "Order 33: the failed-run alert reaches every subscriber, reply not logged"
_sent33: list = []
_env33 = {k: _os.environ.get(k) for k in
          ("TELEGRAM_CHAT_ID", "TELEGRAM_OWNER_CHAT_ID", "TELEGRAM_SUBSCRIBER_CHAT_IDS")}
_send33 = _nt33.send_telegram
try:
    _nt33.send_telegram = lambda body, token=None, chat_id=None: (  # type: ignore[assignment]
        _sent33.append(chat_id) or (chat_id != "3333", ["refused"]))
    _os.environ.update(TELEGRAM_CHAT_ID="1111", TELEGRAM_OWNER_CHAT_ID="9999",
                       TELEGRAM_SUBSCRIBER_CHAT_IDS="2222, 3333,1111,,2222,9999")
    _ok33, _notes33 = _nt33.deliver("board")
    assert _sent33 == [None, "2222", "3333"], \
        f"Order 33: the Architect's chat, then each subscriber once, never the Architect twice: {_sent33}"
    assert _ok33 and "delivered to 1/2 subscriber chat(s)" in _notes33 and \
        any("…3333: NOT delivered" in n for n in _notes33), \
        f"Order 33: a failed subscriber is noted and never fails the send: {_notes33}"
finally:
    _nt33.send_telegram = _send33  # type: ignore[assignment]
    for _k33, _val33 in _env33.items():
        if _val33 is None:
            _os.environ.pop(_k33, None)
        else:
            _os.environ[_k33] = _val33
assert _rd_src.count("notify.send_telegram(") == 1 and \
    "notify.send_telegram(b365_text, chat_id=owner_chat)" in _rd_src, \
    "Order 33: only the bet365 board bypasses the subscribers"
_hb_block = _rd_src.split("# HEARTBEAT")[1]
assert "notify.deliver(hb" in _hb_block, "Order 33: subscribers get the heartbeat"
for _src in ("monitor/supervisor.py", "monitor/run_watchdog.py", "scripts/weekly_review.py",
             "news_check.py"):
    _txt = (ROOT / _src).read_text(encoding="utf-8")
    assert "notify.send_telegram(" not in _txt and \
        ("notify.send_everyone(" in _txt or "notify.deliver(" in _txt), \
        f"Order 33: {_src} reaches the subscribers too"

# 30. 17 Sep spec items kept: Run ID + send gate, NO-DATA line, competition chunks
from output import notify as _nt
_rid = _rd._new_run_id()
assert _nt.board_gate(f"Run ID: {_rid} | x") is None, "Order 30: a board with a Run ID may be sent"
assert _nt.board_gate("Run ID: PENDING") and _nt.board_gate(""), \
    "Order 30: a board without a valid Run ID is never sent"
assert "notify.board_gate(telegram_text)" in _rd_src and "run_id=run_id" in _rd_src, \
    "Order 30: the daily run stamps the board's Run ID and gates the send on it"
_b30 = pb.render_canonical_board(
    "Mode A", "Phase 3", [], 0, None, [],
    [pb.BoardFixture("Sociedad B v Granada (La Liga 2)", _fp("Sociedad B", "Granada"), _v,
                     on_deploy_shortlist=True, best_price=1.33),
     pb.BoardFixture("Lech v Legia (Ekstraklasa)", None, _v)], run_id=_rid)
assert f"Run ID: {_rid}" in _b30 and "Fixtures scanned: 2" in _b30, "Order 30: Run ID header"
_t1_30 = _b30.split("TABLE 2 · ")[0]
assert "Lech v Legia" not in _t1_30.split(pb.FENCE)[1], "Order 30: NO-DATA leaves Table 1"
assert "unresolved — NO DATA — PENDING" in _t1_30 and "Lech v Legia" in _t1_30, \
    "Order 30: NO-DATA fixtures listed on one line under Table 1, never dropped"
_rows = lambda c: "\n".join(f"Comp{c} row {i} " + "x" * 100 for i in range(20))
_parts = _nt._chunk(f"{pb.FENCE}\n{_rows(1)}\n\n{_rows(2)}\n{pb.FENCE}")
assert len(_parts) == 2 and "Comp2" not in _parts[0] and "Comp1" not in _parts[1], \
    "Order 30: a long board splits between competitions, never mid-competition"

# 10/11/24 (2026-10-04): the alternative market and the news-swap pool come from
# EVERY winnable in-band outcome, not just those within 3 pts of the top; a
# swapped pick is BANKER only if it is a straight win.
assert "alts = sorted((c for c in full_pool" in _rd_src \
    and "bf.cand_pool = [c for c in full_pool" in _rd_src, \
    "Order 10: the alternative market comes from the full in-band pool"
assert 'b.tier = "SAFE" if agree else "BOOK"' in _rd_src, \
    "Order 11: a news swap off a straight win drops the BANKER label"

# 31. Alternative-market accas
from engine.learning import family as _fam31
from pipeline.odds import MarketQuote as _MQ
def _c31(win, key, price):
    return (win, 0.0, key, win, win, _MQ(price=price))
_bfs31 = []
for _i in range(6):
    # H0-H2: main pick 82% -> Acca A. H3-H5: main pick 72% (singles only) but
    # a 78% Over 1.5 alternative -> Alt A (order 40: a match in one acca at most).
    _main = 0.82 if _i < 3 else 0.72
    _b = pb.BoardFixture(f"H{_i} v A{_i} (La Liga 2)", _fp(f"H{_i}", f"A{_i}"), _v,
                         on_deploy_shortlist=True, best_market_key="SB:10||Home or Away",
                         best_market="Home or Away", best_price=1.30, best_model_prob=_main)
    _b.cand_pool = [_c31(_main, "SB:10||Home or Away", 1.30),
                    _c31(0.80, "SB:10||Home or Draw", 1.25),
                    _c31(0.78, "SB:18|total=1.5|Over 1.5", 1.28)]
    _bfs31.append(_b)
_alts31 = pb._build_alt_accas(_bfs31)
assert _alts31 and all(_fam31(leg[3]) != "Double chance" for _n, ls, _c in _alts31 for leg in ls), \
    "Order 31: every alt leg is a different market family from the main pick"
assert all(len(ls) <= 3 for _n, ls, _c in _alts31) and _alts31[0][0] == "Alt A"
_b31 = pb.render_canonical_board("Mode A", "Phase 3", [], 0, None, [], _bfs31, alt_codes={"Alt A": "ALT123"})
assert "TABLE 3B · ALT-MARKET ACCAS" in _b31 and "Alt A · code ALT123" in _b31 \
    and "Alt A: ALT123" in _b31.split("\nALL CODES\n")[1], "Order 31: alt accas on the board and in ALL CODES"
assert "_build_alt_accas(deploy)" in _rd_src and "alts=_alt_accas(dep)" in _rd_src, \
    "Order 31: alt accas are booked and recorded every run"

# 32. Shaky picks switch to a steadier market
_b32 = pb.BoardFixture("Netherlands v Serbia (UEFA Nations League)", _fp("Netherlands", "Serbia"),
                       _v, on_deploy_shortlist=True, best_market_key="SB:16|hcp=-3.5|Away (+3.5)",
                       best_price=1.29, best_model_prob=0.76, certainty="LOW", tier="BOOK")
_b32.cand_pool = [
    (0.76, 0.0, "SB:16|hcp=-3.5|Away (+3.5)", 0.86, 0.76, _MQ(price=1.29)),   # the shaky pick
    (0.74, 0.0, "SB:18|total=1.5|Over 1.5", 0.75, 0.73, _MQ(price=1.30)),     # agrees, 2 pts less
    (0.79, 0.0, "SB:10||Home or Away", 0.95, 0.70, _MQ(price=1.25)),          # disagrees: never
    (0.69, 0.0, "SB:29||No", 0.69, 0.69, _MQ(price=1.40))]                     # 7 pts less: too far
_c32 = pb.steadier_pick(_b32)
assert _c32 and _c32[2] == "SB:18|total=1.5|Over 1.5", \
    "Order 32: a shaky pick moves to an agreeing market at most 5 pts less likely"
assert pb.steadier_pick(_b32, no_side=True)[2] == "SB:18|total=1.5|Over 1.5"
assert "_steadier(b, no_side=" in _rd_src and "DRIFT_DEMOTE * 100" in _rd_src \
    and "b.engine_divergence and _tn.pick_side" in _rd_src, \
    "Order 32: drift, model disagreement and LOW certainty each trigger the switch"
_b32.switched_from = "Serbia (+3.5) Asian handicap (model and SportyBet disagree)"
_b32.best_market_key, _b32.best_market = "SB:18|total=1.5|Over 1.5", "Over 1.5 goals"
_t32 = pb.render_canonical_board("Mode A", "Phase 3", [], 0, None, [], [_b32])
assert "⇄ SWITCHED" in _t32 and "was Serbia (+3.5) Asian handicap" in _t32, \
    "Order 32: a switch is shown with the old pick and why"

# 34. Draw guard, team profiles, national Elo
assert (_rd.DRAW_PREF_PP, _rd.DRAW_ALLOWANCE_DEFAULT) == (0.03, 0.008), "Order 34: draw guard"
assert _rd._loses_on_draw("SB:10||Home or Away") and not _rd._loses_on_draw("SB:10||Home or Draw"), \
    "Order 34: 'X or Y' loses on a draw, 1X does not"
from engine import national_elo as _ne
assert _ne.k_factor("FIFA World Cup") > _ne.k_factor("UEFA Nations League") > _ne.k_factor("Friendly")

# 35. Codes frozen at 10pm
from engine import freeze as _fz
assert _fz.DRIFT == 0.05, "Order 35: a frozen leg is replaced only on a 5%+ drift, team news or leaving the board"
assert "if send and frozen is not None:" in _rd_src, \
    "Order 35: a frozen day always sends its check, even when the run produced nothing"

# 36. BTTS calibrated; BTTS-yes / over-goals value picks
from engine import calibration as _cal
assert _cal.btts_yes(0.45) > 0.45 and _cal.btts_yes(0.75) < 0.75, "Order 36(a): BTTS calibrated"
assert "cal.model_prob(market, mkt.model_prob(market, p))" in _rd_src \
    and "md = (cal.model_prob(k, md[0]), md[1])" in _rd_src, \
    "Order 36(a): the calibrated BTTS feeds both selection routes"
assert _rd.VALUE_MIN_EV == 0.02, "Order 36(b): value threshold EV >= 2%"
for _k in ("BTTS_YES", "SB:29||Yes", "OVER_2_5", "SB:18|total=2.5|Over 2.5", "SB:19|total=1.5|Over 1.5"):
    assert _rd._goals_value_key(_k), f"Order 36(b): {_k} is a value-eligible market"
for _k in ("BTTS_NO", "SB:29||No", "UNDER_2_5", "SB:18|total=3.5|Under 3.5", "SB:10||Home or Draw", "1X2_HOME"):
    assert not _rd._goals_value_key(_k), f"Order 36(b): {_k} is not value-eligible"
assert slate.TIER_RANK["BANKER"] < slate.TIER_RANK["VALUE"] < slate.TIER_RANK["BOOK"]
from engine import staking as _stk
assert _stk.PRIORS["VALUE"] < 0, "Order 36(b): VALUE gets the minimal stake until proven"

# 37. Positive-value bets
from types import SimpleNamespace as _NS37
assert pb.VALUE_BET_MIN_EV == 0.02, "Order 37: EV >= +2% on our chance"
def _bf37(fix, src="model", pool=None, best="SB:1||Home"):
    return _NS37(fixture=fix, probs=_NS37(home_team="A", away_team="B"), prob_source=src,
                 best_market_key=best, team_news=None, cand_pool=pool or [], kickoff_utc=None,
                 kickoff_date="2026-10-06")
_p37 = [(0.70, -0.03, "SB:1||Home", 0.72, 0.70, _MQ(price=1.38)),     # the main pick
        (0.61, 0.069, "SB:18|total=3.5|Under 3.5", 0.76, 0.55, _MQ(price=1.76)),
        (0.55, 0.01, "SB:29||Yes", 0.56, 0.54, _MQ(price=1.84)),       # +1%: too little
        (0.56, 0.037, "SB:16|hcp=0.5|Home (+0.5)", 0.71, 0.52, _MQ(price=1.84))]
_v = pb.value_leg(_bf37("A v B (Serie A)", pool=_p37))
assert _v and _v[0] == "SB:18|total=3.5|Under 3.5" and abs(_v[3] - 0.069) < 1e-9, \
    "Order 37: the outcome furthest above fair odds, not the main pick"
assert pb.value_leg(_bf37("A v B (FA Cup)", src="market", pool=_p37)) is None, \
    "Order 37: market-implied fixtures never qualify"
assert pb.value_leg(_bf37("A v B (Serie A)", pool=_p37[:1] + _p37[2:3])) is None
_vs = pb._build_value([_bf37("A v B (Serie A)", pool=_p37), _bf37("C v D (Serie A)", pool=_p37[:1] + _p37[3:])])
assert [n for n, _l, _c in _vs] == ["Value 1", "Value 2"], _vs
# order 40: a Value acca only from 75%+ value legs on matches no other acca holds
_p37b = [(0.78, 0.03, "SB:18|total=3.5|Under 3.5", 0.80, 0.76, _MQ(price=1.32))]
_bs37 = [_bf37("A v B (Serie A)", pool=_p37b), _bf37("C v D (Serie A)", pool=_p37b)]
for _x in _bs37:                     # main picks of 80% -> both in Acca A
    _x.best_market, _x.best_model_prob, _x.certainty = "A to win", 0.80, None
assert [n for n, _l, _c in pb._build_accas(_bs37)] == ["Acca A"]
_vs = pb._build_value(_bs37)
assert [n for n, _l, _c in _vs] == ["Value 1", "Value 2"], \
    "Order 40: value legs on matches the main accas hold stay singles"

# 38. No underdog handicaps in the FA Cup
from engine import full_markets as _fm38
assert "FA Cup" in _rd.NO_DOG_HANDICAP_LEAGUES, "Order 38: FA Cup underdog handicaps are dropped"
for _k in ("SB:16|hcp=-2.5|Away (+2.5)", "SB:16|hcp=1.5|Home (+1.5)", "SB:16|hcp=-0.5|Away (+0.5)",
           "SB:14|hcp=0:2|Away (0:2)", "SB:14|hcp=1:0|Home (1:0)"):
    assert _fm38.is_underdog_handicap(_k), f"Order 38: {_k} gives its side a start"
for _k in ("SB:16|hcp=-1.5|Home (-1.5)", "SB:16|hcp=1.5|Away (-1.5)", "SB:16|hcp=0|Home (0)",
           "SB:14|hcp=0:1|Home (0:1)", "SB:14|hcp=0:1|Draw (0:1)", "SB:10||Home or Draw", "HOME"):
    assert not _fm38.is_underdog_handicap(_k), f"Order 38: {_k} is not an underdog handicap"
import inspect as _in38
_src38 = _in38.getsource(_rd._run)
assert "NO_DOG_HANDICAP_LEAGUES" in _src38 and "is_underdog_handicap" in _src38 and \
    _src38.index("is_underdog_handicap") < _src38.index("DRAW GUARD: mark"), \
    "Order 38: underdog handicaps are dropped before the pick is chosen"

from engine import freeze as _fz38
assert _fz38.forbidden("SB:16|hcp=-2.5|Away (+2.5)", "FA Cup"), \
    "Order 38: a frozen FA Cup underdog handicap is replaced at the next run"

# 39. Losing-market watch, knowledge file and proposals
from engine import loss_watch as _lw39
assert (_lw39.FLAG_MIN_N, _lw39.FLAG_MAX_PL, _lw39.PROPOSE_MIN_N, _lw39.PROPOSE_MAX_PL,
        _lw39.PROPOSE_Z, _lw39.WINDOW_DAYS) == (8, -2.0, 12, -3.0, -1.5, 21), "Order 39: watch thresholds"
_src39 = _in38.getsource(_rd._run)
assert "loss_watch.blocked" in _src39 and _src39.index("loss_watch.blocked") < \
    _src39.index("DRAW GUARD: mark"), "Order 39: approved blocks are dropped before the pick"
assert "loss_line" in _src39, "Order 39: the watch reaches the heartbeat"
from output import telegram_commands as _tc39
assert _tc39.handle("/approve P1").startswith("REFUSED"), \
    "Order 39: a decision without the Architect's chat is refused"

# 40. Accas: 3 legs, 75%+ picks, a match in one acca at most
assert (pb.ACCA_MIN, pb.ACCA_MAX, pb.ACCA_LEG_MIN) == (3, 3, 0.75), "Order 40: 3-leg accas of 75%+ picks"
_bfs40 = [pb.BoardFixture(f"P{_i} v Q{_i} (Serie A)", _fp(f"P{_i}", f"Q{_i}"), _v,
                          on_deploy_shortlist=True, best_market="P to win",
                          best_model_prob=_p, certainty=_c)
          for _i, (_p, _c) in enumerate([(0.86, "HIGH"), (0.85, "HIGH"), (0.84, "HIGH"),
                                         (0.80, "LOW"), (0.79, "LOW"), (0.77, "LOW"),
                                         (0.76, "LOW"), (0.70, "LOW"), (0.65, "HIGH")])]
_s40, _a40 = pb._build_safe3(_bfs40), pb._build_accas(_bfs40)
_all40 = [l[0].fixture for _n, ls, _c in _s40 + _a40 for l in ls]
assert len(_all40) == len(set(_all40)) == 7, "Order 40: every 75%+ pick in exactly one acca"
assert not any(f.startswith(("P7 ", "P8 ")) for f in _all40), "Order 40: picks under 75% stay singles"
assert all(len(ls) <= 3 for _n, ls, _c in _s40 + _a40), "Order 40: at most 3 legs an acca"

# 41. NBA board (live test since 2026-10-07)
from engine import nba_value as _nv41
assert (_nv41.MIN_EV_WINNER, _nv41.MIN_EV_LINE, _nv41.MAX_EV, _nv41.BAND) == (0.03, 0.05, 0.25, (1.20, 2.00)), \
    "Order 41: NBA picks only above the fair price; stale gaps left out"
_nba41 = (ROOT / "run_nba.py").read_text(encoding="utf-8")
assert "notify.send_telegram(text, chat_id=owner)" in _nba41 and "send_everyone" not in _nba41, \
    "Order 41: the NBA board goes to the Architect's own chat only"
assert "python run_nba.py" in wf, "Order 41: the NBA board runs with the evening board"
assert "LIVE TEST" in _nba41 and "PAPER BOARD" not in _nba41 and "place it by hand" in _nba41, \
    "Orders 26/41 (2026-10-07): the NBA board is a live test, placed by hand from its codes"

print("standing_orders_test: OK — all Architect standing orders hold")
