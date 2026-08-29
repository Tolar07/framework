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

NOTE: This file now wires to olp_xdv_pipeline.py as the single orchestrator
      (pipeline coordination refactor, 2026-08-18). The old orchestrator.py logic
      is deprecated. run_daily.py now calls:
        from olp_xdv_pipeline import run_pipeline, render_board_from_pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Optional
import dataclasses
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# NEW: Import from unified pipeline instead of orchestrator
from olp_xdv_pipeline import run_pipeline, render_board_from_pipeline

# Legacy imports kept for CLV grading, produced-bet verification, notifications
from brain.store import Brain
from config import PHASE_LABEL, PAPER_PHASE
from data.football_data_source import load_league
from clv.clv_logger import CLVLog, compute_clv, ensemble_weights
from clv.closing_capture import capture_closing_lines
from output import notify
from output.produce_bet import render_verify_results, render_produce_bet
from output.render_fixture_list import render_fixture_list
from booking.verify_fixtures import _parse_bet365_datetime
from output import whatsapp_deliver
from output import email_deliver
import bets.produced_bet as produced_bet
from orchestrator_DEPRECATED import next_season_code, scan_one_league
import pipeline.odds as odds_mod
from data.multi_source_concrete import get_odds as multi_get_odds
from engine.acca import MAX_ODDS_CAP, build_production_bets, build_single_accas, render_production_block, _team_pair
from engine.leagues import WHITELISTED_LEAGUES, build_deploy_shortlist
import engine.recalibration as recal
import engine.markets as mkt
from engine.consensus import compute_consensus
from engine.mes import mes_numeric, edge_diff

# Pipeline Agent Bus - write stage outputs to Obsidian vault for inter-agent handoff
try:
    from pipeline_agent_bus import write_stage_output, write_agent_handoff, create_run_id as bus_create_run_id
    PIPELINE_BUS_AVAILABLE = True
except ImportError:
    PIPELINE_BUS_AVAILABLE = False

# Error tracking (Layer 13 observability)
try:
    from monitor import error_tracker
except ImportError:
    error_tracker = None

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


def _board_fixture_for_leg(board: list, leg) -> "Optional[BoardFixture]":
    """Find the BoardFixture that produced this AccaLeg by matching fixture name."""
    from typing import Optional
    from output.produce_bet import BoardFixture
    _target = getattr(leg, "fixture", None) or leg.get("fixture") if isinstance(leg, dict) else None
    if not _target:
        return None
    for bf in board:
        bf_name = getattr(bf, "fixture", "") or getattr(bf, "fixture_name", "")
        if bf_name == _target or bf_name.startswith(_target):
            return bf
    return None


def _refresh_sportybet_cache(runlog: Path, days_ahead: int = 30) -> str | None:
    """Best-effort SportyBet fixture-cache refresh ahead of the run.

    The booking bridge reads SportyBet fixtures from a TTL cache
    (data/cache/sportybet/). This warms it so the daily board can join
    SportyBet prices without a browser mid-run. Strictly best-effort: a missing
    playwright, a blocked site, or a fault is a miss, never a run failure (HR35).
    The builder is incremental — only leagues whose cache is older than 6h are
    actually re-navigated, so a warm day adds only the browser launch (~2s).
    Even when the refresh cannot run (no browser), the LOADER now accepts the
    cache up to 24h old (2026-08-11), so the board never loses every league's
    prices to a 6h window again.

    Returns a data-flag line (or None when skipped/disabled)."""
    try:
        import asyncio
        from booking.sportybet_fixtures import build_cache
        # SportyBet sidebar requires headless=False for proper rendering (debug_nav.py confirmed)
        results = asyncio.run(build_cache(days_ahead=days_ahead, headless=False))
    except Exception as e:
        msg = f"sportybet cache refresh skipped ({type(e).__name__}: {str(e)[:80]})"
        _mark(runlog, msg)
        return msg
    # build_cache returns fixture counts for EVERY league checked — a fresh
    # (skipped) cache still reports its count, so we cannot tell which were
    # actually re-navigated. Report the total honestly: the cache is warm.
    total = sum(results.values())
    n_checked = len(results)
    msg = (f"sportybet cache warm: {total} fixtures across {n_checked} "
           f"league(s) ready for the booking bridge")
    _mark(runlog, msg)
    return msg


def _retry_transient(fn, label: str, runlog: Path, delay: float = 5.0):
    """Run a network fetch, retrying once on a transient fault.

    A single connection reset / DNS blip should not degrade today's board to
    NO DATA — PENDING. Only connection/timeout/DNS exceptions are retried;
    quota exhaustion, logic errors and anything else pass straight through so
    the caller's own guard handles them. Fetches are pure (they populate TTL
    caches), so a retry is safe and idempotent."""
    import socket
    import requests
    transient = (requests.exceptions.RequestException,
                 socket.timeout, TimeoutError, OSError)
    try:
        return fn()
    except transient as e:
        msg = (f"{label}: transient {type(e).__name__} "
               f"({str(e)[:80]}) — retrying once")
        print(f"  {msg}")
        _mark(runlog, msg)
        time.sleep(delay)
        return fn()


# SCAN and DEPLOY are the SAME pool (unified, 2026-08-10): every whitelisted
# league is pulled, shown AND deploy-eligible. There is no softness A/B cap —
# build_deploy_shortlist returns every market-gate-cleared fixture. Showing a
# competition is not staking it; the market gate (engine/markets.BLOCKED) is the
# only capital restriction, and it is currently open (Architect order 2026-08-10).
SCAN_LEAGUES = list(WHITELISTED_LEAGUES)

# --- Gambler-move selection discipline (Architect 2026-08-15) -------------
# These are SELECTION-SIDE knobs (not protected gate constants): they decide
# which priced markets earn a paper-leg slot, never whether real capital may
# deploy. The Phase 3 capital gate (CLV_LOG.PHASE3_GATE_MIN_LEGS + positive
# mean CLV + ARCHITECT_SIGNOFF) is untouched.
#
# DRAW_DISCOUNT: the model overweights draws on Phase-2 legs (4/16 picks were
# draws, 0 hit, CLV -4.8% to -10% in the Scottish/Danish draw legs). Apply a
# bounded multiplicative haircut to the DRAW model probability BEFORE the EV
# screen so a draw must beat a higher bar to be logged. 0.85 = draw needs
# ~15% more apparent edge to clear. Bounded away from 0; never touches HOME/
# AWAY/BTTS/O-U. This is a visible, single-line lever, not a hidden fudge.
DRAW_DISCOUNT: float = 0.85

# MIN_MES_FLOOR: the default EV floor to LOG a paper leg. The CLI --min-mes
# override still wins. 0.0 (the old default) logs every priced market and
# fills the 30-leg gate with negative-CLV noise. 0.03 requires a real ≥3% EV
# before a leg is logged — the pro would rather reach 30 legs of POSITIVE CLV
# than 30 of mixed. This throttles gate-fill volume, it does not lower the
# gate itself.
MIN_MES_FLOOR: float = 0.03


@dataclass
class RunResult:
    """What one daily run produced, so callers can pick the render they need.

    `full` is the wide PART0-5 file board (+verify block) written to disk;
    `telegram_text` is the compact per-league table board. The 07:00 job and
    /send deliver telegram_text; /produce bet returns it too, so every channel
    shows the same brief board instead of /produce dumping the 20k file board."""
    full: str
    telegram_text: str
    board: list
    leagues_scanned: list[str]


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
        for s in {season, next_season_code(season)}:
            try:
                res, _ = load_league(lg, s)
                table.update({(r.home_team, r.away_team, r.date): r for r in res})
            except (ValueError, OSError, RuntimeError):
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

        # HR46 closing line. The ARCHIVE (CL-ARCHIVE) is the canonical close
        # and upgrades a leg that already holds a CL-LIVE capture; if the
        # archive has no price but a CL-LIVE closing line was captured near
        # kickoff, that stands — the leg still earns its CLV. Only a leg with
        # NO closing line from either path is NO DATA — PENDING.
        closing = None
        if match.odds:
            q = mkt.quote(leg.market, match.odds)
            closing = q.close if q is not None else None
        if closing is not None and leg.entry_odds:
            log.log_close(leg.leg_id, closing_odds=closing,
                           closing_capture_path="CL-ARCHIVE")
        elif leg.closing_odds is None:
            flags.append(f"{leg.fixture} / {leg.market}: no closing price in source "
                         f"— CLV stays NO DATA — PENDING, never estimated")

        graded += 1
        # The number the ledger carries is the entry-vs-close CLV; prefer the
        # (upgraded) archive close, else the CL-LIVE close captured at kickoff.
        close_display = closing if closing is not None else leg.closing_odds
        clv = (compute_clv(leg.entry_odds, close_display)
               if (close_display and leg.entry_odds) else None)
        rows.append({
            "fixture": leg.fixture,
            "ft": f"{match.fthg}-{match.ftag}",
            "onextwo": leg.market,
            "goals": f"entry {leg.entry_odds} / close {close_display if close_display else 'NO DATA — PENDING'}",
            "btts": f"CLV {clv:+.2f}%" if clv is not None else "CLV NO DATA — PENDING",
            "tally": "HIT" if hit else "MISS",
        })

    flags.append(f"graded {graded} of {len(pending)} pending leg(s)")
    return render_verify_results(rows), flags


# --------------------------------------------------------------------------
# 2. LOG TODAY'S PAPER LEGS (this is what advances the Phase 3 gate)
# --------------------------------------------------------------------------

def log_paper_legs(log: CLVLog, board: list, odds_index: dict,
                    min_mes: float = 0.0,
                    agreement_band: Optional[float] = None) -> tuple[int, list[str]]:
    """Attach a live entry price to each deploy-eligible fixture and log it.

    Without this the daily run produces a board and nothing else, the paper
    log stays empty, and the Phase 3 gate can never be reached — which is the
    entire purpose of Phase 2.

    When `agreement_band` is set (the gambler move #2 experiment), only markets
    where the model and book agree within the band are logged — so the CLV ledger
    reflects the SAME gated universe the acca builder selects from."""
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
            # Agreement gate (gambler move #2): skip markets in the disagreement bucket
            if agreement_band is not None:
                book_p = _market_implied(market, fx, quote.price)
                if book_p is None or abs(model_p - book_p) > agreement_band:
                    continue
            edge = edge_diff(model_p, quote.price)
            if edge is None or edge < min_mes:
                continue
            if (fixture_name, market) in already:
                continue
            if not bf.kickoff_date:
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
    flags.append(f"logged {logged} new paper leg(s) with a live entry price"
                 + (f" (agreement_band={agreement_band})" if agreement_band else ""))
    return logged, flags


def _market_implied(market_key: str, fx, price) -> Optional[float]:
    """Local copy of engine.acca._market_implied (devigged where possible)."""
    if fx is not None:
        if market_key in mkt.MARKETS_1X2:
            p1x2 = mkt.implied_1x2(fx)
            if p1x2 is not None:
                return p1x2[mkt.MARKETS_1X2[market_key]]
        if market_key in (mkt.OVER_25, mkt.UNDER_25):
            o = fx.over25.price if market_key == mkt.OVER_25 else fx.under25.price
            other = (fx.under25.price if market_key == mkt.OVER_25
                     else fx.over25.price)
            if o and other:
                s = 1.0 / o + 1.0 / other
                if s > 1.0:
                    return (1.0 / o) / s
    if price and price > 1.0:
        return 1.0 / price
    return None


# --------------------------------------------------------------------------
# 3. THE RUN
# --------------------------------------------------------------------------

def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, days_ahead: int = 0,
        target_date: str | None = None,
        whatsapp: bool = True, email: bool = True,
        web: bool = True, prefetch_crests: bool = False,
        refresh_sportybet: bool = False,
        booking_codes: bool = False,
        agreement_band: Optional[float] = 0.04,
        verify_only: bool = False) -> RunResult:
    """Run the daily board end to end.

    `agreement_band` (default 0.04, the measured calibrated zone — see
    engine/markets.py BLEND, the honest zone where the model agrees with the
    sharper book) is the gambler-move-#2 experiment gate: when set, legs are
    drawn ONLY from markets where the model and book agree within the band —
    the disagreement bucket the measured CLV says is the losing V5-trap. Enabled
    by Architect go-ahead (2026-08-15); explicitly an experiment flag that does
    NOT touch any protected constant.

    Opens the brain, seeds the ledger + corrections mirrors, records the run
    as 'running', and marks it FAILED on any exception — a board that never
    reached the phone is not a completed run, so the launcher can alert.

    `prefetch_crests` (default OFF so library/test callers stay offline) fetches
    missing club badges from TheSportsDB after the web payload is written. The
    CLI enables it by default (env OLP_PREFETCH_CRESTS=0 disables).

    `refresh_sportybet` (default OFF, same offline rule) warms the SportyBet
    fixture cache (data/cache/sportybet/) with a headless Chromium pass before
    the scan, so the booking bridge can join SportyBet prices. Incremental —
    only stale leagues are re-navigated — and strictly best-effort: a missing
    playwright or a fault is a flag, never a run failure (HR35). The CLI
    enables it by default (env OLP_SPORTYBET=0 or --no-sportybet disables).

    `booking_codes` (default OFF, same offline rule) drives today's acca
    payload into SportyBet's betslip with a headless Chromium pass and reads
    the BOOKING CODES SportyBet returns, writing them next to the acca payload
    so the Architect can paste a code into SportyBet to recall the slip.
    Phase 3 — codes only, never a stake (the module never clicks Place Bet;
    capital authority is the Architect's).
    Best-effort: a browser fault degrades each acca to MANUAL, never a run
    failure (HR35). The CLI enables it by default (env OLP_BOOKING_CODES=0 or
    --no-booking-codes disables).

    STRICT SINGLE-DAY PRODUCTION (Architect 2026-08-10, reversing the ratified
    2026-08-07 3-day rolling window): a run is for ONE day and one day alone.
    `target_date` (YYYY-MM-DD, default None = today) pins the production to a
    specific calendar day — the board, accas, produced-bet record and web
    payload are all written for that date, and only fixtures whose kickoff is
    exactly on that date survive. `days_ahead` is now the scan-window default
    0 = today's matches only; when `target_date` is given the scan window is
    widened just enough to reach it and the kickoff-date filter enforces the
    cut. A quiet day is an honest quiet board, never a wider net."""
    leagues = leagues or SCAN_LEAGUES
    # Gambler move #3: don't fill the Phase-3 gate with negative-CLV noise.
    # The default EV floor is MIN_MES_FLOOR (0.03); an explicit --min-mes
    # override always wins (the CLI default 0.0 activates the floor).
    min_mes = min_mes if min_mes != 0.0 else MIN_MES_FLOOR
    brain = Brain()
    run_id = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
              + "-" + uuid.uuid4().hex[:4])
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    brain.sync_legs()
    brain.sync_corrections()
    brain.append_run(run_id, started, status="running")
    try:
        return _run(run_id, started, t0, brain, season, fixtures_season,
                    leagues, send, min_mes, days_ahead, target_date,
                    whatsapp, email, web, prefetch_crests, refresh_sportybet,
                    booking_codes, agreement_band, verify_only)
    except Exception as exc:
        brain.update_run(run_id, status="failed")
        # Record to error tracker (Layer 13 observability)
        if error_tracker:
            try:
                error_tracker.record_error(
                    exc, context="run_daily.run",
                    tags=["daily-run", "unhandled"])
            except (RuntimeError, ValueError, AttributeError):
                pass  # error tracking must never break the run further
        raise
    finally:
        brain.close()


def _run(run_id: str, started: str, t0: float, brain: Brain,
         season: str, fixtures_season: str | None, leagues: list[str],
         send: bool, min_mes: float, days_ahead: int,
         target_date: str | None = None,
         whatsapp: bool = True, email: bool = True,
         web: bool = True, prefetch_crests: bool = False,
         refresh_sportybet: bool = False,
         booking_codes: bool = False,
         agreement_band: Optional[float] = None,
         verify_only: bool = False) -> RunResult:
    """The body of the daily run (wrapped by run() for brain bookkeeping)."""
    today = date.today().isoformat()
    # STRICT SINGLE-DAY (Architect 2026-08-10): the production is pinned to ONE
    # board date — the automated daily run produces today, a manual trigger pins
    # to its selected date. The scan window only has to REACH that day; the
    # kickoff_date filter on the scanned board is the hard guarantee that
    # nothing from an adjacent day survives.
    board_date = target_date or today
    scan_window = max(0, (date.fromisoformat(board_date) - date.today()).days)
    runlog = _mark_started()
    log = CLVLog()
    all_flags: list[str] = []

    # --- warm the SportyBet fixture cache BEFORE the scan, so the booking
    # --- bridge can join SportyBet prices onto the board. Best-effort: a
    # --- fault is a flag, never a run failure (HR35). Incremental: only
    # --- leagues whose 6h-old cache is stale are re-navigated (the loader
    # --- accepts up to 24h, so a failed refresh is a miss, not a wipe). ---
    if refresh_sportybet:
        flag = _refresh_sportybet_cache(runlog)
        if flag:
            all_flags.append(flag)

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    # Phase 4.2: automated CLV grading — settle every pending paper leg
    # against the settled record and capture its closing price (CL-ARCHIVE).
    # grade_open_legs is the run_daily-specific richer renderer; the logger's
    # grade_all_pending is the canonical automated path shared with the CLI.
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags
    try:
        auto_summary, auto_flags = log.grade_all_pending(season)
        all_flags += [f for f in auto_flags
                      if not any(f.split(":")[0] == g.split(":")[0] for g in gflags)]
    except Exception as e:
        all_flags.append(f"automated CLV grading failed ({e})")

    # --- produced-bet verification (ID415): settle YESTERDAY's produced legs
    # --- against real results and record outcomes in the brain, so today's
    # --- board shows what the framework bet yesterday and whether it won. ---
    try:
        vsum = produced_bet.verify_produced_bet(season, brain)
        if vsum.get("n"):
            all_flags.append(
                f"produced-bet verified {vsum['date']}: "
                f"{vsum['won']} won / {vsum['lost']} lost / "
                f"{vsum['pending']} pending")
    except Exception as e:
        # a produced-bet verification fault must never kill the daily board —
        # verification stays PENDING rather than guessed (HR35).
        all_flags.append(f"produced-bet verification failed ({e}) — "
                         f"legs stay PENDING")

    # --- booking tracker settle: grade YESTERDAY's produced legs against
    # --- football-data + ESPN results. This is the thin settlement wrapper
    # --- that mirrors produced_bet verification but writes the tracker's
    # --- per-leg status/ft_result/hit into produced_<date>.json. ---
    try:
        from bets.booking_tracker import settle as _tracker_settle
        _yesterday = (date.today() - timedelta(days=1)).isoformat()
        _set = _tracker_settle(target_date=_yesterday)
        if _set.get("settled") or _set.get("pending"):
            all_flags.append(
                f"booking tracker settled {_yesterday}: "
                f"{_set.get('settled',0)} graded ({_set.get('wins',0)}W/{_set.get('losses',0)}L), "
                f"{_set.get('pending',0)} pending")
            for _err in _set.get("errors", [])[:3]:
                all_flags.append(f"  tracker settle: {_err}")
    except Exception as e:
        # tracker.settle is additive — a fault must never kill the board
        all_flags.append(f"booking tracker settle skipped ({type(e).__name__}: {str(e)[:80]})")

    # ===== PIPELINE BUS: Stage 1 (macro_ingestion) -> Stage 2 (list_filter) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(1, {
                "phase": "CLV_GRADING",
                "verify_block": verify_block[:200] if verify_block else "",
                "flags": gflags,
                "season": season,
            }, run_id=run_id, metadata={"duration_sec": round(time.time() - t0, 1)})
            graded_count = 0
            if auto_summary and isinstance(auto_summary, dict):
                graded = auto_summary.get("graded", [])
                graded_count = len(graded) if isinstance(graded, list) else 0
            write_agent_handoff(1, 2, {
                "graded_legs": graded_count,
                "season": season,
                "flags": all_flags.copy(),
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 1 handoff failed ({e})")

    # ===== STAGE A ARTIFACT LOADING (4am fixture extraction output) =====
    # If a Stage A artifact exists for today's board date, load it instead of
    # re-running the full fixture scan. The artifact is produced by the 04:00
    # GitHub Actions workflow (fixture-extraction.yml) and contains the complete
    # fixture universe with ID403 verification already applied.
    from pipeline.fixture_extraction import StageAOutput, VerifiedFixture
    from pathlib import Path
    stage_a_path = Path(__file__).parent / "data" / "stage_a_output" / f"fixtures_{board_date}_{fixtures_season or season}.json"
    board: list = []
    fixture_sources: set[str] = set()
    fit_stats = {"dc_reused": 0, "dc_refit": 0, "elo_seeded": 0, "pool_built": 0,
                 "xg_leagues": 0}
    stage_a_loaded = False

    if stage_a_path.exists():
        try:
            stage_a = StageAOutput.load(stage_a_path)
            # Convert VerifiedFixture objects to the board fixture format
            # expected by the rest of the pipeline (scan_one_league output)
            for vf in stage_a.fixtures:
                # Only include fixtures for the board date that haven't kicked off yet
                if vf.kickoff_date == board_date and not vf.kicked_off:
                    fixture_sources.add(vf.source or "stage_a")
                    # Build a minimal FixtureRow-compatible object
                    # The pipeline expects objects with fixture, kickoff_date, league attrs
                    bf = type('BoardFixture', (), {
                        'fixture': f"{vf.home_team} v {vf.away_team} ({vf.league})",
                        'home_team': vf.home_team,
                        'away_team': vf.away_team,
                        'league': vf.league,
                        'kickoff_utc': vf.kickoff_utc,
                        'kickoff_date': vf.kickoff_date,
                        'verification_tier': vf.verification_tier,
                        'verification_note': vf.verification_note,
                        'verification_factors': vf.verification_factors,
                        'source': vf.source,
                        'source_tier': vf.source_tier,
                        'status': vf.status,
                        'flags': vf.flags,
                        'kicked_off': vf.kicked_off,
                        'probs': None,  # Will be filled by engine later
                        'elo_probs': None,
                        'xg_probs': None,
                        'on_deploy_shortlist': False,
                        'best_market': None,
                        'best_price': None,
                        'best_bookmaker': None,
                        'best_n_books': None,
                        'best_mes_ev': None,
                        'best_model_prob': None,
                        'best_market_key': None,
                        'cal_adjustment': None,
                        'mes_trigger_price': None,
                    })()
                    board.append(bf)
            stage_a_loaded = True
            all_flags.append(f"Stage A artifact loaded: {len(board)} upcoming fixtures for {board_date} from {stage_a_path.name}")
            fit_stats["leagues_scanned"] = len(stage_a.leagues_scanned)
            fit_stats["leagues_with_fixtures"] = stage_a.stats.get("leagues_with_fixtures", 0)
        except Exception as e:
            all_flags.append(f"Stage A artifact load failed ({e}) — falling back to live scan")
            board = []
            fixture_sources = set()

    # --- scan every league into one board (ID402 wide eyes). The board is for
    # --- ONE day (Architect 2026-08-10, reversing the 2026-08-07 3-day rolling
    # --- window): the automated daily run produces today's matches only, and a
    # --- manual trigger pins the run to its selected date. The scan window
    # --- reaches the board date (scan_window); the kickoff_date filter below
    # --- then drops anything that does not kick off on that exact day, so a
    # --- quiet day is an honest quiet board, never a wider net.
    # --- Each league reports its fit outcome (reused vs refit, seeded vs cold)
    # --- so the run row proves the brain's speed win rather than assuming it.
    if not stage_a_loaded:
        for lg in leagues:
            st: dict = {}
            slice_, flags = scan_one_league(
                lg, season, fixtures_season=fixtures_season,
                days_ahead=scan_window,
                brain=brain, stats=st)
            board += slice_
            all_flags += flags
            for k in fit_stats:
                fit_stats[k] += int(st.get(k, False))
            if st.get("fixture_source"):
                fixture_sources.add(st["fixture_source"])
            # Strict-day pacing (today-only runs only): a league with no today
            # fixture in its cached season feed falls back to TheSportsDB's
            # eventsday endpoint. The free key rate-limits at ~1 req/s, so a
            # back-to-back per-league burst can 429 a league that DOES have today's
            # fixtures into a false NO DATA — PENDING. Pacing the per-league calls
            # keeps that from happening. Future-target runs use the cached season
            # feed and need no throttle (inert there).
            if scan_window == 0:
                time.sleep(1.1)
        # Strict-day pacing (today-only runs only): a league with no today
        # fixture in its cached season feed falls back to TheSportsDB's
        # eventsday endpoint. The free key rate-limits at ~1 req/s, so a
        # back-to-back per-league burst can 429 a league that DOES have today's
        # fixtures into a false NO DATA — PENDING. Pacing the per-league calls
        # keeps that from happening. Future-target runs use the cached season
        # feed and need no throttle (inert there).
        if scan_window == 0:
            time.sleep(1.1)

    # Strict single-day cut: the fixture sources return a WINDOW, so trim the
    # board to the board date. A fixture without a kickoff date cannot be
    # proven to be on the day and is refused rather than guessed (HR35).
    scanned = len(board)
    board = [b for b in board if (b.kickoff_date or "") == board_date]
    if len(board) != scanned:
        all_flags.append(
            f"day-scoped to {board_date}: kept {len(board)} of {scanned} "
            f"scanned fixture(s) — adjacent-day matches dropped")

    # ===== MANDATORY FIXTURE VERIFICATION GATE (Architect directive 2026-08-16
    # ===== — STOP FABRICATION). Every board fixture must be confirmed by BOTH
    # ===== independent live sources (SportyBet cache + FlashScore feed) before it
    # ===== can be priced, scored, or booked. A fixture only one source knows
    # ===== about is unverifiable and is DROPPED (with a loud flag) — shipping it
    # ===== is exactly the fabrication this ends. Double outage (neither source
    # ===== has data) -> keep-but-warn, never guess (HR35). Runs BEFORE the odds
    # ===== pull so bad fixtures never reach the engine, production, or booking.
    from booking.verify_fixtures import verify_board
    board, _verify_report = verify_board(board, board_date, leagues)
    all_flags.append(
        f"VERIFY GATE: {_verify_report.verified} verified, "
        f"{_verify_report.kept_unverified} kept-unverified, "
        f"{_verify_report.dropped_missing_source} dropped "
        f"(FlashScore {'on' if _verify_report.flashscore_available else 'OFF'}, "
        f"SportyBet {'on' if _verify_report.sportybet_available else 'OFF'})")
    all_flags += _verify_report.flags
    if _verify_report.outage:
        all_flags.append(f"⚠ VERIFY GATE OUTAGE: {_verify_report.outage_reason}")

    # ===== RECALCULATE on_deploy_shortlist AFTER VERIFICATION (Architect 2026-08-19)
    # ===== Hard rule: verify gate NEVER drops any fixture. All fixtures with
    # ===== live prices (probs or SportyBet odds or MES) must reach production.
    # ===== The verification stamp informs downstream but does NOT gate deployment.
    from engine.leagues import is_deploy_eligible
    from verification.id403 import Tier
    for bf in board:
        # Extract league inline since _league_of is defined later
        league = bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture else "—"
        has_probs = bf.probs is not None
        has_sb_odds = any(getattr(bf, attr, None) is not None
                          for attr in ("sb_home_odds", "sb_draw_odds", "sb_away_odds"))
        has_mes = bf.mes_trigger_price is not None
        bf.on_deploy_shortlist = (is_deploy_eligible(league)
                                   and bf.verification.tier != Tier.CONFLICT
                                   and (has_probs or has_sb_odds or has_mes))
    # Count how many fixtures are now deploy-eligible
    deployable_count = sum(1 for bf in board if bf.on_deploy_shortlist)
    all_flags.append(f"DEPLOY SHORTLIST RECALCULATED: {deployable_count} of {len(board)} fixtures on deploy shortlist (verify gate stamps preserved)")

    if verify_only:
        # Pre-flight / audit mode: print the verification report and stop before
        # any odds pull, engine scoring, production, or booking.
        _mark(runlog, "verify-only: stopping before odds pull")
        return RunResult(
            full=_verify_report.summary(),
            telegram_text=_verify_report.summary(),
            board=[],
            leagues_scanned=leagues,
        )

    # Multi-source health (data/multi_source_concrete.py): which provider served
    # each league is visible per-run so a silently-degraded source (circuit open,
    # fallback in use) is never mistaken for the primary serving. Backup providers
    # are normal on quiet days; an OPEN circuit is worth a flag. The registry
    # health report is {name: {sources: [{name, health, ...}]}} — unwrap it.
    from data.multi_source_concrete import get_all_health
    health = get_all_health()
    opened = []
    for ms_report in health.get("sources", {}).values():
        for s in ms_report.get("sources", []):
            if s.get("health") == "circuit_open":
                opened.append(s.get("name"))
    if opened:
        all_flags.append(f"⚠ source circuit OPEN (paused): {', '.join(opened)}")
    if fixture_sources and any(s != "thesportsdb" for s in fixture_sources):
        all_flags.append(f"Fixtures served by: {', '.join(sorted(fixture_sources))}")

    # ===== PIPELINE BUS: Stage 2 (list_filter) output -> Stage 3 (entity_profiling) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(2, {
                "phase": "SCAN_COMPLETE",
                "leagues_scanned": len(leagues),
                "board_size": len(board),
                "fixture_sources": sorted(fixture_sources),
                "board_date": board_date,
            }, run_id=run_id, metadata={"fixtures": len(board)})
            write_agent_handoff(2, 3, {
                "board": [bf.fixture for bf in board],
                "leagues": leagues,
                "board_date": board_date,
                "fit_stats": fit_stats,
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 2 handoff failed ({e})")

    # --- live entry prices, pulled for ALL deploy-eligible fixtures.
    # --- Hard rule (Architect 2026-08-19): ALL fixtures with live prices must
    # --- produce a bet — newly promoted teams without model probs use
    # --- market-implied probabilities as fallback so no fixture is ever dropped.
    # --- We pull odds for ALL leagues with deploy-shortlist fixtures, not just
    # --- those with model probs.
    def _league_of(bf) -> str:
        return bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture \
            else "—"
    # Pull odds for all leagues that have ANY deploy-shortlist fixture
    odds_leagues = {_league_of(bf) for bf in board if getattr(bf, "on_deploy_shortlist", False)}
    odds_index: dict = {}
    for lg in sorted(odds_leagues):
        try:
            # Multi-source odds with automatic failover: API-Football paid (primary) -> Odds API UK -> Odds API EU
            fixtures = multi_get_odds(lg)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags.append(f"{lg}: odds served via multi-source layer")
        except Exception as e:
            all_flags.append(f"{lg}: odds fetch failed ({e}) — NO DATA — PENDING")

    # --- Merge SportyBet cache odds for leagues with SportyBet data but no multi-source odds ---
    # This ensures fixtures like Champions League (SportyBet-only) get priced for paper legs
    try:
        from booking.bridge import load_all_sportybet_fixtures
        sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=3, leagues=list(odds_leagues))
        sb_odds_count = 0
        for lg, sb_fixtures in sb_fixtures_by_league.items():
            for sb_fx in sb_fixtures:
                if sb_fx.home_odds and sb_fx.draw_odds and sb_fx.away_odds:
                    key = (sb_fx.home_team, sb_fx.away_team)
                    if key not in odds_index:
                        # Create FixtureOdds from SportyBet cache
                        sb_odds = odds_mod.FixtureOdds(
                            league=lg,
                            home_team=sb_fx.home_team,
                            away_team=sb_fx.away_team,
                            kickoff_utc=sb_fx.kickoff_utc,
                            home=odds_mod.MarketQuote(
                                price=sb_fx.home_odds,
                                bookmaker="SportyBet Nigeria",
                                n_books=1,
                                captured_at=sb_fx.kickoff_utc
                            ),
                            draw=odds_mod.MarketQuote(
                                price=sb_fx.draw_odds,
                                bookmaker="SportyBet Nigeria",
                                n_books=1,
                                captured_at=sb_fx.kickoff_utc
                            ),
                            away=odds_mod.MarketQuote(
                                price=sb_fx.away_odds,
                                bookmaker="SportyBet Nigeria",
                                n_books=1,
                                captured_at=sb_fx.kickoff_utc
                            ),
                            source="sportybet-cache",
                            source_tier="T2"
                        )
                        odds_index[key] = sb_odds
                        sb_odds_count += 1
        if sb_odds_count:
            all_flags.append(f"SportyBet cache merged: {sb_odds_count} fixture(s) with 1X2 odds added to odds_index")

        # --- Attach SportyBet fixture IDs to board fixtures for booking code generation ---
        # The booking code generator needs sportybet_fixture_id on each board fixture
        # to find the fixture in the SportyBet cache. We use the same sb_fixtures_by_league
        # that we just loaded for odds merging.
        try:
            attached_count = 0
            for bf in board:
                if bf.kickoff_date != board_date:
                    continue
                league = _league_of(bf)
                if league not in sb_fixtures_by_league:
                    continue
                home, away = _team_pair(bf)
                for sb_fx in sb_fixtures_by_league[league]:
                    # Match on model keys (same as odds_index lookup)
                    if sb_fx.home_team == home and sb_fx.away_team == away:
                        bf.sportybet_fixture_id = sb_fx.sportybet_fixture_id
                        attached_count += 1
                        break
            if attached_count:
                all_flags.append(f"SportyBet fixture IDs attached: {attached_count} board fixture(s) tagged for booking")
        except Exception as e:
            all_flags.append(f"SportyBet fixture ID attach failed ({e})")

    except Exception as e:
        all_flags.append(f"SportyBet cache merge failed ({e})")

    # --- Merge Bet365 odds feed (bet365_odds_*.jsonl) for ALL canonical markets ---
    # This feed carries 1X2 + Totals 0.5/1.5/2.5/3.5 + BTTS + DC + DNB + HT/FT + Correct Score
    # Each market odds is zoned (SAFE/5050/WATCH/FLOOR/NONE) per MAX_ODDS_CAP/PREFERRED_ODDS_CEILING/MIN_ODDS_FLOOR
    try:
        from pathlib import Path
        live_odds_dir = Path(__file__).parent.parent / "data" / "live_odds"
        bet365_odds_files = sorted(live_odds_dir.glob("bet365_odds_*.jsonl"), reverse=True)
        if bet365_odds_files:
            latest_bet365_odds = bet365_odds_files[0]
            b365_odds_count = 0
            b365_markets_count = 0
            for line in latest_bet365_odds.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "match_odds":
                    continue
                home_team = entry.get("home_team", "")
                away_team = entry.get("away_team", "")
                if not home_team or not away_team:
                    continue
                key = (home_team, away_team)
                markets = entry.get("markets", {})
                if not markets:
                    continue
                # Build FixtureOdds with all available markets from Bet365
                raw_dt = entry.get("match_datetime", "")
                fx = odds_mod.FixtureOdds(
                    league=entry.get("league", ""),
                    home_team=home_team,
                    away_team=away_team,
                    kickoff_utc=_parse_bet365_datetime(raw_dt),
                    source="bet365-odds",
                    source_tier="T1"
                )
                for mkt_key, mkt_data in markets.items():
                    price = mkt_data.get("price")
                    if price is None:
                        continue
                    zone = mkt_data.get("zone", "NONE")
                    # Only add markets that are within MAX_ODDS_CAP for capital deployment
                    # (the engine's _best_deployable_leg will apply the hard ceiling anyway,
                    # but we keep all zoned markets visible for transparency)
                    # Map canonical keys to FixtureOdds attributes
                    if mkt_key == "1X2_HOME":
                        fx.home = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "1X2_DRAW":
                        fx.draw = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "1X2_AWAY":
                        fx.away = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "OVER_0_5":
                        fx.over05 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "UNDER_0_5":
                        fx.under05 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "OVER_1_5":
                        fx.over15 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "UNDER_1_5":
                        fx.under15 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "OVER_2_5":
                        fx.over25 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "UNDER_2_5":
                        fx.under25 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "OVER_3_5":
                        fx.over35 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "UNDER_3_5":
                        fx.under35 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "BTTS_YES":
                        fx.btts_yes = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "BTTS_NO":
                        fx.btts_no = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "DC_1X":
                        fx.dc_1x = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "DC_X2":
                        fx.dc_x2 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "DC_12":
                        fx.dc_12 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "DNB_HOME":
                        fx.dnb_home = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "DNB_AWAY":
                        fx.dnb_away = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_11":
                        fx.htft_11 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_1X":
                        fx.htft_1x = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_12":
                        fx.htft_12 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_X1":
                        fx.htft_x1 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_XX":
                        fx.htft_xx = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_X2":
                        fx.htft_x2 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_21":
                        fx.htft_21 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_2X":
                        fx.htft_2x = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "HT_FT_22":
                        fx.htft_22 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_1_0":
                        fx.cs_10 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_0_1":
                        fx.cs_01 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_1_1":
                        fx.cs_11 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_2_0":
                        fx.cs_20 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_0_2":
                        fx.cs_02 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_2_1":
                        fx.cs_21 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_1_2":
                        fx.cs_12 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_2_2":
                        fx.cs_22 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_0_0":
                        fx.cs_00 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_3_0":
                        fx.cs_30 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_0_3":
                        fx.cs_03 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_3_1":
                        fx.cs_31 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    elif mkt_key == "CS_1_3":
                        fx.cs_13 = odds_mod.MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                    b365_markets_count += 1
                if key not in odds_index:
                    odds_index[key] = fx
                    b365_odds_count += 1
            if b365_odds_count:
                all_flags.append(f"Bet365 odds merged: {b365_odds_count} fixture(s), {b365_markets_count} market-odds added to odds_index")
    except Exception as e:
        all_flags.append(f"Bet365 odds merge failed ({e})")

    # CLV-gated recalibration: the engine's probabilities for THE CALL's EV are
    # nudged by settled-leg evidence ONLY where a market has enough logged CLV
    # legs (engine/recalibration.py). Inert until that evidence exists — right
    # now it is entirely dormant. The ledger still stores the RAW model_prob.
    cal = recal.adjustments_for(brain.calibration_by_market())
    if cal:
        all_flags.append("Calibration active: "
                         + ", ".join(f"{m} {d:+.1%}" for m, d in sorted(cal.items()))
                         + " (from settled-leg CLV evidence, bounded ±3pts)")
    # SHADOW trace: the would-be adjustment on markets below the MIN_LEGS gate.
    # Surfaced for honesty (the signal is visible as it builds) but NEVER applied
    # — the engine only changes once a market crosses MIN_LEGS. Markets already
    # in `cal` are the live ones and are NOT repeated here.
    shadow = recal.shadow_adjustments(brain.calibration_by_market())
    pending = {m: d for m, d in shadow.items() if m not in cal}
    if pending:
        all_flags.append("SHADOW calibration (below gate, NOT applied): "
                         + ", ".join(f"{m} {d:+.1%}"
                                     for m, d in sorted(pending.items()))
                         + " — visible only; inert until MIN_LEGS legs settle")

    # PLATT SCALING (Phase 3.1): a per-market calibration CURVE fitted on the
    # settled-prediction record (raw model_prob -> outcome), correcting
    # confidence that is miscalibrated at some points of the range but not
    # others. Same gates as the flat nudge — a market needs PLATT_MIN_LEGS
    # settled predictions before any curve exists, and the fit is shrunk to
    # identity on thin samples. Inert today (no settled record). The ledger
    # keeps the RAW model_prob; only the EV decision is priced on the curve.
    platt_ev = brain.platt_evidence(engine="dc")
    platt = recal.platt_scalers(platt_ev)
    if platt:
        all_flags.append("PLATT calibration active: "
                         + ", ".join(f"{m} n={s.n} a={s.a:+.2f} b={s.b:.2f}"
                                     for m, s in sorted(platt.items()))
                         + " (curve on settled predictions, shrunk to identity)")
    shadow_platt = recal.shadow_platt_scalers(platt_ev)
    platt_pending = {m: s for m, s in shadow_platt.items() if m not in platt}
    if platt_pending:
        all_flags.append("SHADOW PLATT (below gate, NOT applied): "
                         + ", ".join(f"{m} n={s.n}"
                                     for m, s in sorted(platt_pending.items()))
                         + " — visible only; inert until PLATT_MIN_LEGS settle")

    # ENSEMBLE WEIGHTS (Phase 3.3) — per-engine consensus weights from the
    # settled record: does an engine beat the close on the markets it calls,
    # and is it well-calibrated on its own predictions? CLV-gated and bounded
    # (clv/clv_logger.ensemble_weights): with no settled evidence every weight
    # is 1.0 and the consensus stays the classic equal vote. Weights shape the
    # DISPLAY-only consensus; DC stays canonical for legs, CLV and calibration.
    engine_weights = None
    try:
        engine_weights, ew_info = ensemble_weights(
            brain.engine_clv(), brain.engine_calibration())
        all_flags.append(ew_info["flag"])
    except Exception as e:
        all_flags.append(f"ensemble weights unavailable ({str(e)[:60]}) "
                         f"— consensus unweighted")

    # Attach the best-EV live market to each fixture so HR30's numerical MES
    # can actually be stated, rather than falling back to an HR30 exception.
    #
    # BOOKMAKER (ID413) + MARKET-ANCHORED PROBABILITY (ID414):
    # The devigged implied 1X2 is the model's fourth opinion (real money), and
    # the board DISPLAYS a probability pulled toward this market when the model
    # and market disagree (the honest number — not the raw overconfident one).
    # EV is priced on the blended probability too, so the board never presents
    # model-vs-market disagreement as phantom value. Both computed BEFORE the
    # EV loop so the blend is available for every market decision. Ledger
    # stores the RAW model_prob — no feedback loop.
    #
    # Per-market implied: the devigged probability for the specific market key,
    # so O2.5/U2.5 are anchored alongside the 1X2.
    def _market_implied(market: str, fx, price=None) -> Optional[float]:
        if fx is not None:
            if mkt.MARKETS_1X2.get(market) is not None:
                p1x2 = mkt.implied_1x2(fx)
                return p1x2[mkt.MARKETS_1X2[market]] if p1x2 else None
            if market in (mkt.OVER_25, mkt.UNDER_25):
                o = fx.over25.price if market == mkt.OVER_25 else fx.under25.price
                other = (fx.under25.price if market == mkt.OVER_25
                         else fx.over25.price)
                if o and other:
                    s = 1.0 / o + 1.0 / other
                    if s > 1.0:
                        return (1.0 / o) / s
            # multi-market anchors (BTTS / O1.5 / DC)
            if market == mkt.OVER_15 and fx.over15 and fx.over15.price:
                return 1.0 / fx.over15.price
            if market == mkt.UNDER_15 and fx.under15 and fx.under15.price:
                return 1.0 / fx.under15.price
            if market == mkt.BTTS_YES and fx.btts_yes and fx.btts_yes.price:
                return 1.0 / fx.btts_yes.price
            if market == mkt.BTTS_NO and fx.btts_no and fx.btts_no.price:
                return 1.0 / fx.btts_no.price
            if market == mkt.DC_1X and fx.dc_1x and fx.dc_1x.price:
                return 1.0 / fx.dc_1x.price
            if market == mkt.DC_X2 and fx.dc_x2 and fx.dc_x2.price:
                return 1.0 / fx.dc_x2.price
            if market == mkt.DC_12 and fx.dc_12 and fx.dc_12.price:
                return 1.0 / fx.dc_12.price
        if price and price > 1.0:
            return 1.0 / price
        return None

    # Helper: try to find odds in index with normalized/alias matching
    def _find_odds(board_home: str, board_away: str) -> Optional[Any]:
        """Find fixture odds trying multiple key strategies."""
        # 1. Exact match
        fx = odds_index.get((board_home, board_away))
        if fx is not None:
            return fx
        # 2. Try resolve_team (OLP model key -> SportyBet name) for both sides
        try:
            from booking.team_map import resolve_team
            sb_home = resolve_team(board_home, "sportybet")
            sb_away = resolve_team(board_away, "sportybet")
            fx = odds_index.get((sb_home, sb_away))
            if fx is not None:
                return fx
        except (AttributeError, TypeError, KeyError):
            pass
        # 3. Normalized match (case/diacritic/prefix-insensitive)
        try:
            from booking.team_map import _normalize
            nh, na = _normalize(board_home), _normalize(board_away)
            for (oh, oa), f in odds_index.items():
                noh, noa = _normalize(oh), _normalize(oa)
                if noh == nh and noa == na:
                    return f
                # 3b. Prefix/suffix tolerant: one name contains the other
                # (e.g. "FC ST. Gallen" vs "FC St. Gallen 1879")
                def _contains(a: str, b: str) -> bool:
                    return a == b or (len(a) > 3 and (a in b or b in a))
                if _contains(noh, nh) and _contains(noa, na):
                    return f
        except (AttributeError, TypeError, KeyError):
            pass
        return None

    for bf in board:
        # Get fixture key for odds lookup
        home, away = _team_pair(bf)
        fx = _find_odds(home, away)
        if fx is None:
            continue
        p = bf.probs

        # BOOKMAKER (ID413) + MARKET-ANCHORED PROBABILITY (ID414): compute
        # the devigged implied 1X2 and the blend before the EV loop so both
        # are available for every market decision.
        if p is not None:
            bf.market_probs = mkt.implied_1x2(fx)
            if bf.market_probs is not None:
                bf.consensus = compute_consensus(
                    bf.probs, bf.elo_probs, bf.xg_probs, bf.market_probs,
                    engine_weights=engine_weights)
                mh, md, ma = bf.market_probs
                bp = (mkt.blend_toward_market(p.p_home, mh),
                      mkt.blend_toward_market(p.p_draw, md),
                      mkt.blend_toward_market(p.p_away, ma))
                if any(abs(bp[i] - v) > 0.005
                       for i, v in enumerate((p.p_home, p.p_draw, p.p_away))):
                    bf.blend_probs = bp

        best = None
        for market in mkt.EDGE_MARKETS:
            quote = mkt.quote(market, fx)
            if p is not None:
                raw_p = mkt.model_prob(market, p)
            else:
                # Use market-implied probability as fallback for newly promoted teams
                raw_p = _market_implied(market, fx)
            if quote is None or not quote.available or raw_p is None:
                continue
            # HARD ODDS CAP (FL-bias guardrail, mirrors engine.acca._best_deployable_leg):
            # reject any market priced above MAX_ODDS_CAP. A leg the deploy engine
            # would refuse must not be headlined as THE CALL's best market — that
            # is exactly the Viking @4.20 trap. This keeps the call in the
            # favourite/short-price zone where CLV has been positive.
            if quote.price > MAX_ODDS_CAP:
                continue
            # DRAW DISCOUNT (gambler move #2): the model overweighted draws on
            # Phase-2 legs. Haircut the DRAW model prob before the EV screen so
            # a draw must clear a higher bar. HOME/AWAY/BTTS/O-U are untouched.
            model_p_in = raw_p * DRAW_DISCOUNT if market == mkt.DRAW else raw_p
            # EV is priced on the BLEND — the honest probability when model
            # and market disagree (ID414). Ledger keeps RAW model_est via
            # best_model_prob; calibration stays inert (no feedback loop).
            mp = _market_implied(market, fx)
            p_model = recal.apply(model_p_in, cal.get(market))
            p_model = recal.apply_platt(p_model, platt.get(market))
            p_ev = mkt.blend_toward_market(p_model, mp)
            # ARCHITECT 2026-08-29: THE CALL headlines the BEST EV market across
            # the whole EDGE_MARKETS universe (1X2 + O1.5/O2.5/O3.5 + BTTS +
            # Double Chance). EV = model_prob × price − 1 (MES), not the
            # probability-gap edge — the model's own calibrated currency of
            # expected value per unit staked. Every market carries its own live
            # price (HR35), so alt markets compete on equal footing.
            ev = p_ev * quote.price - 1 if quote.price else None
            if ev is not None and (best is None or ev > best[0]):
                best = (ev, market, raw_p, quote, p_model)
        if best:
            edge, market, raw_p, quote, p_model = best
            # Use fixture name for display when no model probs
            if p is not None:
                best_market_display = mkt.display(market, p.home_team, p.away_team)
            else:
                # Use fixture name directly
                best_market_display = mkt.display(market, home, away)
            bf.best_market = best_market_display
            bf.best_price = quote.price
            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
            bf.best_mes_ev = edge  # canonical edge (prob gap) on the blend; raw prob on the ledger
            bf.best_model_prob = raw_p  # ledger keeps the RAW model estimate
            bf.best_market_key = market  # canonical key for the brain's ledger
            bf.cal_adjustment = round(p_model - raw_p, 4)

    # --- never forget a prediction: persist every rated board prediction ---
    n_preds = _predictions_from_board(board, run_id, started, brain)

    shortlisted = [b for b in board if b.on_deploy_shortlist]
    capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
    for b in board:
        if b.on_deploy_shortlist and id(b) not in capped:
            b.on_deploy_shortlist = False

    # ===== PIPELINE BUS: Stage 3 (entity_profiling) output -> Stage 4 (data_verification) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            priced = [bf for bf in board if bf.best_mes_ev is not None]
            write_stage_output(3, {
                "phase": "ENTITY_PROFILING",
                "predictions_logged": n_preds,
                "priced_fixtures": len(priced),
                "shortlisted": len(shortlisted),
                "capped": len(capped),
            }, run_id=run_id, metadata={"n_preds": n_preds})
            write_agent_handoff(3, 4, {
                "priced_fixtures": [bf.fixture for bf in priced],
                "n_preds": n_preds,
                "shortlisted": len(shortlisted),
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 3 handoff failed ({e})")

    # --- THE BOARD DATE'S PRODUCTION BETS (production intent 2026-08-10):
    # --- Acca A (headline, top 4-5 by confidence) + the remainder split into
    # --- ~4-5 leg accas + a standalone single per remainder fixture — all from
    # --- today's deploy-eligible shortlist, priced on the live line in
    # --- capital-cleared markets (ID405). Named in the board + Telegram + web;
    # --- the same payload feeds the SportyBet booking-code generator. ---
    production = build_production_bets(board, today=board_date,
                                       odds_index=odds_index,
                                       agreement_band=agreement_band)
    acca_list: list = []
    if production.acca_a is not None:
        acca_list.append(production.acca_a)
    acca_list += production.split_accas
    acca_list += build_single_accas(production.singles)
    if production.acca_a or production.split_accas or production.singles:
        all_flags.append(
            f"production bets: "
            f"{production.acca_a.n_legs if production.acca_a else 0} leg(s) in "
            f"Acca A, {len(production.split_accas)} split acca(s), "
            f"{len(production.singles)} single(s) on today's slate")

    # ===== PIPELINE BUS: Stage 4 (data_verification) output -> Stage 5 (xdv_core) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(4, {
                "phase": "DATA_VERIFICATION",
                "production_bets": {
                    "acca_a_legs": production.acca_a.n_legs if production.acca_a else 0,
                    "split_accas": len(production.split_accas),
                    "singles": len(production.singles),
                },
            }, run_id=run_id, metadata={"production": True})
            write_agent_handoff(4, 5, {
                "production": {
                    "acca_a": production.acca_a is not None,
                    "split_accas": len(production.split_accas),
                    "singles": len(production.singles),
                },
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 4 handoff failed ({e})")

    # --- produced-bet record (ID415): every rated fixture with a kickoff on
    # --- the board date is one produced-bet leg, saved to produced_<date>.json
    # --- + the brain mirror, so the framework always has a findable copy of
    # --- what it produced for that day. No fixtures on the date -> an honest
    # --- empty record, still written. The board is final here (prices
    # --- attached, cap applied). ---
    try:
        produced_bet.record_produced_bet(board, board_date, brain)
    except Exception as e:
        # a produced-bet record fault must never kill the daily board — the
        # rest of the run continues; the missing record is visible via the flag.
        all_flags.append(f"produced-bet record failed ({e})")

    # --- booking tracker: wire the produced accas into tracker.place() so
    # --- produced_<date>.json is written with full per-leg detail (status,
    # --- ft_result, hit) ready for next-day settlement. This is the thin
    # --- tracking layer that mirrors what produced_bet writes, but adds the
    # --- acca-level structure the tracker's settle()/status() consume.
    # --- HR35: no fabrication — the tracker writes what the board produced,
    # --- never invents legs or results.
    try:
        from bets.booking_tracker import place as _tracker_place
        if acca_list:
            _place_payload = [dataclasses.asdict(a) for a in acca_list]
            _place_result = _tracker_place(_place_payload, target_date=board_date)
            n_placed = _place_result.get("placed", 0)
            n_skipped = _place_result.get("skipped", 0)
            if n_placed or n_skipped:
                all_flags.append(
                    f"booking tracker: {n_placed} acca(s) placed, "
                    f"{n_skipped} skipped")
    except Exception as e:
        # tracker.place is additive — a fault must never kill the board
        all_flags.append(f"booking tracker place skipped ({type(e).__name__}: {str(e)[:80]})")

    # --- log the paper legs (the point of Phase 2) ---
    _, lflags = log_paper_legs(log, board, odds_index, min_mes=min_mes,
                               agreement_band=agreement_band)
    all_flags += lflags

    # ===== PIPELINE BUS: Stage 5 (xdv_core) output -> Stage 6 (odds_audit) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(5, {
                "phase": "XDV_CORE",
                "paper_legs_logged": True,
                "min_mes": min_mes,
                "flags": lflags,
            }, run_id=run_id, metadata={"legs_logged": len(lflags)})
            write_agent_handoff(5, 6, {
                "paper_legs_logged": True,
                "board_size": len(board),
                "odds_leagues": sorted(odds_leagues),
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 5 handoff failed ({e})")

    # --- CL-LIVE closing lines: any pending leg whose kickoff is inside the
    # --- closing window right now gets its closing line from the live feed,
    # --- reusing the prices this run already pulled (zero extra quota). This
    # --- lets a leg earn CLV the moment its match kicks off, before the
    # --- football-data archive publishes — and covers markets the archive
    # --- never serves (e.g. Danish Superliga totals). Honest rule enforced in
    # --- clv/closing_capture.py: never captured far from kickoff, never
    # --- estimated (HR35).
    try:
        n_close, cflags = capture_closing_lines(log, sorted(odds_leagues),
                                                odds_index=odds_index)
        all_flags += cflags
    except Exception as e:
        # CL-LIVE is new and unproven in production; a bug or transient fault
        # there must never kill the whole daily board. Legs stay PENDING rather
        # than being guessed (HR35) — the flag keeps the failure visible.
        all_flags.append(f"CL-LIVE closing-line capture failed ({e}) — "
                         f"legs stay PENDING, not guessed")

    status = log.phase2_status()

    # ===== PIPELINE BUS: Stage 6 (odds_audit) output -> Stage 7 (compliance) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(6, {
                "phase": "ODDS_AUDIT",
                "closing_lines_captured": n_close,
                "clv_flags": cflags,
                "phase2_status": {
                    "legs_with_clv": status["legs_with_clv"],
                    "gate_requirement": status["gate_requirement"],
                    "mean_clv_pct": status["mean_clv_pct"],
                },
            }, run_id=run_id, metadata={"n_close": n_close})
            write_agent_handoff(6, 7, {
                "closing_lines": n_close,
                "clv_status": status,
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 6 handoff failed ({e})")
    all_flags.append(
        f"Phase 3 gate: {status['legs_with_clv']} of {status['gate_requirement']} "
        f"legs with logged CLV; mean CLV "
        f"{status['mean_clv_pct'] if status['mean_clv_pct'] is not None else 'NO DATA — PENDING'}")

    # ID414: ScoreGPT parity data — yesterday's graded fixtures + 7-day rolling
    # stats, computed once and shared by the Telegram push and the web payload.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    yesterday_graded = brain.graded_yesterday(yesterday)
    rolling_7d = brain.rolling_7d()

    # ID415: the board date's produced-bet record, read back for the
    # board/Telegram block.
    produced_record = produced_bet.load_produced_bet(board_date)

    # The acca payload — what the booking-code generator and the web dashboard
    # read. Always written (even an empty acca set), so downstream consumers
    # never guess at a missing file. Carries Acca A, the split accas AND the
    # singles as 1-leg slips (production intent #6 — every single its own code).
    # --- KICKOFF-TIME FILTER (2026-08-26): drop legs whose kickoff date
    # --- is not today. Prevents the SportyBet booking-code generator from
    # --- wasting a browser session on expired fixtures (e.g. Lyon v Fenerbahce
    # --- which was a midweek UCL tie not in today's cache). Only live legs
    # --- are navigated to, speeding up booking and eliminating MANUAL noise.
    _expired_legs = []
    _filtered_payload_accas = []
    for a in acca_list:
        _live_legs = []
        for l in a.legs:
            _bf = _board_fixture_for_leg(board, l)
            if _bf is not None and _bf.kickoff_date != board_date:
                _expired_legs.append(
                    f"{l.fixture} ({l.league}) — kickoff {_bf.kickoff_date}")
                continue
            _live_legs.append(l)
        if _live_legs:
            _filtered_a = type(a)(
                label=a.label, legs=_live_legs,
                combined_odds=a.combined_odds,
                combined_prob=a.combined_prob)
            _filtered_payload_accas.append(_filtered_a)
    if _expired_legs:
        all_flags.append(
            f"kickoff filter: dropped {len(_expired_legs)} expired leg(s) "
            f"from booking payload")
        _mark(runlog,
              f"kickoff filter: {len(_expired_legs)} expired leg(s) "
              f"skipped for SportyBet booking")

    acca_payload = {
        "date": board_date,
        "n_accas": len(_filtered_payload_accas),
        "accas": [{
            "label": a.label,
            "combined_odds": a.combined_odds,
            "combined_prob": a.combined_prob,
            "n_legs": a.n_legs,
            "legs": [dataclasses.asdict(l) for l in a.legs],
        } for a in _filtered_payload_accas],
    }

    # --- SPORTYBET BOOKING CODES (Phase 2 — codes only, NO stake placed).
    # --- Drives the board date's acca payload into SportyBet's betslip and
    # --- reads the BOOKING CODES SportyBet returns, so the Architect can paste
    # --- a code into SportyBet to recall the exact slip. Runs BEFORE any render
    # --- so the codes reach the Telegram push and the web board. Best-effort
    # --- like the cache refresh: a browser fault degrades each slip to MANUAL,
    # --- never a run failure (HR35). Gated by --no-booking-codes /
    # --- OLP_BOOKING_CODES=0; when skipped, any EXISTING capture for this date
    # --- is preserved (the file is date-scoped, so it can never surface as
    # --- another day's) — see the codes-fix note below.
    codes_result = None
    if booking_codes and _filtered_payload_accas:
        try:
            _mark(runlog, "generating SportyBet booking codes...")
            from booking.booking_codes import book_accas, render_codes
            codes_result = book_accas(acca_payload, headless=True)
            codes_text = render_codes(codes_result)
            codes_path = BOARD_DIR / f"acca_{board_date}_codes.json"
            codes_path.write_text(
                json.dumps(codes_result, ensure_ascii=False, indent=2),
                encoding="utf-8")
            n_booked = sum(1 for r in codes_result.get("results", [])
                           if r.get("code"))
            n_slips = len(codes_result.get("results", []))
            all_flags.append(
                f"SportyBet booking codes: {n_booked}/{n_slips} slip(s) "
                f"booked — {codes_path.name}")
            _mark(runlog, codes_text.replace("\n", " | ")[:200])
        except Exception as e:
            codes_result = None
            all_flags.append(
                f"sportybet booking codes skipped "
                f"({type(e).__name__}: {str(e)[:80]}) — add legs manually")
    elif not booking_codes:
        # CODES-FIX (2026-08-12): the old code UNLINKED acca_<date>_codes.json
        # whenever a run skipped booking, which destroyed a good capture on a
        # later MANUAL regen (M5LMFE, 2026-08-11). The file is date-scoped —
        # acca_{board_date}_codes.json can never surface as another day's codes
        # — so the unlink was harmful and unnecessary. A capture is preserved,
        # and the skip is logged loudly (never silent).
        stale = BOARD_DIR / f"acca_{board_date}_codes.json"
        if stale.exists():
            all_flags.append("booking codes skipped — existing capture "
                             f"{stale.name} preserved (codes-fix)")
        # MANDATORY BOOKING (Architect directive 2026-08-16): a PRODUCTION run
        # (it delivers to Telegram/web) must not finish a day with production
        # slips that have no booking code. If booking_codes was disabled in a
        # production context, that is a configuration error, not a quiet skip —
        # refuse the run rather than ship "NO DATA — PENDING" picks to the phone.
        if acca_list and (send or web):
            raise RuntimeError(
                "REFUSING PRODUCTION RUN: booking_codes disabled but this run "
                "delivers to Telegram/web. Every Acca A leg, split acca leg and "
                "single must carry a SportyBet booking code at pipeline end "
                "(Architect 2026-08-16). Re-run with booking enabled "
                "(OLP_BOOKING_CODES=1, drop --no-booking-codes).")

    # --- POST-BOOKING ALL-LEGS CHECK (Architect directive 2026-08-16). After
    # --- codes are generated, every leg of every acca AND every single must have
    # --- a booked code. The old code tolerated silent per-leg MANUAL failures,
    # --- which left "NO DATA — PENDING" in the production output. Now a missing
    # --- code is a loud run failure, never a silent gap. Honest-edge preserved:
    # --- a MANUAL reason (browser couldn't drive the selection) is reported, but
    # --- it still counts as a missing code and is flagged, not hidden.
    if codes_result and acca_list:
        _missing: list[str] = []
        _odds_bad: list[str] = []
        for r in codes_result.get("results", []):
            for leg in r.get("per_leg", []):
                if leg.get("status") != "BOOKED":
                    _missing.append(
                        f"{r.get('label','?')}: {leg.get('fixture','?')} "
                        f"({leg.get('market_name','?')}) — "
                        f"{leg.get('reason', leg.get('status', 'no code'))}")
            # HARD RULE (Architect 2026-08-20): code odds must equal expected
            # combined odds. A mismatch means the slip is wrong — flag it so the
            # Architect never places a slip with bad numbers.
            oc = r.get("odds_check")
            if oc and not oc.get("match"):
                exp = oc.get("expected")
                bs = oc.get("betslip")
                _odds_bad.append(
                    f"{r.get('label','?')}: expected {exp:.2f} vs betslip {bs:.2f}")
        if _missing:
            all_flags.append(
                f"⚠ BOOKING COVERAGE GAP — {len(_missing)} leg(s) WITHOUT a "
                f"booked code: " + "; ".join(_missing[:12])
                + (" …" if len(_missing) > 12 else "")
                + " (Architect must add manually before placing)")
        if _odds_bad:
            all_flags.append(
                f"⚠ BOOKING ODDS MISMATCH — {len(_odds_bad)} slip(s) with WRONG "
                f"odds (code rejected): " + "; ".join(_odds_bad[:12])
                + (" …" if len(_odds_bad) > 12 else "")
                + " (Architect must verify the slip by hand before placing)")

    # The production block (Acca A -> split accas -> singles) with codes inline;
    # the same block feeds the saved acca txt, the Telegram push and the wide
    # board.
    acca_text = render_production_block(production, codes=codes_result,
                                        today=board_date, board=board)

    # Telegram board uses the BLENDED 4-TABLE format (Architect 2026-08-28):
    # CLEAN TELEGRAM OUTPUT — compact heartbeat format (Architect 2026-08-28 directive)
    # Shows ONLY fixtures with model probabilities, league-grouped with kickoff time,
    # alt markets, and AI pick. No "NO DATA — PENDING" entries.
    telegram_text = render_telegram_board(
        mode="Mode A", phase=PHASE_LABEL,
        leagues_scanned=leagues, calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board,
        yesterday_graded=yesterday_graded, rolling_7d=rolling_7d,
        produced_bet=produced_record, production=production,
        codes=codes_result,
        compact=True, target_date=board_date)

    # The FEED text — one render, two outlets (Architect 2026-08-11). This
    # exact string is BOTH what the phone receives (notify.deliver below) AND
    # what telegram_<date>.txt persists for the web feed, so the web == Telegram
    # structurally and the two can never disagree about today's picks or codes.
    # The persisted file is intentionally the UNSTAMPED body (notify wraps the
    # banner internally); document, don't "fix".
    board_url = os.environ.get("BOARD_URL", "").strip()
    feed_text = (f"{telegram_text}\n\nFull board: {board_url}"
                 if board_url else telegram_text)

    board_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board,
        produced_bet=produced_record, production=production,
        codes=codes_result,
        include_data_flags=True, only_rated=False, compact=False)

    full = board_text + "\n\n" + "=" * 60 + "\n\n" + verify_block
    path = BOARD_DIR / f"board_{board_date}.txt"

    try:
        (BOARD_DIR / f"acca_{board_date}.json").write_text(
            json.dumps(acca_payload, ensure_ascii=False, indent=2),
            encoding="utf-8")
        (BOARD_DIR / f"acca_{board_date}.txt").write_text(
            acca_text, encoding="utf-8")
    except Exception as e:
        # the acca files are additive — a fault never kills the board
        all_flags.append(f"acca file write failed ({e})")

    # The web dashboard (webapp/) reads board_<today>.json — the local server
    # and the hosted static export both consume it, so today's board is
    # available without re-running the pipeline. Additive and cheap; written
    # whether or not delivery happens. Toggled by --no-web / web=False.
    if web:
        try:
            from webapp import schema as web_schema
            from clv.phase3_gate import gate_status_for_dashboard
            web_payload = web_schema.build_payload(
                date=board_date, phase=PHASE_LABEL, leagues_scanned=leagues,
                board=board, data_flags=all_flags,
                gate=gate_status_for_dashboard(),
                telemetry=brain.leg_telemetry(),
                calibration_count=status["legs_with_clv"],
                mean_clv=status["mean_clv_pct"],
                # the ⭐ TODAY'S PICKS parlay is retired (2026-08-10) — Acca A
                # is the headline product; the slot stays for schema compat.
                recommendation="",
                produced_bet=produced_record,
                yesterday_graded=yesterday_graded,
                rolling_7d=rolling_7d,
                accas=acca_payload["accas"])
            web_schema.write_payload(
                web_payload, BOARD_DIR / f"board_{board_date}.json")
            # The Telegram-feed copy — byte-faithful to feed_text, so the web
            # page == the phone push for today's picks and codes. Additive; a
            # fault is logged, never a run failure. The audit stamp records the
            # gate numbers on the feed side so an override is never silent.
            try:
                (BOARD_DIR / f"telegram_{board_date}.txt").write_text(
                    feed_text, encoding="utf-8")
                web_schema.stamp_feed_audit(board_date, web_payload)
            except Exception as e:
                _mark(runlog, f"telegram feed file write failed ({e})")
            if prefetch_crests:
                # Best-effort club-badge prefetch so the dashboard carries real
                # TheSportsDB crests, not just initials. Never raises; a failed
                # lookup is a miss, not a fault (HR35).
                try:
                    from webapp import crests as _crests
                    n = len(_crests.prefetch(
                        _crests.teams_from_board(
                            BOARD_DIR / f"board_{board_date}.json")))
                    _mark(runlog, f"crest prefetch added {n} badge(s)")
                except Exception as e:
                    _mark(runlog, f"crest prefetch skipped ({e})")
        except Exception as e:
            _mark(runlog, f"web payload write failed ({e}) — txt board unaffected")

    # ===== PIPELINE COORDINATION (2026-08-18 refactor) =====
    # run_daily builds the board (scan/verify/odds/engine/production) itself; the
    # unified pipeline is the SINGLE renderer for the canonical artifacts:
    #   telegram_<date>.txt, feed_audit.jsonl, acca_<date>_codes.json,
    #   board_<date>.txt, acca_<date>.json/.txt
    # The CEO sign-off (Agent 10) runs against the live CLV gate so the feed
    # audit records the same decision the dashboard shows. Wired mode: board/
    # production/codes are passed in directly (no re-scan), the pipeline only
    # adds the sign-off + artifact rendering.
    try:
        from olp_xdv_pipeline import run_pipeline as _pipe_run, \
            render_board_from_pipeline as _pipe_render
        _pipe_state = _pipe_run(season=season, fixtures_season=fixtures_season,
                                dry_run=False, only=10)
        _pipe_out = _pipe_render(
            state=_pipe_state,
            board=board, production=production, codes_result=codes_result,
            leagues_scanned=leagues,
            calibration_count=status["legs_with_clv"],
            mean_clv=status["mean_clv_pct"], all_data_flags=all_flags,
            yesterday_graded=yesterday_graded, rolling_7d=rolling_7d,
            produced_record=produced_record, date_str=board_date)
        _mark(runlog, f"pipeline render: {_pipe_out['telegram_file']} written "
                      f"({_pipe_out['feed_audit']['ceo_decision']})")
    except Exception as e:
        _mark(runlog, f"pipeline render failed ({e}) — falling back to local "
                      f"telegram/board writes below")

    # ===== PIPELINE BUS: Stage 7 (compliance) output -> Stage 8 (execution) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(7, {
                "phase": "COMPLIANCE",
                "board_date": board_date,
                "feed_written": (BOARD_DIR / f"telegram_{board_date}.txt").exists(),
                "gate_status": {
                    "legs_with_clv": status["legs_with_clv"],
                    "gate_requirement": status["gate_requirement"],
                    "mean_clv_pct": status["mean_clv_pct"],
                    "gate_met": status["gate_met"] if "gate_met" in status else None,
                },
                "codes_generated": codes_result is not None,
            }, run_id=run_id, metadata={"board_date": board_date})
            write_agent_handoff(7, 8, {
                "board_date": board_date,
                "feed_file": f"telegram_{board_date}.txt",
                "codes_result": bool(codes_result),
                "production": {
                    "acca_a": production.acca_a is not None,
                    "split_accas": len(production.split_accas),
                    "singles": len(production.singles),
                },
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 7 handoff failed ({e})")

    if send:
        # Suppress phone push for empty/paper-only boards (no deployable call).
        # The board is still written to disk for the web feed, but we don't
        # wake the phone for "NO DEPLOY-ELIGIBLE CALL this session" results.
        has_deployable = (
            (production.acca_a is not None)
            or production.split_accas
            or production.singles
        )
        if not has_deployable:
            _mark(runlog, "Telegram push suppressed — no deployable call (empty/paper-only board)")
        else:
            # The delivered body IS feed_text — the same string persisted to
            # telegram_<date>.txt above, so the phone and the web feed are one
            # render, two outlets (Architect 2026-08-11). BOARD_URL (set once the
            # dashboard is hosted) rides inside feed_text.
            delivered, notes = notify.deliver(feed_text, save_to=None)
            for n in notes:
                print(f"  {n}")
                _mark(runlog, n)
            if not delivered:
                # A run that failed to reach the phone is NOT a completed run.
                # Reporting OK here is what let three failed message parts pass as
                # success — the launcher then exits 0 and no alert fires.
                _mark(runlog, "RUN FAILED — board built but delivery incomplete")
                raise RuntimeError("Telegram delivery incomplete — see log")
        # Always persist the full artifact for web feed / audit
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        # WhatsApp is the COPY channel, not the source of truth: a failure here
        # is logged loudly but never fails the run — Telegram already reached
        # the phone. RETIRED BY DEFAULT (ID412): the web dashboard replaced it
        # (recurring token-expiry + template-approval pain). Re-enable with
        # WHATSAPP_ENABLED=1. Also silently skipped when no credentials are set.
        if (whatsapp and os.environ.get("WHATSAPP_ENABLED", "0").lower()
                not in ("0", "false", "no")):
            wa_delivered, wa_notes = whatsapp_deliver.deliver(telegram_text)
            for n in wa_notes:
                print(f"  {n}")
                _mark(runlog, n)
        # Email is likewise a best-effort COPY channel (zero-approval, SMTP).
        # Toggled off by --no-email or EMAIL_ENABLED=0; skipped silently when
        # no credentials are set.
        if (email and os.environ.get("EMAIL_ENABLED", "1").lower()
                not in ("0", "false", "no")):
            em_delivered, em_notes = email_deliver.deliver(telegram_text)
            for n in em_notes:
                print(f"  {n}")
                _mark(runlog, n)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(full, encoding="utf-8")
        print(f"  board saved to {path} (delivery skipped)")

    # ===== PIPELINE BUS: Stage 8 (execution) output -> Stage 9 (team_lead) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(8, {
                "phase": "EXECUTION",
                "delivered": send,
                "board_path": str(path),
                "board_date": board_date,
            }, run_id=run_id, metadata={"delivered": send})
            write_agent_handoff(8, 9, {
                "delivered": send,
                "board_date": board_date,
                "board_path": str(path),
                "flags": all_flags.copy(),
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 8 handoff failed ({e})")

    _mark(runlog, "run completed OK")
    # Remove leagues_with_fixtures - not a column in runs table
    fit_stats_for_update = {k: v for k, v in fit_stats.items() if k != "leagues_with_fixtures"}
    brain.update_run(
        run_id, status="ok",
        finished_at=datetime.now(timezone.utc).isoformat(),
        fixtures_seen=len(board),
        predictions_logged=n_preds,
        legs_logged=status["legs_logged_total"],
        fit_seconds=round(time.time() - t0, 1),
        warnings=json.dumps(all_flags),
        **fit_stats_for_update)

    # ===== PIPELINE BUS: Stage 9 (team_lead) output -> Stage 10 (ceo) =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(9, {
                "phase": "TEAM_LEAD_REVIEW",
                "run_id": run_id,
                "board_date": board_date,
                "summary": {
                    "fixtures_scanned": len(board),
                    "production_bets": {
                        "acca_a": production.acca_a is not None,
                        "split_accas": len(production.split_accas),
                        "singles": len(production.singles),
                    },
                    "clv_gate": {
                        "legs_with_clv": status["legs_with_clv"],
                        "gate_requirement": status["gate_requirement"],
                        "mean_clv_pct": status["mean_clv_pct"],
                    },
                    "delivered": send,
                },
            }, run_id=run_id, metadata={"stage": "team_lead"})
            write_agent_handoff(9, 10, {
                "brief_id": f"BRIEF-{board_date.replace('-', '')}-001",
                "board_date": board_date,
                "run_id": run_id,
                "publish_gate": {
                    "architect_signoff": os.environ.get("ARCHITECT_SIGNOFF", "0").strip().lower() in ("1", "true", "yes"),
                    "clv_legs": status["legs_with_clv"],
                    "clv_mean": status["mean_clv_pct"],
                },
            }, run_id=run_id)
        except Exception as e:
            all_flags.append(f"pipeline bus stage 9 handoff failed ({e})")

    # ===== PIPELINE BUS: Stage 10 (ceo) final sign-off =====
    if PIPELINE_BUS_AVAILABLE:
        try:
            write_stage_output(10, {
                "phase": "CEO_SIGNOFF",
                "run_id": run_id,
                "board_date": board_date,
                "decision": "CEO_APPROVE" if send else "PENDING_MANUAL_REVIEW",
                "summary": "Pipeline run completed. Board generated and persisted.",
            }, run_id=run_id, metadata={"stage": "ceo"})
        except Exception as e:
            all_flags.append(f"pipeline bus stage 10 handoff failed ({e})")

    return RunResult(full=full, telegram_text=telegram_text,
                     board=board, leagues_scanned=leagues)


def _predictions_from_board(board, run_id: str, predicted_at: str,
                            brain: Brain) -> int:
    """Persist every rated board prediction to the brain's `predictions` table
    so nothing the board said is forgotten. ~9 rows per rated fixture: the 1X2
    and O1.5/O2.5/BTTS model probabilities from the goals engine, plus the Elo
    second opinion's 1X2. The one priced best-market row also carries its
    odds/bookmaker/EV. Returns the number of rows written."""
    rows: list[dict] = []
    for bf in board:
        if bf.probs is None:
            continue
        league = bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture \
            else "—"
        fixture = bf.fixture.split(" (")[0]
        engine = getattr(bf, "model_engine", "dc")
        p = bf.probs
        base = dict(run_id=run_id, predicted_at=predicted_at, league=league,
                    fixture=fixture, match_date=bf.kickoff_date,
                    on_deploy_shortlist=int(bf.on_deploy_shortlist),
                    entry_odds=None, bookmaker=None, ev=None,
                    cal_adjustment=None)
        for key, prob in (("1X2_HOME", p.p_home), ("1X2_DRAW", p.p_draw),
                          ("1X2_AWAY", p.p_away), ("OVER_1_5", p.p_over_15),
                          ("OVER_2_5", p.p_over_25), ("BTTS_YES", p.p_btts_yes)):
            # HR35: a stretch-rated fixture (ClubElo fallback, Architect
            # 2026-08-12) has no goals-market opinion — p_over_*/p_btts are
            # None. Never persist a fabricated prediction; skip the row.
            if prob is None:
                continue
            r = dict(base, market=key, model_engine=engine, model_prob=prob)
            if getattr(bf, "best_market_key", None) == key:
                r.update(entry_odds=bf.best_price, bookmaker=bf.best_bookmaker,
                         ev=bf.best_mes_ev,
                         cal_adjustment=bf.cal_adjustment)
            rows.append(r)
        if bf.elo_probs:
            eh, ed, ea = bf.elo_probs
            for key, prob in (("1X2_HOME", eh), ("1X2_DRAW", ed),
                              ("1X2_AWAY", ea)):
                rows.append(dict(base, market=key, model_engine="elo",
                                 model_prob=prob))
        if bf.xg_probs:
            xh, xd, xa = bf.xg_probs
            for key, prob in (("1X2_HOME", xh), ("1X2_DRAW", xd),
                              ("1X2_AWAY", xa)):
                rows.append(dict(base, market=key, model_engine="xg",
                                 model_prob=prob))
            if getattr(bf, "xg_goals", None):
                # Phase 3.4: xG's goals-market read persisted like its 1X2 —
                # the brain grades chance quality on the goals markets it
                # calls, so engine_clv attributes goals-market CLV to xG (and
                # never to DC, which did not author these).
                xo15, xo25, _, xb = bf.xg_goals
                for key, prob in (("OVER_1_5", xo15), ("OVER_2_5", xo25),
                                  ("BTTS_YES", xb)):
                    rows.append(dict(base, market=key, model_engine="xg",
                                     model_prob=prob))
        if getattr(bf, "market_probs", None):
            # ID413: the bookmaker's devigged implied 1X2 — real money, the
            # sharpest calibration source. Persisted so the brain grades the
            # market's opinion against reality like any other engine.
            mh, md, ma = bf.market_probs
            for key, prob in (("1X2_HOME", mh), ("1X2_DRAW", md),
                              ("1X2_AWAY", ma)):
                rows.append(dict(base, market=key, model_engine="bookmaker",
                                 model_prob=prob))
        if getattr(bf, "consensus", None) and bf.consensus.result \
                and bf.consensus.avg_home is not None:
            # ID412: the cross-engine consensus, persisted so the brain can
            # grade it against reality like any other model opinion. Only the
            # averaged 1X2 when a majority exists — a split with no majority
            # is NOT a prediction and is never persisted (HR35).
            for key, prob in (("1X2_HOME", bf.consensus.avg_home),
                              ("1X2_DRAW", bf.consensus.avg_draw),
                              ("1X2_AWAY", bf.consensus.avg_away)):
                rows.append(dict(base, market=key, model_engine="consensus",
                                 model_prob=prob))
    return brain.append_predictions(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OLP XDV daily 07:00 run")
    ap.add_argument("--season", default="2526", help="season the model is FIT on")
    ap.add_argument("--fixtures-season", default=None)
    ap.add_argument("--leagues", nargs="+", default=None)
    ap.add_argument("--min-mes", type=float, default=0.0,
                     help="minimum EV to log a paper leg (0 = log every priced market)")
    ap.add_argument("--no-send", action="store_true", help="write the board, don't deliver")
    ap.add_argument("--no-whatsapp", action="store_true",
                    help="skip the WhatsApp copy even when configured")
    ap.add_argument("--no-email", action="store_true",
                    help="skip the email copy even when configured")
    ap.add_argument("--no-web", action="store_true",
                    help="skip writing the board_<date>.json the web dashboard reads")
    ap.add_argument("--days-ahead", type=int, default=0,
                    help="fixture window in days from today (0 = today's matches only — "
                         "strict single-day production, Architect 2026-08-10)")
    ap.add_argument("--date", dest="target_date", default=None,
                    help="produce the board for this exact YYYY-MM-DD only "
                         "(default: today; same strict single-day rule)")
    ap.add_argument("--no-prefetch-crests", action="store_true",
                    help="skip the club-badge prefetch even when the web board is written")
    ap.add_argument("--no-sportybet", action="store_true",
                    help="skip the SportyBet fixture-cache refresh before the scan")
    ap.add_argument("--no-booking-codes", action="store_true",
                    help="skip generating SportyBet booking codes for today's accas")
    ap.add_argument("--verify-only", action="store_true",
                    help="run ONLY the fixture verification gate (SportyBet + "
                         "FlashScore cross-check) and print the report — no odds "
                         "pull, engine scoring, production, or booking")
    ap.add_argument("--agreement-band", type=float, default=0.04,
                    help="experiment (gambler move #2): only bet markets where "
                         "model and book agree within this probability band "
                         "(default 0.04 = the calibrated zone, BLEND_NOOP_AT). "
                         "Explicitly an experiment flag — no protected constant.")
    a = ap.parse_args()
    print(f"OLP XDV daily run — {date.today().isoformat()} — {PHASE_LABEL}")
    # The CLI pre-warms club badges by default (real runs have the network);
    # env OLP_PREFETCH_CRESTS=0 or --no-prefetch-crests turns it off.
    prefetch = (not a.no_prefetch_crests
                and os.environ.get("OLP_PREFETCH_CRESTS", "1") != "0")
    # The CLI also warms the SportyBet fixture cache (best-effort, incremental);
    # env OLP_SPORTYBET=0 or --no-sportybet turns it off.
    refresh_sportybet = (not a.no_sportybet
                         and os.environ.get("OLP_SPORTYBET", "1") != "0")
    # And it generates SportyBet booking codes for today's accas (Phase 2 —
    # codes only, never a stake); env OLP_BOOKING_CODES=0 or --no-booking-codes
    # turns it off.
    booking_codes = (not a.no_booking_codes
                     and os.environ.get("OLP_BOOKING_CODES", "1") != "0")
    out = run(season=a.season, fixtures_season=a.fixtures_season,
              leagues=a.leagues, send=not a.no_send, min_mes=a.min_mes,
              days_ahead=a.days_ahead, target_date=a.target_date,
              whatsapp=not a.no_whatsapp, email=not a.no_email,
              web=not a.no_web, prefetch_crests=prefetch,
              refresh_sportybet=refresh_sportybet,
              booking_codes=booking_codes,
              agreement_band=a.agreement_band,
              verify_only=a.verify_only)
    # Windows console (cp1252) can't encode ��� and other Unicode chars
    try:
        print("\n" + out.full)
    except UnicodeEncodeError:
        print("\n" + out.full.encode('cp1252', 'replace').decode('cp1252'))
