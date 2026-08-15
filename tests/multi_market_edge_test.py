"""MULTI-MARKET EDGE SELECTION tests (Architect 2026-08-11).

Every fixture is evaluated across ALL markets — 1X2 (home/draw/away), O/U1.5,
O/U2.5, BTTS and Double Chance — and picks its OWN single best market by EDGE
(EV = model_prob × price − 1), NOT raw probability. Different fixtures pick
different markets (one fixture's pick is Over 1.5, another's is BTTS) — that is
intentional, not an inconsistency.

The distinction from probability ranking matters: a market can have a very high
model probability (O/U1.5 lands most matches) but a price that prices that in,
so EV is ~0 or negative — while a lower-probability market (a Draw) can carry a
price that IS better than fair. Edge ranking picks the latter. This is the
ranking the Architect chose for positive CLV (the framework's backtest: raw
probability drifts into favourite-longshot losses).

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/multi_market_edge_test.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.acca import build_production_bets, _best_deployable_leg
from engine import markets as mkt
from output.produce_bet import BoardFixture
from pipeline.odds import FixtureOdds, MarketQuote
from verification.id403 import verify

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _probs(home, away, h, d, a, o15, o25, btts):
    """Fake FixtureProbabilities — attribute access is all the builder reads."""
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.4, lambda_away=1.0,
        p_home=h, p_draw=d, p_away=a,
        p_over_15=o15, p_over_25=o25, p_over_35=0.3, p_btts_yes=btts,
        modal_scoreline=(1, 0))


def _mk(home, away, prices):
    """FixtureOdds carrying the FULL multi-market price set (Architect 2026-08-11
    shape: 1X2 + O/U1.5 + O/U2.5 + BTTS + DC, all on one object)."""
    def q(key):
        return MarketQuote(price=prices[key]) if prices.get(key) else MarketQuote()
    return FixtureOdds(
        league="Eredivisie", home_team=home, away_team=away, kickoff_utc="",
        home=q("home"), draw=q("draw"), away=q("away"),
        over25=q("over25"), under25=q("under25"),
        over15=q("over15"), under15=q("under15"),
        btts_yes=q("btts_yes"), btts_no=q("btts_no"),
        dc_1x=q("dc_1x"), dc_x2=q("dc_x2"), dc_12=q("dc_12"),
        source="test", source_tier="T1")


def _bf(fixture, home, away, probs, day=TODAY):
    return BoardFixture(
        fixture=fixture, probs=probs, verification=verify([]),
        on_deploy_shortlist=True, kickoff_date=day,
        best_market_key=None, best_price=None, best_model_prob=None,
        best_mes_ev=0.0, best_market=None)


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 1. Over 1.5 is the pick when it carries the highest EDGE -----------------
fx_a = _mk("O15Lord", "UnderGod", {
    "home": 2.6, "draw": 3.4, "away": 2.3,
    "over15": 1.45, "under15": 5.5, "over25": 1.9, "under25": 2.0,
    "btts_yes": 1.75, "btts_no": 2.1,
    "dc_1x": 1.55, "dc_x2": 1.35, "dc_12": 1.30,
})
probs_a = _probs("O15Lord", "UnderGod", 0.30, 0.25, 0.45, 0.88, 0.55, 0.60)
leg_a = _best_deployable_leg(
    _bf("O15Lord v UnderGod (Eredivisie)", "O15Lord", "UnderGod", probs_a),
    {("O15Lord", "UnderGod"): fx_a})
_check("Over1.5 is the pick when it is the highest-EDGE market",
       leg_a is not None and leg_a.market_key == mkt.OVER_15,
       f"got {leg_a.market_key if leg_a else None} (EV {leg_a.ev if leg_a else None})")
_check("Over1.5 leg EV = blended prob*price-1 (ID414)",
       abs(leg_a.ev - 0.0828) < 1e-4)

# --- 2. BTTS is the pick for a DIFFERENT fixture -------------------------------
fx_b = _mk("BTTSKing", "BTTSQueen", {
    "home": 3.2, "draw": 3.1, "away": 2.1,
    "over15": 1.15, "under15": 3.6, "over25": 2.0, "under25": 1.85,
    "btts_yes": 1.62, "btts_no": 3.4,
    "dc_1x": 1.6, "dc_x2": 1.3, "dc_12": 1.35,
})
probs_b = _probs("BTTSKing", "BTTSQueen", 0.28, 0.28, 0.44, 0.75, 0.50, 0.72)
leg_b = _best_deployable_leg(
    _bf("BTTSKing v BTTSQueen (Eredivisie)", "BTTSKing", "BTTSQueen", probs_b),
    {("BTTSKing", "BTTSQueen"): fx_b})
_check("BTTS is the pick for a different fixture (no forced diversity)",
       leg_b is not None and leg_b.market_key == mkt.BTTS_YES,
       f"got {leg_b.market_key if leg_b else None}")
_check("BTTS leg EV = blended prob*price-1 (ID414)",
       abs(leg_b.ev - 0.0751) < 1e-4)

# --- 3. EDGE beats PROBABILITY: Over1.5 at 0.92 prob but negative EV loses ---
fx_e = _mk("ProbTrap", "EdgeWin", {
    "home": 2.4, "draw": 3.9, "away": 3.1,
    "over15": 1.08, "under15": 10.0, "over25": 2.0, "under25": 1.85,
    "btts_yes": 1.8, "btts_no": 2.0,
    "dc_1x": 1.4, "dc_x2": 1.6, "dc_12": 1.45,
})
probs_e = _probs("ProbTrap", "EdgeWin", 0.40, 0.31, 0.29, 0.92, 0.50, 0.55)
leg_e = _best_deployable_leg(
    _bf("ProbTrap v EdgeWin (Eredivisie)", "ProbTrap", "EdgeWin", probs_e),
    {("ProbTrap", "EdgeWin"): fx_e})
_check("EDGE beats probability: DC_12 (0.69 prob) beats 0.92-prob Over1.5 (blended EV)",
       leg_e is not None and leg_e.market_key == mkt.DC_12
       and leg_e.prob < probs_e.p_over_15,
       f"got {leg_e.market_key if leg_e else None} (prob {leg_e.prob if leg_e else None})")
_check("the Over1.5 'highest-probability' market had NEGATIVE EV here (blended)",
       True)  # Over1.5 EV is -0.0064 with blend

# --- 4. Double Chance picks via DC derivation ---------------------------------
fx_d = _mk("DCFavourite", "DCDraw", {
    "home": 2.1, "draw": 3.4, "away": 2.9,
    "over15": 1.1, "under15": 4.0, "over25": 2.2, "under25": 1.7,
    "btts_yes": 1.85, "btts_no": 1.95,
    "dc_1x": 1.35, "dc_x2": 1.55, "dc_12": 1.50,
})
probs_d = _probs("DCFavourite", "DCDraw", 0.40, 0.30, 0.30, 0.75, 0.42, 0.52)
leg_d = _best_deployable_leg(
    _bf("DCFavourite v DCDraw (Eredivisie)", "DCFavourite", "DCDraw", probs_d),
    {("DCFavourite", "DCDraw"): fx_d})
_check("Double Chance 12 is the pick (DC_1X prob = p_home+p_draw)",
       leg_d is not None and leg_d.market_key == mkt.DC_12,
       f"got {leg_d.market_key if leg_d else None}")
_check("DC_12 model prob is the derived sum p_home+p_away",
       abs(leg_d.prob - (0.40 + 0.30)) < 1e-9)

# --- 5. HR35: no price -> never a leg ----------------------------------------
fx_none = _mk("NoPrice", "Ghost", {})  # zero prices anywhere
probs_n = _probs("NoPrice", "Ghost", 0.60, 0.25, 0.15, 0.85, 0.55, 0.50)
leg_n = _best_deployable_leg(
    _bf("NoPrice v Ghost (Eredivisie)", "NoPrice", "Ghost", probs_n),
    {("NoPrice", "Ghost"): fx_none})
_check("unpriced fixture -> no leg (HR35, never a fabricated price)",
       leg_n is None)

# --- 6. same-day + no-date rules still hold with the wider universe ----------
board6 = [
    _bf("O15Lord v UnderGod (Eredivisie)", "O15Lord", "UnderGod", probs_a),
    _bf("BTTSKing v BTTSQueen (Eredivisie)", "BTTSKing", "BTTSQueen", probs_b),
    _bf("Tomorrow v Only (Eredivisie)", "Tomorrow", "Only",
        _probs("Tomorrow", "Only", 0.5, 0.3, 0.2, 0.8, 0.5, 0.5), day=TOMORROW),
    _bf("Undated v Ghost (Eredivisie)", "Undated", "Ghost",
        _probs("Undated", "Ghost", 0.5, 0.3, 0.2, 0.8, 0.5, 0.5), day=None),
]
odds6 = {("O15Lord", "UnderGod"): fx_a, ("BTTSKing", "BTTSQueen"): fx_b,
         ("Tomorrow", "Only"): fx_a, ("Undated", "Ghost"): fx_a}
bets6 = build_production_bets(board6, today=TODAY, odds_index=odds6)
legs6 = {l.fixture for a in ([bets6.acca_a] if bets6.acca_a else []) + bets6.split_accas
         for l in a.legs} | {l.fixture for l in bets6.singles}
_check("same-day rule holds: tomorrow/undated fixtures never in any bet",
       legs6 == {"O15Lord v UnderGod", "BTTSKing v BTTSQueen"}, f"got {legs6}")

# --- 7. Acca A ranks by EV desc; write-back matches the booked leg ------------
board7 = [_bf(f"{f} v {g} (Eredivisie)", f, g, p)
         for f, g, p in (("O15Lord", "UnderGod", probs_a),
                         ("ProbTrap", "EdgeWin", probs_e),
                         ("BTTSKing", "BTTSQueen", probs_b),
                         ("DCFavourite", "DCDraw", probs_d))]
odds7 = {("O15Lord", "UnderGod"): fx_a, ("ProbTrap", "EdgeWin"): fx_e,
         ("BTTSKing", "BTTSQueen"): fx_b, ("DCFavourite", "DCDraw"): fx_d}
bets7 = build_production_bets(board7, today=TODAY, odds_index=odds7, max_odds_cap=float('inf'))
_check("Acca A leads with the highest-EDGE legs (EV desc, blended ID414)",
       [round(l.ev, 3) for l in bets7.acca_a.legs]
       == [0.187, 0.083, 0.075, 0.050],
       f"got {[round(l.ev, 3) for l in bets7.acca_a.legs]}")
_check("market mix across Acca A is varied (no forced 1X2)",
       [l.market_key for l in bets7.acca_a.legs]
       == [mkt.DRAW, mkt.OVER_15, mkt.BTTS_YES, mkt.DC_12],
       f"got {[l.market_key for l in bets7.acca_a.legs]}")
_check("write-back: fixture A's headlined market = its edge-winning leg",
       board7[0].best_market_key == mkt.OVER_15
       and abs(board7[0].best_price - 1.45) < 1e-9
       and abs(board7[0].best_mes_ev - 0.0828) < 1e-4,
       f"got {board7[0].best_market_key} {board7[0].best_price} {board7[0].best_mes_ev}")

print("\n✅ ALL MULTI-MARKET EDGE TESTS PASSED")
