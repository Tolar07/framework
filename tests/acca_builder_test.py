"""ACCA BUILDER + SAME-DAY RULE tests — standing rule 2026-08-09.

The product bet (TODAY'S PICKS, THE CALL, the acca set) draws ONLY from
fixtures kicking off today — nothing else. A fixture with no kickoff date is
never assumed to be today (HR35), so it cannot be in the bet. The acca set is
up to 3 four-leg accas, each leg capital-cleared (ID405 gate opened 2026-08-10:
all five markets — 1X2 Home/Draw/Away, Over/Under 1.5, Over/Under 2.5, BTTS,
Double Chance — are now deployable).

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/acca_builder_test.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from output.produce_bet import BoardFixture, render_daily_recommendation, render_produce_bet
from engine.acca import build_accas, render_acca_block, LEGS_PER_ACCA, MAX_ACCAS
from engine import markets as mkt
from pipeline.odds import FixtureOdds, MarketQuote
from verification.id403 import verify

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _probs(h=0.5, d=0.25, a=0.25, over25=0.5, home="Home FC", away="Away FC"):
    """Fake FixtureProbabilities with the fields build_accas reads (attribute
    access — SimpleNamespace is fine, same pattern as consensus_test)."""
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.4, lambda_away=1.0,
        p_home=h, p_draw=d, p_away=a,
        p_over_15=0.7, p_over_25=over25, p_over_35=0.3, p_btts_yes=0.5,
        modal_scoreline=(1, 0))


def _bf(fixture, probs, day, market_key=None, price=None, sb_draw=None,
        shortlist=True, tier="A"):
    """BoardFixture for the acca paths. Prices via best_market/best_price for
    the fallback, or sb_draw_odds for the SportyBet-first Draw path."""
    name, league = fixture.split(" (")
    return BoardFixture(
        fixture=fixture, probs=probs, verification=verify([]),
        softness_tier=tier, on_deploy_shortlist=shortlist,
        kickoff_date=day, best_market_key=market_key, best_price=price,
        best_model_prob=(probs.p_draw if market_key == mkt.DRAW else
                         (1 - probs.p_over_25) if market_key == mkt.UNDER_25 else None),
        best_mes_ev=0.0, best_market=None, sb_draw_odds=sb_draw)


def _fx(home, away, draw=None, under25=None):
    return FixtureOdds(
        league="Eredivisie", home_team=home, away_team=away, kickoff_utc="",
        draw=MarketQuote(price=draw) if draw is not None else MarketQuote(),
        under25=MarketQuote(price=under25) if under25 is not None else MarketQuote())


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 1. same-day rule: tomorrow's fixtures never enter the acca -------------
board = [
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=3.30),
    _bf("Gamma v Delta (Eredivisie)", _probs(d=0.28), TOMORROW, sb_draw=3.50),
    _bf("Epsilon v Zeta (Eredivisie)", _probs(d=0.26), TODAY, sb_draw=3.80),
    _bf("Eta v Theta (Eredivisie)", _probs(d=0.24), TOMORROW, sb_draw=4.10),
    _bf("Iota v Kappa (Eredivisie)", _probs(d=0.22), TODAY, sb_draw=4.30),
    _bf("Lambda v Mu (Eredivisie)", _probs(d=0.20), TODAY, sb_draw=4.60),
]
accas = build_accas(board, today=TODAY, odds_index=None)
legs1 = {l.fixture for a in accas for l in a.legs}
_check("same-day: only today's fixtures in the acca",
       legs1 == {"Alpha v Beta", "Epsilon v Zeta", "Iota v Kappa", "Lambda v Mu"},
       f"got {legs1}")
_check("same-day: 4 legs, 1 acca when exactly 4 today",
       len(accas) == 1 and accas[0].n_legs == 4, f"got {[(a.label, a.n_legs) for a in accas]}")

# --- 2. HR35: a fixture with no kickoff date is never assumed to be today ----
board_no_date = board + [_bf("Undated v Ghost (Eredivisie)", _probs(d=0.40),
                             None, sb_draw=2.50)]
accas2 = build_accas(board_no_date, today=TODAY, odds_index=None)
legs2 = {l.fixture for a in accas2 for l in a.legs}
_check("HR35: no-date fixture excluded", "Undated v Ghost" not in legs2, f"got {legs2}")

# --- 3. capital gate: ID405 gate opened 2026-08-10 — all five markets deployable
board_gate = [
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=3.30),
    # Away is now deployable (gate open) — should appear in the acca.
    _bf("Blocked v Only (Eredivisie)", _probs(h=0.10, d=0.15, a=0.75),
        TODAY, market_key=mkt.AWAY, price=1.60, sb_draw=None),
]
accas3 = build_accas(board_gate, today=TODAY, odds_index=None)
legs3 = {l.fixture for a in accas3 for l in a.legs}
_check("ID405 gate open: away-priced fixture NOW included", "Blocked v Only" in legs3, f"got {legs3}")
_check("ID405: leg market may be any of the five deployable markets",
       all(l.market_key in mkt.DEPLOYABLE for a in accas3 for l in a.legs))

# --- 4. up to 3 accas, disjoint 4s, ranked by EV ----------------------------
board_rich = [_bf(f"T{i} v A{i} (Eredivisie)", _probs(d=0.20 + i * 0.01, home=f"T{i}", away=f"A{i}"),
                  TODAY, sb_draw=3.0 + i * 0.1) for i in range(12)]
accas4 = build_accas(board_rich, today=TODAY, odds_index=None)
_check("3 accas max, 4 legs each",
       len(accas4) == min(3, len(board_rich) // 4) and all(a.n_legs == 4 for a in accas4),
       f"got {[(a.label, a.n_legs) for a in accas4]}")
_check("ranked: Acca 1 has the strongest conviction (highest EV first)",
       accas4[0].legs[0].ev >= accas4[0].legs[-1].ev)
_check("disjoint accas: no leg repeats across Acca 1/2/3",
       len({l.fixture for a in accas4 for l in a.legs}) == 12)

# --- 5. combined odds = product of prices -----------------------------------
a0 = accas4[0]
expected_odds = 1.0
for l in a0.legs:
    expected_odds *= l.price
_check("combined odds is the product of the leg prices",
       abs(a0.combined_odds - expected_odds) < 1e-9)

# --- 6. fewer than 4 today fixtures -> shortened acca, honestly -------------
board_short = [_bf("Only v One (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=3.30)]
accas6 = build_accas(board_short, today=TODAY, odds_index=None)
_check("shortened acca (never padded with a non-today fixture)",
       len(accas6) == 1 and accas6[0].n_legs == 1, f"got {[(a.label, a.n_legs) for a in accas6]}")
txt6 = render_acca_block(accas6, today=TODAY)
_check("shortened acca labelled honestly",
       "shortened, not padded" in txt6, txt6)

# --- 7. SportyBet price preferred for Draw over the Odds API -----------------
board_sb = [
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY,
        sb_draw=3.30, market_key=mkt.DRAW, price=2.90),
]
odds_index = {("Alpha v Beta", "Away FC"): _fx("Alpha v Beta", "Away FC", draw=3.10)}
accas7 = build_accas(board_sb, today=TODAY, odds_index=odds_index)
_check("SportyBet price wins for Draw when present",
       accas7 and abs(accas7[0].legs[0].price - 3.30) < 1e-9,
       f"got {accas7[0].legs[0].price if accas7 else 'no acca'}")

# --- 8. empty today -> honest NO ACCA block ----------------------------------
txt8 = render_acca_block([], today=TODAY)
_check("no acca renders an honest note (HR35, never fabricated)",
       "NO ACCA" in txt8, txt8)

# --- 9. render_daily_recommendation is same-day too --------------------------
rec = render_daily_recommendation(board)
_check("TODAY'S PICKS: tomorrow's fixtures excluded from the parlay",
       "Gamma v Delta" not in rec and "Eta v Theta" not in rec, rec)

# --- 10. THE CALL in render_produce_bet is today-only ------------------------
call_board = board + [_bf("Tomorrow v Only (Eredivisie)", _probs(d=0.45),
                          TOMORROW, sb_draw=2.20, shortlist=True)]
out10 = render_produce_bet(mode="M", phase="P", leagues_scanned=["Eredivisie"],
                           calibration_count=0, mean_clv=None, data_flags=[],
                           board=call_board)
_check("THE CALL says today's fixtures only", "today's fixtures only" in out10)
_check("THE CALL excludes the tomorrow fixture",
       "PART 1" in out10 and "Tomorrow v Only" not in out10.split("PART 2")[0],
       "tomorrow fixture leaked into the call")

# --- 11. acca set renders at the end of production ---------------------------
_check("render_produce_bet ends with the acca block",
       "4-LEG ACCA" in out10)

print("\n✅ ALL ACCA + SAME-DAY RULE TESTS PASSED")
