"""ACCA BUILDER + SAME-DAY RULE tests — PRODUCTION INTENT shape (2026-08-10,
ranking 2026-08-11 EDGE).

The product bet (THE CALL, Acca A, the split accas, the singles) draws ONLY
from fixtures kicking off today — nothing else. A fixture with no kickoff date
is never assumed to be today (HR35), so it cannot be in any bet. Each leg is
priced on the live line in a CAPITAL-CLEARED market — every market a fixture
can be scored on (1X2, O/U1.5, O/U2.5, BTTS, Double Chance) that carries a real
price (ID405 scope overridden 2026-08-11 — away may be recommended).

Production shape (OLP_XDV_PRODUCTION_INTENT1.md):
  - Acca A (headline): the top 4-5 HIGHEST-EDGE fixtures, each leg that
    fixture's OWN single best market across the full universe (no forced
    diversity).
  - Acca A fixtures are REMOVED from the pool — a fixture never appears in two
    different bets.
  - Singles: every remaining fixture's natural best market, each with its own
    booking code.
  - The remainder splits into grouped accas of ~4-5 legs each (never one giant
    acca) — but every remainder leg is ALSO a standalone single (intent #6:
    "independent of which accumulator it's ALSO part of").

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/acca_builder_test.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from output.produce_bet import BoardFixture, render_produce_bet
from engine.acca import (build_accas, build_production_bets, build_single_accas,
                         render_production_block, ACCA_A_MAX, HEADLINE_MIN_LEGS)
from engine import markets as mkt
from pipeline.odds import FixtureOdds, MarketQuote
from verification.id403 import verify

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _probs(h=0.5, d=0.25, a=0.25, over25=0.5, home="Home FC", away="Away FC"):
    """Fake FixtureProbabilities with the fields build_production_bets reads
    (attribute access — SimpleNamespace is fine, same pattern as consensus_test)."""
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.4, lambda_away=1.0,
        p_home=h, p_draw=d, p_away=a,
        p_over_15=0.7, p_over_25=over25, p_over_35=0.3, p_btts_yes=0.5,
        modal_scoreline=(1, 0))


def _bf(fixture, probs, day, market_key=None, price=None, sb_draw=None,
        shortlist=True):
    """BoardFixture for the acca paths. Prices via best_market/best_price for
    the fallback, or sb_draw_odds for the SportyBet-first Draw path."""
    name, league = fixture.split(" (")
    return BoardFixture(
        fixture=fixture, probs=probs, verification=verify([]),
        on_deploy_shortlist=shortlist,
        kickoff_date=day, best_market_key=market_key, best_price=price,
        best_model_prob=(probs.p_draw if market_key == mkt.DRAW else
                         (1 - probs.p_over_25) if market_key == mkt.UNDER_25 else None),
        best_mes_ev=0.0, best_market=None, sb_draw_odds=sb_draw)


def _fx(home, away, draw=None, under25=None):
    return FixtureOdds(
        league="Eredivisie", home_team=home, away_team=away, kickoff_utc="",
        draw=MarketQuote(price=draw) if draw is not None else MarketQuote(),
        under25=MarketQuote(price=under25) if under25 is not None else MarketQuote())


def _fx_full(home, away, h, d, a, over25, under25):
    """FixtureOdds with the five base markets priced — lets the builder rank by
    EDGE (EV = prob*price-1) across the priced set. O1.5/BTTS/DC have no price
    here so they are honest scan-only, exactly as on a bare Odds-API pull."""
    return FixtureOdds(
        league="Eredivisie", home_team=home, away_team=away, kickoff_utc="",
        home=MarketQuote(price=h), draw=MarketQuote(price=d),
        away=MarketQuote(price=a), over25=MarketQuote(price=over25),
        under25=MarketQuote(price=under25))


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  ✓ {name}")


# --- 1. same-day rule: tomorrow's fixtures never enter any bet ---------------
board = [
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=3.30),
    _bf("Gamma v Delta (Eredivisie)", _probs(d=0.28), TOMORROW, sb_draw=3.50),
    _bf("Epsilon v Zeta (Eredivisie)", _probs(d=0.26), TODAY, sb_draw=3.80),
    _bf("Eta v Theta (Eredivisie)", _probs(d=0.24), TOMORROW, sb_draw=4.10),
    _bf("Iota v Kappa (Eredivisie)", _probs(d=0.22), TODAY, sb_draw=4.30),
    _bf("Lambda v Mu (Eredivisie)", _probs(d=0.20), TODAY, sb_draw=4.60),
]
bets1 = build_production_bets(board, today=TODAY, odds_index=None)
accas1 = ([bets1.acca_a] if bets1.acca_a else []) + bets1.split_accas
legs1 = {l.fixture for a in accas1 for l in a.legs} | {l.fixture for l in bets1.singles}
_check("same-day: only today's fixtures in any bet",
       legs1 == {"Alpha v Beta", "Epsilon v Zeta", "Iota v Kappa", "Lambda v Mu"},
       f"got {legs1}")
_check("same-day: 4 today fixtures all land in Acca A (acca_a_max=5), no splits/singles",
       bets1.acca_a is not None and bets1.acca_a.n_legs == 4
       and not bets1.split_accas and not bets1.singles,
       f"got {[(a.label, a.n_legs) for a in accas1]} + {len(bets1.singles)} singles")
_check("legacy build_accas returns the same acca set, no singles",
       [a.label for a in build_accas(board, today=TODAY)] == ["Acca A"])

# --- 2. HR35: a fixture with no kickoff date is never assumed to be today ----
board_no_date = board + [_bf("Undated v Ghost (Eredivisie)", _probs(d=0.40),
                             None, sb_draw=2.50)]
bets2 = build_production_bets(board_no_date, today=TODAY, odds_index=None)
legs2 = {l.fixture for a in
         (([bets2.acca_a] if bets2.acca_a else []) + bets2.split_accas)
         for l in a.legs} | {l.fixture for l in bets2.singles}
_check("HR35: no-date fixture excluded", "Undated v Ghost" not in legs2, f"got {legs2}")

# --- 3. each leg = the fixture's OWN highest-probability market ---------------
# Four fixtures, four distinct natural best markets (all five priced via the
# odds index). Selection must follow model probability, not EV or market order.
best_board = [
    _bf("HighOver v LowUnder (Eredivisie)", _probs(h=0.30, d=0.20, a=0.30, over25=0.85),
        TODAY),                                  # OVER_25 @ 0.85
    _bf("DrawLord v DrawLady (Eredivisie)", _probs(h=0.18, d=0.62, a=0.20, over25=0.40),
        TODAY),                                  # DRAW @ 0.62
    _bf("HomeTitan v AwayMouse (Eredivisie)", _probs(h=0.75, d=0.12, a=0.13, over25=0.30),
        TODAY),                                  # HOME @ 0.75
    _bf("UnderKing v OverQueen (Eredivisie)", _probs(h=0.20, d=0.20, a=0.20, over25=0.10),
        TODAY),                                  # UNDER_25 @ 0.90
]
odds_index = {("Home FC", "Away FC"): _fx_full("Home FC", "Away FC",
                                               2.0, 3.5, 4.0, 2.0, 1.8)}
bets3 = build_production_bets(best_board, today=TODAY, odds_index=odds_index)
leg3 = {l.fixture: l for a in
        (([bets3.acca_a] if bets3.acca_a else []) + bets3.split_accas)
        for l in a.legs}
expect_market = {
    "HighOver v LowUnder": mkt.OVER_25,
    "DrawLord v DrawLady": mkt.DRAW,
    "HomeTitan v AwayMouse": mkt.HOME,
    "UnderKing v OverQueen": mkt.UNDER_25,
}
_check("best market: each leg is the fixture's highest-probability market",
       all(leg3[f].market_key == expect_market[f] for f in expect_market),
       f"got { {f: leg3[f].market_key for f in expect_market} }")
_check("best market: leg prob is the model prob of that market",
       abs(leg3["HighOver v LowUnder"].prob - 0.85) < 1e-9
       and abs(leg3["UnderKing v OverQueen"].prob - 0.90) < 1e-9)
_check("edge ranking: Acca A legs sorted by EV desc",
       [round(l.ev, 2) for l in bets3.acca_a.legs] == [1.17, 0.70, 0.62, 0.50],
       f"got {[round(l.ev, 2) for l in bets3.acca_a.legs]}")
_check("EV stays on the leg as information (prob*price-1)",
       all(l.ev is not None for l in bets3.acca_a.legs))

# --- 4. write-back: the CALL/scan pick now equals the booked leg ------------
bf_a = best_board[0]  # HighOver v LowUnder -> OVER_25
_check("write-back: best_market_key/best_market/best_price/best_model_prob/best_mes_ev "
       "set from the leg",
       bf_a.best_market_key == mkt.OVER_25
       and bf_a.best_market == "Over 2.5 goals"
       and abs(bf_a.best_price - 2.0) < 1e-9
       and abs(bf_a.best_model_prob - 0.85) < 1e-9
       and bf_a.best_mes_ev is not None,
       f"got {bf_a.best_market_key} {bf_a.best_market} {bf_a.best_price}")

# --- 5. Acca A = top 5 by confidence; no fixture in two different bets ------
def _conf_board(n, start=0.31):
    return [_bf(f"F{i} v G{i} (Eredivisie)", _probs(d=start - i * 0.01),
                TODAY, sb_draw=3.0 + i * 0.1) for i in range(n)]

board_rich = _conf_board(12)
bets5 = build_production_bets(board_rich, today=TODAY, odds_index=None)
a5 = bets5.acca_a
# With _conf_board's prob/price schedule (draw prob falls 0.01, draw price
# rises 0.1 per fixture) EV is monotonic with prob, so the top-5 by EDGE is
# also the top-5 by probability — the assertion pins the ORDER either way.
_check("Acca A holds the top 5 by edge",
       [round(l.prob, 2) for l in a5.legs] == [0.31, 0.30, 0.29, 0.28, 0.27],
       f"got {[round(l.prob, 2) for l in a5.legs]}")
_check("Acca A has no duplicate fixture",
       len({l.fixture for l in a5.legs}) == 5)
rem_fixtures = {l.fixture for a in bets5.split_accas for l in a.legs} \
    | {l.fixture for l in bets5.singles}
_check("Acca A fixtures are REMOVED from the pool (never in two bets)",
       len(a5.legs) == 5 and not ({l.fixture for l in a5.legs} & rem_fixtures),
       f"Acca A leaked into the remainder: "
       f"{ {l.fixture for l in a5.legs} & rem_fixtures }")
_check("split accas are disjoint from each other",
       len({l.fixture for a in bets5.split_accas for l in a.legs}) == 7)
_check("singles == the remainder legs (each is ALSO a standalone slip, intent #6)",
       {l.fixture for l in bets5.singles}
       == {l.fixture for a in bets5.split_accas for l in a.legs},
       "singles should be exactly the split-acca legs")

# --- 6. chunking: remainder splits into ~4-5 leg groups, never one giant acca
def _split_sizes(n):
    b = _conf_board(n)
    pb = build_production_bets(b, today=TODAY, odds_index=None)
    return [a.n_legs for a in pb.split_accas], len(pb.singles)

_check("chunk 6 -> Acca A(5) + singles only (rem 1, no split acca)",
       _split_sizes(6) == ([], 1), f"got {_split_sizes(6)}")
_check("chunk 8 -> [3] (rem 3 one group), singles=3",
       _split_sizes(8) == ([3], 3), f"got {_split_sizes(8)}")
_check("chunk 12 -> [4,3], singles=7",
       _split_sizes(12) == ([4, 3], 7), f"got {_split_sizes(12)}")
_check("chunk 13 -> [4,4], singles=8",
       _split_sizes(13) == ([4, 4], 8), f"got {_split_sizes(13)}")
_check("chunk 15 -> [5,5], singles=10",
       _split_sizes(15) == ([5, 5], 10), f"got {_split_sizes(15)}")
_check("chunk 18 -> [5,4,4], singles=13",
       _split_sizes(18) == ([5, 4, 4], 13), f"got {_split_sizes(18)}")
_check("every split group is 3-6 legs (never one giant acca)",
       all(3 <= s <= 6 for s in _split_sizes(24)[0]), f"got {_split_sizes(24)}")

# --- 7. combined odds = product of prices; combined prob = product of probs --
a0 = bets5.acca_a
expected_odds = 1.0
expected_prob = 1.0
for l in a0.legs:
    expected_odds *= l.price
    expected_prob *= l.prob
_check("combined odds is the product of the leg prices",
       abs(a0.combined_odds - expected_odds) < 1e-9)
_check("combined prob is the product of the leg probs",
       abs(a0.combined_prob - expected_prob) < 1e-9)

# --- 8. singles book as 1-leg slips with their own label --------------------
singles = build_single_accas(bets5.singles)
_check("every single is a 1-leg acca, labelled SINGLE — <fixture>",
       len(singles) == 7
       and all(a.n_legs == 1 and a.label.startswith("SINGLE — ")
               for a in singles),
       f"got {[a.label for a in singles]}")
_check("single's combined odds/prob equal the leg's own price/prob",
       abs(singles[0].combined_odds - singles[0].legs[0].price) < 1e-9
       and abs(singles[0].combined_prob - singles[0].legs[0].prob) < 1e-9)

# --- 9. fewer than HEADLINE_MIN_LEGS -> shortened acca, honestly -------------
board_short = [_bf("Only v One (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=3.30)]
bets9 = build_production_bets(board_short, today=TODAY, odds_index=None)
_check("shortened acca (never padded with a non-today fixture)",
       bets9.acca_a is not None and bets9.acca_a.n_legs == 1
       and not bets9.split_accas and not bets9.singles,
       f"got acca_a={bets9.acca_a.n_legs if bets9.acca_a else None}")
txt9 = render_production_block(bets9, today=TODAY)
_check("shortened acca renders lean (no prob/EV on the leg)",
       "★ Acca A — HEADLINE, 1 legs" in txt9
       and "Only v One (Eredivisie) — Draw @ 3.30" in txt9
       and "30%" not in txt9, txt9)

# --- 10. empty today -> honest NO production pick (HR35) --------------------
bets10 = build_production_bets([], today=TODAY, odds_index=None)
_check("empty board -> acca_a is None, no splits, no singles",
       bets10.acca_a is None and not bets10.split_accas and not bets10.singles)
txt10 = render_production_block(bets10, today=TODAY)
_check("no production pick renders an honest note",
       "NO production pick today" in txt10, txt10)

# --- 11. render_production_block: Acca A -> splits -> singles, with codes ---
codes11 = {"results": [
    {"label": "Acca A", "code": "AAA11"},
    {"label": "Acca B", "code": "BBB22"},
    {"label": "SINGLE — F5 v G5", "code": "S555"},
]}
txt11 = render_production_block(bets5, codes=codes11, today=TODAY)
_check("block leads with Acca A as the HEADLINE",
       txt11.find("★ Acca A") < txt11.find("Acca B") < txt11.find("SINGLES"),
       txt11[:120])
_check("codes render inline on the combined line (Architect format)",
       "AAA11" in txt11 and "BBB22" in txt11 and "S555" in txt11
       and any("Combined" in ln and "Booking code: AAA11" in ln
               for ln in txt11.splitlines()), txt11[:400])
_check("star on EVERY acca (not just the headline)",
       "★ Acca A" in txt11 and "★ Acca B" in txt11, txt11[:400])
_check("legs are lean — no prob% or EV on any leg line",
       # Leg lines carry only fixture + market + price. The ID407 combined-prob
       # disclosure is a SEPARATE line (allowed to carry %); the assertion checks
       # each leg line, not the whole block, so the disclosure doesn't trip it.
       all("EV" not in ln and "%" not in ln
           for ln in txt11.splitlines()
           if ln.strip().startswith(("F", "★")) and "Combined" not in ln
           and "compounding" not in ln),
       txt11[:400])
_check("ID407: combined-prob disclosure present on multi-leg accas, "
       "labelled 'arithmetic, not a weakness'",
       "Combined prob" in txt11
       and "product of 5 legs — compounding is arithmetic, not a weakness" in txt11,
       txt11[:400])
txt11b = render_production_block(bets5, codes=None, today=TODAY)
_check("no codes -> honest NO DATA — PENDING per item "
       "(3 accas + 7 singles = 10)",
       txt11b.count("NO DATA — PENDING") == 10, txt11b)
_check("block is lean — honest/capital lines moved to the notify envelope",
       "Phase 3 live" not in txt11 and "HONEST EDGE" not in txt11
       and "shortened, not padded" not in txt11, txt11[:400])

# --- 12. SportyBet price preferred for Draw over the Odds API ----------------
board_sb = [
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY,
        sb_draw=3.30, market_key=mkt.DRAW, price=2.90),
]
odds_index12 = {("Alpha v Beta", "Away FC"): _fx("Alpha v Beta", "Away FC", draw=3.10)}
bets12 = build_production_bets(board_sb, today=TODAY, odds_index=odds_index12)
_check("SportyBet price wins for Draw when present",
       bets12.acca_a is not None and abs(bets12.acca_a.legs[0].price - 3.30) < 1e-9,
       f"got {bets12.acca_a.legs[0].price if bets12.acca_a else 'no acca'}")

# --- 13. THE CALL in render_produce_bet is today-only + production block -----
call_board = board + [_bf("Tomorrow v Only (Eredivisie)", _probs(d=0.45),
                          TOMORROW, sb_draw=2.20, shortlist=True)]
out13 = render_produce_bet(mode="M", phase="P", leagues_scanned=["Eredivisie"],
                           calibration_count=0, mean_clv=None, data_flags=[],
                           board=call_board)
_check("THE CALL says today's fixtures only", "today's fixtures only" in out13)
_check("THE CALL excludes the tomorrow fixture",
       "PART 1" in out13 and "Tomorrow v Only" not in out13.split("PART 2")[0],
       "tomorrow fixture leaked into the call")
_check("render_produce_bet carries the production block (Acca A headline)",
       "PRODUCTION BETS" in out13 and "★ Acca A" in out13, out13[-500:])

print("\n✅ ALL ACCA + PRODUCTION INTENT TESTS PASSED")
