"""
THE 07:00 DAILY RUN — blueprint Section 1, end to end.

    grade yesterday -> fixtures -> odds -> engine -> verify -> board -> log -> notify

WHAT THIS IS
  A Phase 2 CALIBRATION instrument. Its job is to accumulate paper legs with
  logged closing-line value toward the >=30-leg Phase 3 gate. It is not a
  tipping service, and the message it sends says so.

WHAT IT CANNOT DO
  Stake. config.assert_paper_only() blocks any stake reaching disk below
  Phase 3, so a bug in this file cannot deploy money.

OPERATING PROTOCOL (master 13.1, anti-iteration)
  Runs end to end without stopping to ask permission at each step. A league
  with no clean data degrades to NO DATA — PENDING in full view. Near-zero
  approvals is correct behaviour, not failure.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PHASE_LABEL, PAPER_PHASE
from data.football_data_source import load_league
from engine.softness import (SOFTNESS_TIER, DEPLOY_ELIGIBLE_TIERS,
                             build_deploy_shortlist, market_blocked)
from engine.mes import mes_numeric
from clv.clv_logger import CLVLog, compute_clv
from output.produce_bet import render_produce_bet, render_verify_results
from output import notify
import orchestrator
import pipeline.odds as odds_mod

BOARD_DIR = Path(__file__).parent / "output" / "boards"

# Deploy-eligible leagues only for the odds pull — scan-only leagues can never
# produce a capital pick, so spending API credits on their prices would burn
# the monthly quota for nothing.
DEPLOY_LEAGUES = [lg for lg, t in SOFTNESS_TIER.items() if t in DEPLOY_ELIGIBLE_TIERS]


# --------------------------------------------------------------------------
# 1. GRADE YESTERDAY  (VERIFY RESULTS + forward CLV)
# --------------------------------------------------------------------------

def _settle(market: str, fthg: int, ftag: int):
    total = fthg + ftag
    return {
        "Match result — home win": fthg > ftag,
        "Match result — draw": fthg == ftag,
        "Match result — away win": ftag > fthg,
        "Over 2.5 goals": total > 2,
        "Under 2.5 goals": total <= 2,
        "Over 1.5 goals": total > 1,
        "Both teams to score — yes": fthg > 0 and ftag > 0,
        "Both teams to score — no": not (fthg > 0 and ftag > 0),
    }.get(market)


def grade_open_legs(log: CLVLog, season: str) -> tuple[str, list[str]]:
    """Settle any logged leg whose match has now been played, and capture its
    CLOSING price so CLV can be computed (HR46).

    HR15: football-data.co.uk's FT columns are the 90-minute result, which is
    the required settlement basis. ID48: a result reaches the board only from
    the source, never reconstructed — an ungraded leg stays ungraded."""
    flags: list[str] = []
    pending = [l for l in log.legs
               if l.phase == PAPER_PHASE and l.hit is None]
    if not pending:
        return "VERIFY RESULTS\nNo legs awaiting settlement.", flags

    # Keyed by (home, away, DATE). Keying on the pairing alone settled a leg on
    # a future fixture against last season's meeting of the same two clubs —
    # inventing a result and a closing price, and feeding both into the Phase 3
    # capital gate. The date is now part of the key, and a leg with no recorded
    # match_date is refused rather than matched loosely.
    results_by_league: dict[str, dict] = {}
    for lg in {l.league for l in pending}:
        table: dict = {}
        for s in {season, orchestrator.next_season_code(season)}:
            try:
                res, _ = load_league(lg, s)
                table.update({(r.home_team, r.away_team, r.date): r for r in res})
            except Exception:
                continue  # that season simply isn't published yet
        if table:
            results_by_league[lg] = table
        else:
            flags.append(f"{lg}: no results available for grading — "
                         f"legs stay PENDING, not guessed")

    rows, graded = [], 0
    for leg in pending:
        table = results_by_league.get(leg.league)
        if not table:
            continue
        try:
            home, away = [s.strip() for s in leg.fixture.split(" v ", 1)]
        except ValueError:
            continue
        if not leg.match_date:
            # Pre-fix leg, or one logged without a kickoff date. Grading it
            # would mean matching on the pairing alone, which is exactly the
            # defect that produced fabricated results. Refuse (HR35/ID48).
            flags.append(f"{leg.fixture} / {leg.market}: no kickoff date recorded "
                         f"— cannot be graded without matching the wrong match. "
                         f"NO DATA — PENDING.")
            continue
        match = table.get((home, away, leg.match_date))
        if match is None:
            continue  # not played yet, or not published — remains PENDING (ID48)

        hit = _settle(leg.market, match.fthg, match.ftag)
        if hit is None:
            flags.append(f"{leg.fixture}: market '{leg.market}' has no settlement "
                         f"rule — NO DATA — PENDING")
            continue

        log.log_result(leg.leg_id, ft_result=f"{match.fthg}-{match.ftag}", hit=hit)

        # HR46 closing line, from the archive path (CL-ARCHIVE).
        closing = None
        if match.odds:
            closing = {
                "Match result — home win": match.odds.home.close,
                "Match result — draw": match.odds.draw.close,
                "Match result — away win": match.odds.away.close,
                "Over 2.5 goals": match.odds.over25.close,
                "Under 2.5 goals": match.odds.under25.close,
            }.get(leg.market)
        if closing is not None and leg.entry_odds:
            log.log_close(leg.leg_id, closing_odds=closing,
                           closing_capture_path="CL-ARCHIVE")
        else:
            flags.append(f"{leg.fixture} / {leg.market}: no closing price in source "
                         f"— CLV stays NO DATA — PENDING, never estimated")

        graded += 1
        clv = compute_clv(leg.entry_odds, closing) if (closing and leg.entry_odds) else None
        rows.append({
            "fixture": leg.fixture,
            "ft": f"{match.fthg}-{match.ftag}",
            "onextwo": leg.market,
            "goals": f"entry {leg.entry_odds} / close {closing if closing else 'NO DATA — PENDING'}",
            "btts": f"CLV {clv:+.2f}%" if clv is not None else "CLV NO DATA — PENDING",
            "tally": "HIT" if hit else "MISS",
        })

    flags.append(f"graded {graded} of {len(pending)} pending leg(s)")
    return render_verify_results(rows), flags


# --------------------------------------------------------------------------
# 2. LOG TODAY'S PAPER LEGS (this is what advances the Phase 3 gate)
# --------------------------------------------------------------------------

def log_paper_legs(log: CLVLog, board: list, odds_index: dict,
                    min_mes: float = 0.0) -> tuple[int, list[str]]:
    """Attach a live entry price to each deploy-eligible fixture and log it.

    Without this the daily run produces a board and nothing else, the paper
    log stays empty, and the Phase 3 gate can never be reached — which is the
    entire purpose of Phase 2."""
    flags: list[str] = []
    logged = 0
    already = {(l.fixture, l.market) for l in log.legs}

    for bf in board:
        if not bf.on_deploy_shortlist or bf.probs is None:
            continue
        p = bf.probs
        fixture_name = bf.fixture.split(" (")[0]
        fx = odds_index.get((p.home_team, p.away_team))
        if fx is None:
            flags.append(f"{fixture_name}: no live price found — "
                         f"NO DATA — PENDING, leg not logged")
            continue

        for market, model_p, quote in (
            (f"Match result — home win", p.p_home, fx.home),
            (f"Match result — draw", p.p_draw, fx.draw),
            (f"Match result — away win", p.p_away, fx.away),
            ("Over 2.5 goals", p.p_over_25, fx.over25),
            ("Under 2.5 goals", 1 - p.p_over_25, fx.under25),
        ):
            if not quote.available:
                continue
            blocked = market_blocked(market)
            if blocked:
                # Ratified market gate — this market is structurally negative,
                # so a leg on it would add noise to the Phase 2 evidence base.
                continue
            mes = mes_numeric(model_p, quote.price)
            if mes is None or mes < min_mes:
                continue
            if (fixture_name, market) in already:
                continue
            if not bf.kickoff_date:
                # No kickoff date means this leg could never be settled against
                # the right match. Refuse to log it rather than create
                # something that can only be graded by guessing.
                flags.append(f"{fixture_name}: no kickoff date — leg not logged "
                             f"(it could not be settled against the correct match)")
                break
            log.log_entry(league=bf.fixture.split("(")[-1].rstrip(")"),
                           fixture=fixture_name, market=market,
                           model_prob=model_p, entry_odds=quote.price,
                           entry_capture_path="CL-LIVE", phase=PAPER_PHASE,
                           stake=None,   # Phase 2: never a stake
                           match_date=bf.kickoff_date)
            logged += 1
    flags.append(f"logged {logged} new paper leg(s) with a live entry price")
    return logged, flags


# --------------------------------------------------------------------------
# 3. THE RUN
# --------------------------------------------------------------------------

def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0) -> str:
    leagues = leagues or DEPLOY_LEAGUES
    today = date.today().isoformat()
    log = CLVLog()
    all_flags: list[str] = []

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- live entry prices for the deploy leagues ---
    odds_index: dict = {}
    for lg in leagues:
        try:
            fixtures, oflags = odds_mod.fetch_odds(lg)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags += oflags
        except odds_mod.QuotaExhausted as e:
            all_flags.append(f"{lg}: {e}")
        except Exception as e:
            all_flags.append(f"{lg}: odds fetch failed ({e}) — NO DATA — PENDING")

    # --- scan every league into one board (ID402 wide eyes) ---
    board: list = []
    for lg in leagues:
        slice_, flags = orchestrator.scan_one_league(
            lg, season, fixtures_season=fixtures_season)
        board += slice_
        all_flags += flags

    # Attach the best-EV live market to each fixture so HR30's numerical MES
    # can actually be stated, rather than falling back to an HR30 exception.
    for bf in board:
        if bf.probs is None:
            continue
        fx = odds_index.get((bf.probs.home_team, bf.probs.away_team))
        if fx is None:
            continue
        p = bf.probs
        best = None
        for market, model_p, quote in (
            (f"{p.home_team} to win", p.p_home, fx.home),
            ("Draw", p.p_draw, fx.draw),
            (f"{p.away_team} to win", p.p_away, fx.away),
            ("Over 2.5 goals", p.p_over_25, fx.over25),
            ("Under 2.5 goals", 1 - p.p_over_25, fx.under25),
        ):
            if not quote.available:
                continue
            ev = mes_numeric(model_p, quote.price)
            if ev is not None and (best is None or ev > best[0]):
                best = (ev, market, model_p, quote)
        if best:
            ev, market, model_p, quote = best
            bf.best_market, bf.best_price = market, quote.price
            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
            bf.best_mes_ev, bf.best_model_prob = ev, model_p

    shortlisted = [b for b in board if b.on_deploy_shortlist]
    capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
    for b in board:
        if b.on_deploy_shortlist and id(b) not in capped:
            b.on_deploy_shortlist = False

    # --- log the paper legs (the point of Phase 2) ---
    _, lflags = log_paper_legs(log, board, odds_index, min_mes=min_mes)
    all_flags += lflags

    status = log.phase2_status()
    all_flags.append(
        f"Phase 3 gate: {status['legs_with_clv']} of {status['gate_requirement']} "
        f"legs with logged CLV; mean CLV "
        f"{status['mean_clv_pct'] if status['mean_clv_pct'] is not None else 'NO DATA — PENDING'}")

    board_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    full = board_text + "\n\n" + "=" * 60 + "\n\n" + verify_block
    path = BOARD_DIR / f"board_{today}.txt"
    if send:
        for n in notify.deliver(full, save_to=path):
            print(f"  {n}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        print(f"  board saved to {path} (delivery skipped)")
    return full


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OLP XDV daily 07:00 run")
    ap.add_argument("--season", default="2526", help="season the model is FIT on")
    ap.add_argument("--fixtures-season", default=None)
    ap.add_argument("--leagues", nargs="+", default=None)
    ap.add_argument("--min-mes", type=float, default=0.0,
                     help="minimum EV to log a paper leg (0 = log every priced market)")
    ap.add_argument("--no-send", action="store_true", help="write the board, don't deliver")
    a = ap.parse_args()
    print(f"OLP XDV daily run — {date.today().isoformat()} — {PHASE_LABEL}")
    out = run(season=a.season, fixtures_season=a.fixtures_season,
              leagues=a.leagues, send=not a.no_send, min_mes=a.min_mes)
    print("\n" + out)
