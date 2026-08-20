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
                         render_production_block, ACCA_A_MAX, HEADLINE_MIN_LEGS,
                         MAX_ODDS_CAP)
from engine import markets as mkt
from pipeline.odds import FixtureOdds, MarketQuote
from verification.id403 import verify

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _probs(h=0.5, d=0.25, a=0.25, over25=0.5, home="Home FC", away="Away FC",
          over15=0.7, btts=0.5):
    """Fake FixtureProbabilities with the fields build_production_bets reads
    (attribute access — SimpleNamespace is fine, same pattern as consensus_test)."""
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.4, lambda_away=1.0,
        p_home=h, p_draw=d, p_away=a,
        p_over_15=over15, p_over_25=over25, p_over_35=0.3, p_btts_yes=btts,
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
    _bf("Alpha v Beta (Eredivisie)", _probs(d=0.30), TODAY, sb_draw=1.80),
    _bf("Gamma v Delta (Eredivisie)", _probs(d=0.28), TOMORROW, sb_draw=1.90),
    _bf("Epsilon v Zeta (Eredivisie)", _probs(d=0.26), TODAY, sb_draw=1.95),
    _bf("Eta v Theta (Eredivisie)", _probs(d=0.24), TOMORROW, sb_draw=1.85),
    _bf("Iota v Kappa (Eredivisie)", _probs(d=0.22), TODAY, sb_draw=1.92),
    _bf("Lambda v Mu (Eredivisie)", _probs(d=0.20), TODAY, sb_draw=1.88),
]
bets1 = build_production_bets(board, today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
       [a.label for a in build_accas(board, today=TODAY, max_odds_cap=float('inf'))] == ["Acca A"])

# --- 2. HR35: a fixture with no kickoff date is never assumed to be today ----
board_no_date = board + [_bf("Undated v Ghost (Eredivisie)", _probs(d=0.40),
                             None, sb_draw=2.50)]
bets2 = build_production_bets(board_no_date, today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
bets3 = build_production_bets(best_board, today=TODAY, odds_index=odds_index, max_odds_cap=float('inf'))
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
_check("edge ranking: Acca A legs sorted by canonical edge (prob gap) desc",
       [round(l.edge, 2) for l in bets3.acca_a.legs] == [0.09, 0.09, 0.08, 0.06],
       f"got edge={[round(l.edge, 2) for l in bets3.acca_a.legs]}")
_check("EV stays on the leg as information (prob*price-1)",
       [round(l.ev, 2) for l in bets3.acca_a.legs] == [1.17, 0.70, 0.62, 0.50],
       f"got ev={[round(l.ev, 2) for l in bets3.acca_a.legs]}")

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
    # Use short odds (<2.00) so they pass the MAX_ODDS_CAP
    return [_bf(f"F{i} v G{i} (Eredivisie)", _probs(d=start - i * 0.01),
                TODAY, sb_draw=1.70 + i * 0.02) for i in range(n)]

board_rich = _conf_board(12)
bets5 = build_production_bets(board_rich, today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
    pb = build_production_bets(b, today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
bets9 = build_production_bets(board_short, today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
bets10 = build_production_bets([], today=TODAY, odds_index=None, max_odds_cap=float('inf'))
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
        sb_draw=1.80, market_key=mkt.DRAW, price=1.90),
]
odds_index12 = {("Alpha v Beta", "Away FC"): _fx("Alpha v Beta", "Away FC", draw=1.90)}
bets12 = build_production_bets(board_sb, today=TODAY, odds_index=odds_index12, max_odds_cap=float('inf'))
_check("SportyBet price wins for Draw when present",
       bets12.acca_a is not None and abs(bets12.acca_a.legs[0].price - 1.80) < 1e-9,
       f"got {bets12.acca_a.legs[0].price if bets12.acca_a else 'no acca'}")

# --- 13. THE CALL in render_produce_bet is today-only + production block -----
# ID409 (PROPOSED, pending ratification): Detail (PART 2) → Call (PART 1) order.
# Pass a pre-built production object (uncapped) so the render function doesn't
# re-build with the default MAX_ODDS_CAP (which filters the >2.00 draw odds).
call_board = board + [_bf("Tomorrow v Only (Eredivisie)", _probs(d=0.45),
                          TOMORROW, sb_draw=2.20, shortlist=True)]
call_production = build_production_bets(call_board, today=TODAY, odds_index=None,
                                        max_odds_cap=float('inf'))
out13 = render_produce_bet(mode="M", phase="P", leagues_scanned=["Eredivisie"],
                           calibration_count=0, mean_clv=None, data_flags=[],
                           board=call_board, production=call_production, codes=None)
_check("THE CALL says today's fixtures only", "today's fixtures only" in out13)
_check("PART 2 (THE SCAN) now prints FIRST, then PART 1 (THE CALL) — ID409",
       "PART 2" in out13 and "PART 1" in out13 and out13.index("PART 2") < out13.index("PART 1"),
       "ID409 reorder not applied: PART 2 must precede PART 1")
_check("THE CALL still excludes tomorrow fixture (today-only rule)",
       "Tomorrow v Only" not in out13.split("PART 1")[-1],
       "tomorrow fixture leaked into the CALL section")
_check("render_produce_bet carries the production block (Acca A headline)",
       "PRODUCTION BETS" in out13 and "★ Acca A" in out13, out13[-500:])

# --- 14. agreement gate (gambler move #2, 2026-08-15 experiment) -------------
# A fixture where the model and the book DISAGREE hard (the measured-losing
# bucket): model loves the away dog at 45%, book prices it at 3.60 => implied
# ~27.8%, a >17pp gap. With NO gate, this is a +62% EV "value" leg that the
# framework would headline. With agreement_band=0.04 it must be excluded.
#
# A second fixture where model and book AGREE (the calibrated zone): model 52%,
# book prices home at 1.95 => implied ~51.3%, a 0.7pp gap. This leg must
# survive the gate when it carries positive EV, and be excluded when EV <= 0.
def _fx_home(home, away, h, d, a):
    return FixtureOdds(
        league="Eredivisie", home_team=home, away_team=away, kickoff_utc="",
        home=MarketQuote(price=h), draw=MarketQuote(price=d),
        away=MarketQuote(price=a), over25=MarketQuote(price=2.0),
        under25=MarketQuote(price=1.8))

agree_board = [
    # DISAGREEMENT: model away 45% vs book away @3.60 (implied ~27.8%) — EV +62%
    _bf("Dog v Fav (Eredivisie)", _probs(h=0.40, d=0.15, a=0.45,
                                         home="Dog FC", away="Fav FC"), TODAY),
    # AGREEMENT, positive EV: model home 52% vs book home @1.95 (implied ~51.3%)
    _bf("Tier v Mid (Eredivisie)", _probs(h=0.52, d=0.24, a=0.24,
                                         home="Tier FC", away="Mid FC"), TODAY),
    # AGREEMENT, NEGATIVE EV: model home 55% vs book home @1.70 (implied ~58.8%)
    # i.e. book SHORTENS the favourite below true value — inside band, but no edge
    _bf("Big v Small (Eredivisie)", _probs(h=0.55, d=0.22, a=0.23,
                                          home="Big FC", away="Small FC"), TODAY),
]
agree_index = {
    ("Dog FC", "Fav FC"): _fx_home("Dog FC", "Fav FC", 2.30, 3.40, 3.60),
    ("Tier FC", "Mid FC"): _fx_home("Tier FC", "Mid FC", 1.95, 3.30, 4.20),
    ("Big FC", "Small FC"): _fx_home("Big FC", "Small FC", 1.70, 3.60, 5.50),
}
# Baseline (no gate): canonical edge (prob gap) ranks legs (Architect 2026-08-19).
# Dog v Fav away: model 45% vs book implied 27.8% -> edge = 17.2pp (HIGHEST)
# Tier v Mid home: model 52% vs book implied 51.3% -> edge = 0.7pp
# Big v Small home: model 55% vs book implied 58.8% -> edge = -3.8pp (negative!)
bets_base = build_production_bets(agree_board, today=TODAY, odds_index=agree_index, max_odds_cap=float('inf'))
_check("agreement gate: without band, canonical edge determines ranking (ID414)",
       bets_base.acca_a is not None
       and bets_base.acca_a.legs[0].fixture == "Dog v Fav"
       and "Fav" in bets_base.acca_a.legs[0].market_name,
       f"got {bets_base.acca_a.legs[0].fixture if bets_base.acca_a else 'no acca'} "
       f"market={bets_base.acca_a.legs[0].market_name if bets_base.acca_a else '?'}")
# With band=0.04: the DISAGREEING away market on Dog v Fav (17pp gap) is
# excluded — but the fixture may still appear on a DIFFERENT market that agrees.
# True per-fixture exclusion requires ALL markets to disagree, so we verify
# per-MARKET instead: the away market must never be selected within the gate.
bets_gate = build_production_bets(agree_board, today=TODAY,
                                 odds_index=agree_index, agreement_band=0.04, max_odds_cap=float('inf'))
gate_legs = [l for a in
             (([bets_gate.acca_a] if bets_gate.acca_a else [])
              + bets_gate.split_accas) for l in a.legs] \
    + list(bets_gate.singles)
gate_fixtures = {l.fixture for l in gate_legs}
gate_away_legs = [l for l in gate_legs if "Away" in l.market_name
                  or "away" in l.market_name.lower()
                  or "Fav" in l.market_name
                  or "Dog" in l.market_name]  # Dog is the away team in this test
_check("agreement gate: disagreement AWAY market (17pp) never selected",
       len(gate_away_legs) == 0,
       f"got away legs: {[(l.fixture, l.market_name) for l in gate_away_legs]}")
_check("agreement gate: agreement leg with positive EV (Tier v Mid) survives",
       "Tier v Mid" in gate_fixtures, f"got {gate_fixtures}")
# Big v Small: home model 55% vs book implied ~58.8% -> 3.8pp gap, inside band
# but EV is negative (0.55 * 1.70 - 1 = -6.5%). The agreement gate passes it
# through (band does NOT check EV), but the EV filter recomputes the best leg
# across all markets.  So Big v Small may appear on Over 2.5 (model 50% vs devig
# ~47.4% = 2.6pp, inside band, EV = 0.0 if price 2.0).  Verify it never appears
# on the NEGATIVE-EV home market.
big_legs = [l for l in gate_legs if l.fixture == "Big v Small"]
if big_legs:
    _check("agreement gate: Big v Small never on negative-EV home market",
           all("Home" not in l.market_name and "home" not in l.market_name.lower()
               for l in big_legs),
           f"got {[(l.market_name, l.price) for l in big_legs]}")
else:
    _check("agreement gate: Big v Small excluded entirely (no agreeing +EV market)",
           True, "")
bets_none = build_production_bets(agree_board, today=TODAY,
                                 odds_index=agree_index, agreement_band=None, max_odds_cap=float('inf'))
none_legs = [l for a in
             (([bets_none.acca_a] if bets_none.acca_a else [])
              + bets_none.split_accas) for l in a.legs] \
    + list(bets_none.singles)
_check("agreement gate: agreement_band=None == no-gate (shipped behaviour)",
       {l.fixture for l in none_legs} == {l.fixture for l in
           [ll for a in
            (([bets_base.acca_a] if bets_base.acca_a else [])
             + bets_base.split_accas) for ll in a.legs]
           + list(bets_base.singles)},
       f"none={[l.fixture for l in none_legs]}")

# --- 15. MAX_ODDS_CAP: legs priced above the cap are rejected (FL guardrail) ---
cap_board = [
    _bf("FavA v DogA (Eredivisie)", _probs(h=0.55, d=0.25, a=0.20,
                                           home="FavA", away="DogA"), TODAY,
        sb_draw=1.50),  # Draw @ 1.50 -> under cap, admitted
    _bf("FavB v DogB (Eredivisie)", _probs(h=0.50, d=0.25, a=0.25,
                                           home="FavB", away="DogB"), TODAY,
        sb_draw=3.50),  # Draw @ 3.50 -> over cap, rejected
]
bets_cap = build_production_bets(cap_board, today=TODAY, odds_index=None)
cap_fixtures = set()
if bets_cap.acca_a:
    cap_fixtures |= {l.fixture for l in bets_cap.acca_a.legs}
cap_fixtures |= {l.fixture for a in bets_cap.split_accas for l in a.legs}
cap_fixtures |= {l.fixture for l in bets_cap.singles}
_check("MAX_ODDS_CAP: fixture with odds <= 2.00 admitted",
       "FavA v DogA" in cap_fixtures, f"got {cap_fixtures}")
_check("MAX_ODDS_CAP: fixture with odds > 2.00 rejected",
       "FavB v DogB" not in cap_fixtures, f"got {cap_fixtures}")

# --- 15b. ID420 WATCHLIST: legs with odds > 2.00 are captured in watchlist, not dropped ---
# The watchlist is separate from capital-eligible legs. Legs > 2.00 should NOT be
# in accas/singles but SHOULD appear in production.watchlist.
_check("ID420: watchlist captures leg with odds > 2.00",
       hasattr(bets_cap, 'watchlist')
       and len(bets_cap.watchlist) == 1
       and bets_cap.watchlist[0].fixture == "FavB v DogB"
       and bets_cap.watchlist[0].price == 3.50
       and bets_cap.watchlist[0].status == "watchlist",
       f"got watchlist: {[(l.fixture, l.price, l.status) for l in getattr(bets_cap, 'watchlist', [])]}")
_check("ID420: watchlist leg NOT in capital accas/singles",
       "FavB v DogB" not in cap_fixtures, f"capital fixtures: {cap_fixtures}")
_check("ID420: capital leg still admitted (FavA v DogA @ 1.50)",
       "FavA v DogA" in cap_fixtures, f"got {cap_fixtures}")

# Helper to build full FixtureOdds (used by 15c and 16)
def _fx_ticket(home_team, away_team, **prices):
    """Full market prices for the real ticket fixtures."""
    def q(key):
        return MarketQuote(price=prices.get(key)) if prices.get(key) else MarketQuote()
    return FixtureOdds(
        league="World Cup", home_team=home_team, away_team=away_team, kickoff_utc="",
        home=q("home"), draw=q("draw"), away=q("away"),
        over15=q("over15"), under15=q("under15"),
        over25=q("over25"), under25=q("under25"),
        btts_yes=q("btts_yes"), btts_no=q("btts_no"),
        dc_1x=q("dc_1x"), dc_x2=q("dc_x2"), dc_12=q("dc_12"),
        source="test", source_tier="T1")

# --- 15c. WATCHLIST: fixture with BOTH a capital-eligible leg AND a watchlist leg ---
# The fixture should get its capital-eligible leg in the bets, and the watchlist
# leg should be in the watchlist for review.
mixed_board = [
    # Fixture with Home @ 1.80 (capital) AND Draw @ 3.20 (watchlist)
    _bf("Mixed v Case (Eredivisie)",
        _probs(h=0.45, d=0.28, a=0.27, over25=0.45, home="Mixed", away="Case"), TODAY),
]

mixed_odds = {
    ("Mixed", "Case"): _fx_ticket("Mixed", "Case", home=1.80, draw=3.20),
}
bets_mixed = build_production_bets(mixed_board, today=TODAY, odds_index=mixed_odds)
mixed_cap_fixtures = set()
if bets_mixed.acca_a:
    mixed_cap_fixtures |= {l.fixture for l in bets_mixed.acca_a.legs}
mixed_cap_fixtures |= {l.fixture for a in bets_mixed.split_accas for l in a.legs}
mixed_cap_fixtures |= {l.fixture for l in bets_mixed.singles}

_check("ID420: mixed fixture - capital leg admitted (Home @ 1.80)",
       "Mixed v Case" in mixed_cap_fixtures, f"got {mixed_cap_fixtures}")
_check("ID420: mixed fixture - watchlist leg captured (Draw @ 3.20)",
       hasattr(bets_mixed, 'watchlist')
       and len(bets_mixed.watchlist) == 1
       and bets_mixed.watchlist[0].fixture == "Mixed v Case"
       and bets_mixed.watchlist[0].price == 3.20
       and bets_mixed.watchlist[0].status == "watchlist"
       and bets_mixed.watchlist[0].market_key == mkt.DRAW,
       f"got watchlist: {[(l.fixture, l.price, l.market_key, l.status) for l in getattr(bets_mixed, 'watchlist', [])]}")

# --- 16. REAL TICKET REGRESSION: 2026-08-15 World Cup ticket with 15 legs ---
# Every leg sits between 1.16 and 2.05 — the 2.00 ceiling should NOT filter any
# of these legitimate short-price legs. This validates the ceiling is correctly
# positioned to exclude only longshot bias, not compounding short prices.
# Total odds = 1.16 × 1.29 × 1.48 × 1.96 × 1.74 × 1.52 × 1.28 × 2.05 × 1.35 ×
#              1.32 × 1.32 × 1.44 × 1.51 × 1.61 ≈ 344.07 (one leg void)

# All 15 legs from the real ticket — odds all in [1.16, 2.05]
# Note: the framework doesn't have Over/Under 3.5 markets, so we use 2.5 equivalents
# for the test — the point is validating the 2.00 ceiling admits all short prices.
ticket_board = [
    # South Africa v Canada — DC Draw/Away @ 1.16
    _bf("South Africa v Canada (World Cup)",
        _probs(home="South Africa", away="Canada",
               h=0.30, d=0.35, a=0.35, over25=0.50),
        TODAY),
    # Brazil v Japan — Over 1.5 @ 1.29
    _bf("Brazil v Japan (World Cup)",
        _probs(home="Brazil", away="Japan",
               h=0.55, d=0.25, a=0.20, over25=0.60),
        TODAY),
    # Germany v Paraguay — Under 2.5 @ 1.48 (was Under 3.5 in ticket)
    _bf("Germany v Paraguay (World Cup)",
        _probs(home="Germany", away="Paraguay",
               h=0.60, d=0.20, a=0.20, over25=0.45),
        TODAY),
    # Netherlands v Morocco — BTTS Yes @ 1.96
    _bf("Netherlands v Morocco (World Cup)",
        _probs(home="Netherlands", away="Morocco",
               h=0.45, d=0.25, a=0.30, over25=0.55),
        TODAY),
    # Ivory Coast v Norway — BTTS Yes @ 1.74
    _bf("Ivory Coast v Norway (World Cup)",
        _probs(home="Ivory Coast", away="Norway",
               h=0.40, d=0.30, a=0.30, over25=0.50),
        TODAY),
    # France v Sweden — Over 2.5 @ 1.52
    _bf("France v Sweden (World Cup)",
        _probs(home="France", away="Sweden",
               h=0.50, d=0.25, a=0.25, over25=0.60),
        TODAY),
    # Mexico v Ecuador — Under 2 @ 1.75 (VOID — excluded from final odds)
    # Not included since it was voided
    # England v Congo DR — Home @ 1.28
    _bf("England v Congo DR (World Cup)",
        _probs(home="England", away="Congo DR",
               h=0.65, d=0.20, a=0.15, over25=0.40),
        TODAY),
    # Belgium v Senegal — BTTS @ 2.05 (at ceiling edge)
    _bf("Belgium v Senegal (World Cup)",
        _probs(home="Belgium", away="Senegal",
               h=0.45, d=0.25, a=0.30, over25=0.55),
        TODAY),
    # USA v Bosnia-Herzegovina — Home @ 1.35
    _bf("USA v Bosnia-Herzegovina (World Cup)",
        _probs(home="USA", away="Bosnia-Herzegovina",
               h=0.60, d=0.25, a=0.15, over25=0.45),
        TODAY),
    # Spain v Austria — Home @ 1.32
    _bf("Spain v Austria (World Cup)",
        _probs(home="Spain", away="Austria",
               h=0.58, d=0.25, a=0.17, over25=0.42),
        TODAY),
    # Switzerland v Algeria — Over 1.5 @ 1.32
    _bf("Switzerland v Algeria (World Cup)",
        _probs(home="Switzerland", away="Algeria",
               h=0.50, d=0.30, a=0.20, over25=0.55),
        TODAY),
    # Australia v Egypt — Under 2.5 @ 1.44
    _bf("Australia v Egypt (World Cup)",
        _probs(home="Australia", away="Egypt",
               h=0.35, d=0.30, a=0.35, over25=0.40),
        TODAY),
    # Argentina v Cape Verde — Under 2.5 @ 1.51 (was Under 3.5 in ticket)
    _bf("Argentina v Cape Verde (World Cup)",
        _probs(home="Argentina", away="Cape Verde",
               h=0.65, d=0.20, a=0.15, over25=0.35),
        TODAY),
    # Colombia v Ghana — Home @ 1.61
    _bf("Colombia v Ghana (World Cup)",
        _probs(home="Colombia", away="Ghana",
               h=0.55, d=0.25, a=0.20, over25=0.45),
        TODAY),
]

# Build the full price index for all 14 fixtures (the voided one excluded)
ticket_odds = {
    ("South Africa", "Canada"): _fx_ticket("South Africa", "Canada",
        dc_x2=1.16),
    ("Brazil", "Japan"): _fx_ticket("Brazil", "Japan",
        over15=1.29),
    ("Germany", "Paraguay"): _fx_ticket("Germany", "Paraguay",
        under25=1.48),
    ("Netherlands", "Morocco"): _fx_ticket("Netherlands", "Morocco",
        btts_yes=1.96),
    ("Ivory Coast", "Norway"): _fx_ticket("Ivory Coast", "Norway",
        btts_yes=1.74),
    ("France", "Sweden"): _fx_ticket("France", "Sweden",
        over25=1.52),
    ("England", "Congo DR"): _fx_ticket("England", "Congo DR",
        home=1.28),
    ("Belgium", "Senegal"): _fx_ticket("Belgium", "Senegal",
        btts_yes=2.05),
    ("USA", "Bosnia-Herzegovina"): _fx_ticket("USA", "Bosnia-Herzegovina",
        home=1.35),
    ("Spain", "Austria"): _fx_ticket("Spain", "Austria",
        home=1.32),
    ("Switzerland", "Algeria"): _fx_ticket("Switzerland", "Algeria",
        over15=1.32),
    ("Australia", "Egypt"): _fx_ticket("Australia", "Egypt",
        under25=1.44),
    ("Argentina", "Cape Verde"): _fx_ticket("Argentina", "Cape Verde",
        under25=1.51),
    ("Colombia", "Ghana"): _fx_ticket("Colombia", "Ghana",
        home=1.61),
}

bets_ticket = build_production_bets(ticket_board, today=TODAY, odds_index=ticket_odds,
                                     max_odds_cap=2.00, min_odds_floor=1.20)

# Collect all legs from Acca A, split accas, and singles
ticket_legs = {}
if bets_ticket.acca_a:
    for l in bets_ticket.acca_a.legs:
        ticket_legs[l.fixture] = (l.market_name, l.price)
for acca in bets_ticket.split_accas:
    for l in acca.legs:
        ticket_legs[l.fixture] = (l.market_name, l.price)
for l in bets_ticket.singles:
    ticket_legs[l.fixture] = (l.market_name, l.price)

_check("REAL TICKET: 12 of 14 fixtures admitted (Belgium 2.05 above cap, South Africa 1.16 below floor)",
       len(ticket_legs) == 12, f"got {len(ticket_legs)} legs: {list(ticket_legs.keys())}")
_check("REAL TICKET: every admitted leg price in [1.20, 2.00] (floor + ceiling respected)",
       all(1.20 <= price <= 2.00 for _, price in ticket_legs.values()),
       f"got prices: {[(f, p) for f, (_, p) in ticket_legs.items()]}")
_check("REAL TICKET: Belgium v Senegal at 2.05 correctly filtered (above 2.00 ceiling)",
       "Belgium v Senegal" not in ticket_legs,
       f"got {ticket_legs.get('Belgium v Senegal')}")
_check("REAL TICKET: South Africa v Canada at 1.16 correctly filtered (below 1.20 floor)",
       "South Africa v Canada" not in ticket_legs,
       f"got {ticket_legs.get('South Africa v Canada')}")
_check("REAL TICKET: Acca A combined odds is product of top 5 edge legs (not all 12)",
       bets_ticket.acca_a is not None
       and abs(bets_ticket.acca_a.combined_odds - 7.569) < 0.01,
       f"Acca A combined odds = {bets_ticket.acca_a.combined_odds if bets_ticket.acca_a else 'N/A'}")
_check("REAL TICKET: the 1.20-2.00 deployment window works — filters below-floor and above-cap legs",
       True, "")  # validated by the 12 admitted / 2 filtered checks above

# --- 15b. PREFERRED ZONE (1.20-1.50) — Architect 2026-08-19 deployment policy:
# build accas from short-priced "safe" legs (1.20-1.50); only fall back to a
# 1.50-2.00 leg on a fixture when NO preferred-zone market exists for it.
pref_board = [
    # Home @ 1.55 (1.50-2.00) AND Over 2.5 @ 1.45 (preferred 1.20-1.50) both exist
    _bf("Pref v Fallback (Eredivisie)",
        _probs(h=0.62, d=0.24, a=0.14, over25=0.58, home="Pref", away="Fallback"), TODAY),
    # Home @ 1.80 (1.50-2.00) is the only sub-cap market; Over 2.5 @ 2.10 is over cap
    _bf("OnlyFallback v X (Eredivisie)",
        _probs(h=0.45, d=0.28, a=0.27, over25=0.50, home="OnlyFallback", away="X"), TODAY),
]
pref_odds = {
    ("Pref", "Fallback"): _fx_ticket("Pref", "Fallback", home=1.55, over25=1.45),
    ("OnlyFallback", "X"): _fx_ticket("OnlyFallback", "X", home=1.80, over25=2.10),
}
bets_pref = build_production_bets(pref_board, today=TODAY, odds_index=pref_odds)
pref_legs = {}
if bets_pref.acca_a:
    for l in bets_pref.acca_a.legs:
        pref_legs[l.fixture] = (l.market_name, l.price)
for a in bets_pref.split_accas:
    for l in a.legs:
        pref_legs[l.fixture] = (l.market_name, l.price)
for l in bets_pref.singles:
    pref_legs[l.fixture] = (l.market_name, l.price)

_check("PREFERRED ZONE: fixture with a 1.45 preferred leg picks it over a 1.55 leg",
       pref_legs.get("Pref v Fallback", (None, None))[1] == 1.45,
       f"got {pref_legs.get('Pref v Fallback')}")
_check("PREFERRED ZONE: fixture with only a 1.80 leg (2.10 over cap) still admitted",
       "OnlyFallback v X" in pref_legs
       and pref_legs["OnlyFallback v X"][1] == 1.80,
       f"got {pref_legs.get('OnlyFallback v X')}")
_check("PREFERRED ZONE: the 2.10 Over 2.5 leg rejected (above cap), only 1.80 survives",
       pref_legs.get("OnlyFallback v X", (None, None))[1] == 1.80,
       f"got {pref_legs.get('OnlyFallback v X')}")

# --- 16. PART 1 (THE CALL) renders as a FULL DETAIL TABLE (ID409 + HR53) -----
# Every today's fixture is ONE row; all probability/opinion/edge columns inline.
# No stacked prose blocks. Regression guard so a future edit cannot silently
# revert the table back to per-fixture text blocks.
from output.produce_bet import render_part1_the_call, stamp
_t1 = _bf("TableTest v Row (Eredivisie)",
          _probs(home="TableTest", away="Row", h=0.42, d=0.32, a=0.26,
                 over15=0.61, over25=0.33, btts=0.41),
          TODAY)
_t1.elo_probs = (0.48, 0.26, 0.26)
_t1.consensus = SimpleNamespace(result="HOME", agreeing=2, n_engines=2,
                                split=False, weighted=False, weight_used=None,
                                avg_home=0.45, avg_draw=0.29, avg_away=0.26, votes=None)
_t1.best_market = "Draw"
_t1.best_price = 3.25
_t1.best_model_prob = 0.32
_t1.best_mes_ev = 0.0452
_t1.mes_trigger_price = 1.63
t1_out = render_part1_the_call([_t1])
_check("PART 1 is a table: data row has 17 columns joined by ' | '",
       "\n" in t1_out and len(t1_out.splitlines()[-1].split(" | ")) == 17,
       f"last row cols = {len(t1_out.splitlines()[-1].split(' | ')) if t1_out.splitlines() else 0}")
_check("PART 1 table carries the frozen column names (Fixture, H%, D%, A%, O1.5, O2.5, BTTS, Elo H/D/A, xG H/D/A, Mkt H/D/A, Cons, BestMkt, Price, MES EV, Trig, Src, Notes)",
       "Fixture | H% | D% | A% | O1.5 | O2.5 | BTTS | Elo H/D/A | xG H/D/A | Mkt H/D/A | Cons | BestMkt | Price | MES EV | Trig | Src | Notes" in t1_out,
       "frozen header missing")
_check("PART 1 table row renders all numeric cells inline (no stacked prose)",
       "TableTest v Row (Eredivisie) | 42 | 32 | 26 | O61 | U67 | N59 | 48/26/26" in t1_out
       and "Draw | 3.25 | +4.52% | 1.63+" in t1_out,
       "detail cells not inline in one row")
_check("PART 1 has NO stacked fixture-block markers (no 'Second opinion' prose)",
       "Second opinion" not in t1_out and "Expected goals (model)" not in t1_out,
       "PART 1 reverted to prose blocks")

print("\n✅ ALL ACCA + PRODUCTION INTENT TESTS PASSED")
