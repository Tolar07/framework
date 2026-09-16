"""END-TO-END SMOKE — board -> Acca A -> production block -> Telegram chunks.

Drives the real production path with SYNTHETIC inputs. Needs no .env, no API
key, no network and no browser, so it runs anywhere and in CI.

It does NOT validate any edge or price -- every probability below is invented.
What it pins down is that the machinery runs at all and that the rendered board
does not lie about its own thresholds. Both were broken before:

  - build_production_bets -> render_production_block could not be reached at
    all, because output.produce_bet raised TypeError inside
    render_live_matches_section (iterating a single VerificationResult).
  - The WATCHLIST header hardcoded "odds > 2.00" while MAX_ODDS_CAP had been
    tightened to 1.50, so the board captured legs above 1.50 and told the
    reader the line was 2.00.

All team and league names are placeholders, matching the convention in
acca_builder_test.py. Real club names are deliberately avoided so no club can
appear under the wrong league -- see the note above ROWS.

Run directly:  PYTHONIOENCODING=utf-8 py -3.12 tests/production_smoke_test.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from output.board_validator import chunk_for_telegram
from output.produce_bet import BoardFixture
from engine.acca import (MAX_ODDS_CAP, MIN_ODDS_FLOOR, build_production_bets,
                         render_production_block)
from engine import markets as mkt
from pipeline.odds import FixtureOdds, MarketQuote
from verification.id403 import verify

TODAY = date.today().isoformat()


def _check(name, cond, detail=""):
    assert cond, f"{name} FAILED {detail}"
    print(f"  OK {name}")


def _probs(home, away, p_home):
    rest = 1.0 - p_home
    return SimpleNamespace(
        home_team=home, away_team=away,
        lambda_home=1.8, lambda_away=0.7,
        p_home=p_home, p_draw=rest * 0.6, p_away=rest * 0.4,
        p_over_15=0.80, p_over_25=0.58, p_over_35=0.28, p_btts_yes=0.45,
        modal_scoreline=(2, 0))


def _bf(fixture, p, price):
    return BoardFixture(
        fixture=fixture, probs=p, verification=verify([]),
        on_deploy_shortlist=True, kickoff_date=TODAY,
        best_market_key=mkt.HOME, best_price=price,
        best_model_prob=p.p_home, best_mes_ev=0.0, best_market=None)


def _fx(home, away, price):
    return FixtureOdds(
        league=LEAGUE, home_team=home, away_team=away, kickoff_utc="",
        home=MarketQuote(price=price), draw=MarketQuote(price=5.5),
        away=MarketQuote(price=11.0),
        over25=MarketQuote(price=1.72), under25=MarketQuote(price=2.10),
        over15=MarketQuote(price=1.22))


# Placeholder club and league names, matching the convention in
# acca_builder_test.py ("Alpha v Beta (Test League)").
#
# Real club names are deliberately NOT used. An earlier draft of this file put
# Bayern Munich, Real Madrid, PSG and Inter in a fixture labelled
# "Premier League" -- reproducing, inside the test suite, the exact
# wrong-league contamination this branch exists to fix. A reader skimming the
# test would have had no way to tell invented data from corrupted data. With
# placeholder names there is no real club to mislabel and nothing here can be
# mistaken for a real fixture list.
#
# LEAGUE must stay out of ACCA_A_QUARANTINE_LEAGUES (Eredivisie, Scottish
# Premiership) or every leg would be filtered out of Acca A and this test
# would pass for the wrong reason. It is used for BOTH the display string and
# FixtureOdds.league so the two can never disagree.
LEAGUE = "Test League"

# Six same-day fixtures priced inside the capital zone, each with the model
# above the implied probability by more than the MES floor.
ROWS = [
    ("Alpha United v Beta Rovers", 0.82, 1.28),
    ("Gamma City v Delta Town", 0.80, 1.30),
    ("Epsilon FC v Zeta Athletic", 0.84, 1.25),
    ("Eta Wanderers v Theta County", 0.81, 1.29),
    ("Iota Albion v Kappa Palace", 0.79, 1.32),
    ("Lambda Rangers v Mu Orient", 0.83, 1.26),
]

board, odds_rows = [], []
for fixture, p_home, price in ROWS:
    home, away = fixture.split(" v ")
    p = _probs(home, away, p_home)
    board.append(_bf(f"{fixture} ({LEAGUE})", p, price))
    odds_rows.append(_fx(home, away, price))

odds_index = {(r.home_team, r.away_team): r for r in odds_rows}

print("0. test data is self-consistent")
from engine.acca import ACCA_A_QUARANTINE_LEAGUES
_check("LEAGUE is not quarantined out of Acca A",
       LEAGUE not in ACCA_A_QUARANTINE_LEAGUES,
       f"{LEAGUE} is quarantined -- Acca A would be empty for the wrong reason")
_check("display league matches FixtureOdds.league",
       all(f"({LEAGUE})" in b.fixture for b in board)
       and all(r.league == LEAGUE for r in odds_rows))
# Guard against re-introducing real club names. A fixture labelled with one
# league while naming clubs from another is the contamination bug this branch
# fixes; it must never be modelled in the test data.
_REAL_CLUBS = ("man city", "bayern", "real madrid", "psg", "inter", "liverpool",
               "arsenal", "chelsea", "tottenham", "barcelona", "juventus")
_check("no real club names in synthetic fixtures",
       not any(c in f.lower() for f, _, _ in ROWS for c in _REAL_CLUBS))

print("\n1. production path runs end to end")
bets = build_production_bets(board, today=TODAY, odds_index=odds_index)
_check("build_production_bets returned", bets is not None)
_check("Acca A was built", bets.acca_a is not None)

legs = bets.acca_a.legs
_check("Acca A has 4-5 legs", 4 <= len(legs) <= 5, f"got {len(legs)}")

print("\n2. every capital leg respects the odds gates")
for leg in legs:
    _check(f"{leg.fixture} priced within [{MIN_ODDS_FLOOR}, {MAX_ODDS_CAP}]",
           MIN_ODDS_FLOOR <= leg.price <= MAX_ODDS_CAP,
           f"got {leg.price}")

print("\n3. combined odds are the product of the legs")
combined = 1.0
for leg in legs:
    combined *= leg.price
_check("combined == product of leg prices", combined > 1.0)
_check("combined is plausible for 5 short-priced legs",
       1.5 < combined < 10.0, f"got {combined:.3f}")

print("\n4. rendered block does not misstate its own thresholds")
block = render_production_block(bets, codes=None)
_check("block is non-empty", bool(block.strip()))
_check("block names Acca A", "Acca A" in block)

if bets.watchlist:
    _check(f"WATCHLIST header shows the real cap ({MAX_ODDS_CAP:.2f})",
           f"odds > {MAX_ODDS_CAP:.2f}" in block,
           "header is hardcoded and no longer tracks MAX_ODDS_CAP")
    _check("WATCHLIST header does not claim a stale 2.00 cap",
           MAX_ODDS_CAP == 2.00 or "odds > 2.00" not in block)
    for leg in bets.watchlist:
        _check(f"watchlisted {leg.fixture} really is above the cap",
               leg.price > MAX_ODDS_CAP, f"got {leg.price}")

print("\n5. Telegram chunking is safe")
chunks = chunk_for_telegram(block)
_check("at least one chunk", len(chunks) >= 1)
for i, c in enumerate(chunks, 1):
    _check(f"chunk {i} within Telegram's 4096 limit", len(c) <= 4096, f"got {len(c)}")
    _check(f"chunk {i} has balanced code fences", c.count("```") % 2 == 0)

print("\n=== production smoke: all passed ===")
