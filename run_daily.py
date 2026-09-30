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
from engine.slate import WHITELIST_LEAGUES, build_deploy_shortlist, market_blocked
from engine.mes import mes_numeric
from engine import markets as mkt
from engine.form import compute_table, fixture_form, form_support as _form_support
from clv.clv_logger import CLVLog, compute_clv
from output.produce_bet import (render_produce_bet, render_verify_results,
                                render_canonical_board)
from output import notify
import orchestrator
import pipeline.odds as odds_mod
from pipeline.odds_sportybet import SPORTYBET_TOURNAMENT_ID

BOARD_DIR = Path(__file__).parent / "output" / "boards"
LOG_DIR = Path(__file__).parent / "logs"


def _mark_started() -> Path:
    """Write proof-of-life BEFORE anything can fail.

    The 07:00 job failed silently twice because the only evidence a run had
    happened was produced late, after several fragile steps. If this marker is
    missing after a scheduled trigger, Python never started — which is a
    different fault from Python starting and crashing, and needs a different
    fix. Distinguishing the two is the whole point."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"daily_{date.today().isoformat()}.log"
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now(timezone.utc).isoformat()}] "
                f"run_daily.py STARTED\n")
    return log


def _mark(log: Path, message: str) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")


# Leagues to pull odds for and scan. Softness tiering is retired — every
# whitelisted league is equally deploy-eligible now. The practical set is simply
# the leagues a live odds source can actually price today (SportyBet's covered
# tournaments), so a run doesn't waste a scan on leagues that could only ever
# come back NO DATA. Add a league here by giving it a SportyBet tournament ID in
# pipeline/odds_sportybet.py.
DEPLOY_LEAGUES = [lg for lg in WHITELIST_LEAGUES if lg in SPORTYBET_TOURNAMENT_ID]


# --------------------------------------------------------------------------
# 1. GRADE YESTERDAY  (VERIFY RESULTS + forward CLV)
# --------------------------------------------------------------------------

def _settle(market_key: str, fthg: int, ftag: int):
    """Delegates to the canonical registry — one settlement rule per
    market, shared with the backtest and the board."""
    return mkt.settle(market_key, fthg, ftag)


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
            q = mkt.quote(leg.market, match.odds)
            closing = q.close if q is not None else None
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

        for market in mkt.DEPLOYABLE:
            quote = mkt.quote(market, fx)
            model_p = mkt.model_prob(market, p)
            if quote is None or not quote.available or model_p is None:
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

def _has_production(board: list, logged_count: int) -> bool:
    """True when the run produced something worth delivering: at least one
    fixture on the final deploy shortlist (a real pick), or at least one new
    paper leg logged this run. An all-'NO DATA — PENDING' board with nothing
    deploy-eligible and no new leg is a quiet slate, not production — so under
    --only-production it is built and committed but NOT pushed to Telegram.

    Note: this gates DELIVERY only. The failure-alert path is separate: a run
    that errors still pages, because a failure is not a quiet slate."""
    deploy_eligible = any(getattr(b, "on_deploy_shortlist", False) for b in board)
    return deploy_eligible or logged_count > 0


def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, only_production: bool = False) -> str:
    leagues = leagues or DEPLOY_LEAGUES
    today = date.today().isoformat()
    runlog = _mark_started()
    log = CLVLog()
    all_flags: list[str] = []

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- live entry prices for the deploy leagues ---
    odds_index: dict = {}
    for lg in leagues:
        try:
            # Chained source: the-odds-api first, then football-data fixtures
            # (free, no quota) so an exhausted metered quota no longer means
            # zero entry prices — see pipeline.odds.fetch_odds_chained.
            fixtures, oflags = odds_mod.fetch_odds_chained(lg)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags += oflags
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
        # Only markets that could actually carry capital may headline THE CALL.
        # Previously the board could headline Over 2.5 (or an away win, which
        # the string-matched gate missed entirely) while the logger refused to
        # record it — recommending what the framework would not log.
        for market in mkt.DEPLOYABLE:
            quote = mkt.quote(market, fx)
            model_p = mkt.model_prob(market, p)
            if quote is None or not quote.available or model_p is None:
                continue
            ev = mes_numeric(model_p, quote.price)
            if ev is not None and (best is None or ev > best[0]):
                best = (ev, market, model_p, quote)
        if best:
            ev, market, model_p, quote = best
            bf.best_market = mkt.display(market, p.home_team, p.away_team)
            bf.best_price = quote.price
            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
            bf.best_mes_ev, bf.best_model_prob = ev, model_p

    # --- form & standings context (engine.form) ---
    # Derived from the same football-data results the model is fit on, so it
    # needs no new source. A ranking/flag signal only: it never changes a
    # probability, EV or CLV. Wrapped so a data hiccup degrades the context,
    # never the run.
    try:
        _tables: dict[str, dict] = {}
        current = orchestrator.next_season_code(season)
        for bf in board:
            if bf.probs is None:
                continue
            lg = bf.fixture.split("(")[-1].rstrip(")").strip()
            if lg not in _tables:
                tbl: dict = {}
                for s in (current, season):   # prefer the live (current) table
                    try:
                        res, _ = load_league(lg, s)
                        if res:
                            tbl = compute_table(res)
                            break
                    except Exception:
                        continue
                _tables[lg] = tbl
            table = _tables.get(lg) or {}
            if not table:
                continue
            ff = fixture_form(table, bf.probs.home_team, bf.probs.away_team)
            bf.form_summary = ff.summary()
            side = "home" if bf.probs.p_home >= bf.probs.p_away else "away"
            bf.form_support = _form_support(ff, side)
            if (bf.on_deploy_shortlist and bf.form_support is not None
                    and bf.form_support < -0.33):
                all_flags.append(f"{bf.fixture}: CAUTION — recent form runs against "
                                 f"the model's lean ({bf.form_summary})")
    except Exception as e:  # noqa: BLE001 — context is optional, the run is not
        all_flags.append(f"form/standings context unavailable ({e}) — proceeding without it")

    shortlisted = [b for b in board if b.on_deploy_shortlist]
    capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
    for b in board:
        if b.on_deploy_shortlist and id(b) not in capped:
            b.on_deploy_shortlist = False

    # --- log the paper legs (the point of Phase 2) ---
    logged_count, lflags = log_paper_legs(log, board, odds_index, min_mes=min_mes)
    all_flags += lflags

    status = log.phase2_status()
    all_flags.append(
        f"Phase 3 gate: {status['legs_with_clv']} of {status['gate_requirement']} "
        f"legs with logged CLV; mean CLV "
        f"{status['mean_clv_pct'] if status['mean_clv_pct'] is not None else 'NO DATA — PENDING'}")

    # --- real SportyBet booking codes for the deploy picks ---
    # A booking code is a shareable slip, NOT a placed bet (no stake, no account).
    # Anything that can't be resolved on SportyBet's live feed, or fails the share
    # call, stays PENDING on the board — never a fabricated code (HR35).
    acca_code = board_code = None
    try:
        from output.produce_bet import _best_market_key, _build_accas
        from pipeline import sportybet_booking as sbk

        def _leg(b):
            league = b.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
            key = _best_market_key(b.probs)[0]
            return (league, b.probs.home_team, b.probs.away_team, key)

        finalists = [b for b in board if b.on_deploy_shortlist and b.probs is not None]
        if finalists:
            sb_index = sbk._event_index()
            if sb_index is None:
                all_flags.append("SportyBet booking feed unavailable — codes PENDING")
            else:
                booked = 0
                for b in finalists:
                    leg = _leg(b)
                    if leg[3] is None:
                        continue
                    code, url = sbk.code_for_legs(sb_index, [leg])
                    if code:
                        b.booking_code, b.booking_url = code, url
                        booked += 1
                board_legs = [l for l in (_leg(b) for b in finalists) if l[3]]
                board_code, _ = sbk.code_for_legs(sb_index, board_legs)
                accas = _build_accas([b for b in board if b.on_deploy_shortlist])
                if accas:
                    acca_legs = [(bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip(),
                                  bf.probs.home_team, bf.probs.away_team,
                                  _best_market_key(bf.probs)[0])
                                 for bf, _pick, _prob in accas[0][1]]
                    if all(l[3] for l in acca_legs):
                        acca_code, _ = sbk.code_for_legs(sb_index, acca_legs)
                all_flags.append(
                    f"SportyBet booking codes: {booked}/{len(finalists)} singles resolved, "
                    f"board code {'set' if board_code else 'PENDING'}, "
                    f"Acca A {'set' if acca_code else 'PENDING'}")
    except Exception as e:  # noqa: BLE001 — codes are optional; the run is not
        all_flags.append(f"booking-code step skipped ({e}) — codes shown as PENDING")

    # The Telegram message is the Architect's canonical ##########OLP XDV#########
    # board (four tables + honest footer). The detailed HR53 per-fixture audit
    # (render_produce_bet) is preserved in the SAVED board as an appendix, so
    # the repo record keeps the full MES / Elo / divergence trail while the
    # phone gets the clean canonical board.
    telegram_text = render_canonical_board(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board,
        acca_code=acca_code, board_code=board_code)

    detail_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    full = (telegram_text
            + "\n\n" + "=" * 60 + "\n\n" + verify_block
            + "\n\n" + "=" * 60 + "\n\n"
            + "DETAIL — HR53 full per-fixture audit (not sent to Telegram)\n\n"
            + detail_text)
    path = BOARD_DIR / f"board_{today}.txt"

    # --only-production: deliver only when the run actually produced picks. This
    # keeps the phone quiet on the empty paper-calibration slates (no odds, no
    # deploy-eligible fixtures) while still committing every board to the repo.
    produced = _has_production(board, logged_count)
    deliver_now = send and (produced or not only_production)

    if deliver_now:
        delivered, notes = notify.deliver(telegram_text, save_to=None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        for n in notes:
            print(f"  {n}")
            _mark(runlog, n)
        if not delivered:
            # A run that failed to reach the phone is NOT a completed run.
            # Reporting OK here is what let three failed message parts pass as
            # success — the launcher then exits 0 and no alert fires.
            _mark(runlog, "RUN FAILED — board built but delivery incomplete")
            raise RuntimeError("Telegram delivery incomplete — see log")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        if send and only_production and not produced:
            reason = ("no production today (nothing deploy-eligible, no new leg) "
                      "— board built and committed, not delivered (--only-production)")
        else:
            reason = "delivery skipped (--no-send)"
        print(f"  board saved to {path}; {reason}")
        _mark(runlog, reason)
    _mark(runlog, "run completed OK")
    return full


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OLP XDV daily 07:00 run")
    ap.add_argument("--season", default="2526", help="season the model is FIT on")
    ap.add_argument("--fixtures-season", default=None)
    ap.add_argument("--leagues", nargs="+", default=None)
    ap.add_argument("--min-mes", type=float, default=0.0,
                     help="minimum EV to log a paper leg (0 = log every priced market)")
    ap.add_argument("--no-send", action="store_true", help="write the board, don't deliver")
    ap.add_argument("--only-production", action="store_true",
                     help="deliver to Telegram ONLY when the run produced picks "
                          "(a deploy-eligible fixture or a new paper leg); an empty "
                          "slate is committed but not sent")
    a = ap.parse_args()
    print(f"OLP XDV daily run — {date.today().isoformat()} — {PHASE_LABEL}")
    out = run(season=a.season, fixtures_season=a.fixtures_season,
              leagues=a.leagues, send=not a.no_send, min_mes=a.min_mes,
              only_production=a.only_production)
    print("\n" + out)
