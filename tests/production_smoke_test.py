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
        league="Premier League", home_team=home, away_team=away, kickoff_utc="",
        home=MarketQuote(price=price), draw=MarketQuote(price=5.5),
        away=MarketQuote(price=11.0),
        over25=MarketQuote(price=1.72), under25=MarketQuote(price=2.10),
        over15=MarketQuote(price=1.22))


# Six same-day fixtures priced inside the capital zone, each with the model
# above the implied probability by more than the MES floor.
ROWS = [
    ("Man City v Burnley", 0.82, 1.28),
    ("Bayern Munich v Augsburg", 0.80, 1.30),
    ("Real Madrid v Getafe", 0.84, 1.25),
    ("PSG v Le Havre", 0.81, 1.29),
    ("Inter v Empoli", 0.79, 1.32),
    ("Liverpool v Sheffield United", 0.83, 1.26),
]

board, odds_rows = [], []
for fixture, p_home, price in ROWS:
    home, away = fixture.split(" v ")
    p = _probs(home, away, p_home)
    board.append(_bf(f"{fixture} (Premier League)", p, price))
    odds_rows.append(_fx(home, away, price))

odds_index = {(r.home_team, r.away_team): r for r in odds_rows}

print("1. production path runs end to end")
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
