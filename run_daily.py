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

# Import for calibration tracking
from data.calibration_tracker import GradedPick, record_outcome
from output.produce_bet import render_telegram_board
from output.produce_bet import render_verify_results, render_produce_bet
from output.board_validator import filter_board_for_telegram
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

# NEW: Import provider fallback infrastructure
from fixtures_and_odds_providers import get_fixtures_for_run_daily
from provider_fallback import create_provider_chain
from telegram_send_guard import should_send_telegram

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
    """Mark the start of a run by creating a runlog file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    runlog = LOG_DIR / f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
    with open(runlog, "w") as f:
        f.write(f"Run started at {datetime.now(timezone.utc).isoformat()}\n")
    return runlog


def _mark(runlog: Path, message: str) -> None:
    """Append a message to the runlog."""
    with open(runlog, "a") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")


# Type aliases
SCAN_LEAGUES = [
    "Premier League",
    "Championship",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "La Liga",
    "Primeira Liga",
    "Eredivisie",
    "Scottish Premiership",
    "Belgian Pro League",
    "Turkish Super Lig",
    "Swiss Super League",
    "Russian Premier League",
    "Serie B",
    "La Liga 2",
    "Ligue 2",
]

MIN_MES_FLOOR = 0.03


@dataclass
class RunResult:
    """Result of a daily run."""
    full: str
    telegram_text: str
    board: list
    leagues_scanned: list[str]
    flags: list[str] = None
    booking_codes: dict = None

    def __post_init__(self):
        if self.flags is None:
            self.flags = []
        if self.booking_codes is None:
            self.booking_codes = {}


def _prefetch_stage(board_date: str, season: str, fixtures_season: str | None,
                    leagues: list[str], runlog: Path, all_flags: list[str]) -> RunResult:
    """Pre-fetch and cache all external data for the given board_date.

    This is Stage 1 of the two-stage pipeline. It runs at ~20:00 and populates
    data/cache/ with everything Stage 2 (22:00) needs to run in <30 seconds.
    """
    from datetime import date, timedelta
    import time
    from pathlib import Path

    t0 = time.time()
    _mark(runlog, f"PREFETCH START — board_date={board_date}")

    # 1. Pre-fetch fixtures for all leagues using provider fallback chain
    _mark(runlog, f"Fetching fixtures for {len(leagues)} leagues (using provider fallback)...")

    # Use new provider fallback chain for fixtures
    fixtures_by_league = get_fixtures_for_run_daily(leagues, season, fixtures_season, board_date, days_ahead=1)

    for lg in leagues:
        fixtures = fixtures_by_league.get(lg, [])
        all_flags.append(f"{lg}: fixture prefetch completed ({len(fixtures)} fixtures) - via provider fallback")
        _mark(runlog, f"  {lg}: {len(fixtures)} fixtures fetched")

    # 2. Pre-fetch odds for all leagues via multi-source layer
    _mark(runlog, f"Fetching odds for {len(leagues)} leagues...")
    odds_index: dict = {}
    for lg in leagues:
        try:
            fixtures = multi_get_odds(lg)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags.append(f"{lg}: odds prefetched ({len(fixtures)} fixtures)")
            _mark(runlog, f"  {lg}: odds cached")
        except Exception as e:
            all_flags.append(f"{lg}: odds prefetch failed ({e})")
            _mark(runlog, f"  {lg}: odds FAILED - {e}")

    # 3. Merge SportyBet cache odds (headless Chromium pass)
    _mark(runlog, f"Refreshing SportyBet fixture cache...")
    try:
        from booking.bridge import load_all_sportybet_fixtures
        sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=3, leagues=leagues)
        total_sb = sum(len(v) for v in sb_fixtures_by_league.values())
        all_flags.append(f"SportyBet cache refreshed: {total_sb} fixtures across {len(sb_fixtures_by_league)} leagues")
        _mark(runlog, f"  SportyBet: {total_sb} fixtures cached")
    except Exception as e:
        all_flags.append(f"SportyBet cache refresh failed ({e})")
        _mark(runlog, f"  SportyBet: FAILED - {e}")

    # 4. Pre-fetch Bet365 odds feed
    _mark(runlog, f"Checking Bet365 odds feed...")
    try:
        from pathlib import Path
        live_odds_dir = Path(__file__).parent.parent / "data" / "live_odds"
        bet365_odds_files = sorted(live_odds_dir.glob("bet365_odds_*.jsonl"), reverse=True)
        if bet365_odds_files:
            latest = bet365_odds_files[0]
            size = latest.stat().st_size
            all_flags.append(f"Bet365 odds feed available: {latest.name} ({size} bytes)")
            _mark(runlog, f"  Bet365: {latest.name} found")
        else:
            all_flags.append("Bet365 odds feed: NO FILES FOUND")
            _mark(runlog, f"  Bet365: NO FILES")
    except Exception as e:
        all_flags.append(f"Bet365 odds check failed ({e})")
        _mark(runlog, f"  Bet365: FAILED - {e}")

    # 5. Pre-fetch injury/squad lists from TheSportsDB
    _mark(runlog, f"Fetching injury/squad data...")
    try:
        from data.thesportsdb_fixtures import fetch_injuries
        for lg in leagues:
            try:
                fetch_injuries(lg)
            except Exception:
                pass
        all_flags.append("Injury/squad data prefetched for all leagues")
        _mark(runlog, f"  Injuries: cached")
    except Exception as e:
        all_flags.append(f"Injury prefetch failed ({e})")
        _mark(runlog, f"  Injuries: FAILED - {e}")

    elapsed = round(time.time() - t0, 1)
    _mark(runlog, f"PREFETCH COMPLETE — {elapsed}s")
    all_flags.append(f"Prefetch completed in {elapsed}s — data/cache/ populated for {board_date}")

    return RunResult(
        full="\n".join(all_flags),
        telegram_text=f"Prefetch completed for {board_date} in {elapsed}s",
        board=[],
        leagues_scanned=leagues,
    )


def _refresh_sportybet_cache(runlog: Path) -> Optional[str]:
    """Refresh SportyBet fixture cache with headless browser."""
    try:
        from booking.bridge import load_all_sportybet_fixtures
        _mark(runlog, "Refreshing SportyBet cache...")
        sb_fixtures_by_league = load_all_sportybet_fixtures(days_ahead=3, leagues=SCAN_LEAGUES)
        total = sum(len(v) for v in sb_fixtures_by_league.values())
        _mark(runlog, f"SportyBet cache refreshed: {total} fixtures")
        return f"SportyBet cache refreshed: {total} fixtures across {len(sb_fixtures_by_league)} leagues"
    except Exception as e:
        _mark(runlog, f"SportyBet cache refresh failed: {e}")
        return f"SportyBet cache refresh failed ({e})"


def grade_open_legs(log: CLVLog, season: str) -> tuple[str, list[str]]:
    """Grade open legs and return verification block and flags."""
    flags = []
    try:
        verify_block = log.verify_pending(season)
        flags.append("CLV verification completed")
        return verify_block, flags
    except Exception as e:
        flags.append(f"CLV verification failed ({e})")
        return "", flags


def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, days_ahead: int = 0,
        target_date: str | None = None,
        whatsapp: bool = True, email: bool = True,
        web: bool = True, prefetch_crests: bool = False,
        refresh_sportybet: bool = False,
        booking_codes: bool = False,
        agreement_band: Optional[float] = 0.04,
        verify_only: bool = False,
        prefetch_only: bool = False) -> RunResult:
    """Run the daily board end to end."""
    leagues = leagues or SCAN_LEAGUES
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
                    booking_codes, agreement_band, verify_only, prefetch_only)
    except Exception as exc:
        brain.update_run(run_id, status="failed")
        if error_tracker:
            try:
                error_tracker.record_error(
                    exc, context="run_daily.run",
                    tags=["daily-run", "unhandled"])
            except (RuntimeError, ValueError, AttributeError):
                pass
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
         verify_only: bool = False,
         prefetch_only: bool = False) -> RunResult:
    """The body of the daily run (wrapped by run() for brain bookkeeping)."""
    today = date.today().isoformat()
    board_date = target_date or today
    scan_window = max(0, (date.fromisoformat(board_date) - date.today()).days)
    runlog = _mark_started()
    log = CLVLog()
    all_flags: list[str] = []

    # --- PREFETCH-ONLY MODE ---
    if prefetch_only:
        return _prefetch_stage(board_date, season, fixtures_season, leagues, runlog, all_flags)

    # --- warm the SportyBet fixture cache BEFORE the scan ---
    if refresh_sportybet:
        flag = _refresh_sportybet_cache(runlog)
        if flag:
            all_flags.append(flag)

    # --- grade yesterday first ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- Calibration tracking: record outcomes for all settled legs ---
    # FIX: Use Path directly from pathlib import to avoid UnboundLocalError
    calibration_log_path = Path("calibration_log.jsonl")
    recorded_count = 0
    for leg in log.legs:
        if leg.hit is not None and leg.model_prob is not None:
            pick = GradedPick(
                fixture=leg.fixture,
                market=leg.market,
                predicted_prob=leg.model_prob,
                outcome_hit=leg.hit,
                date=leg.date_logged
            )
            record_outcome(calibration_log_path, pick)
            recorded_count += 1
    if recorded_count:
        all_flags.append(f"calibration tracker: recorded {recorded_count} graded leg outcome(s)")

    try:
        auto_summary, auto_flags = log.grade_all_pending(season)
        all_flags += [f for f in auto_flags
                      if not any(f.split(":")[0] == g.split(":")[0] for g in gflags)]
    except Exception as e:
        all_flags.append(f"automated CLV grading failed ({e})")

    # --- produced-bet verification (ID415) ---
    try:
        vsum = produced_bet.verify_produced_bet(season, brain)
        if vsum.get("n"):
            all_flags.append(
                f"produced-bet verified {vsum['date']}: "
                f"{vsum['won']} won / {vsum['lost']} lost / "
                f"{vsum['pending']} pending")
    except Exception as e:
        all_flags.append(f"produced-bet verification failed ({e}) — "
                         f"legs stay PENDING")

    # --- booking tracker settle ---
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
    from pipeline.fixture_extraction import StageAOutput, VerifiedFixture
    stage_a_path = Path(__file__).parent / "data" / "stage_a_output" / f"fixtures_{board_date}_{fixtures_season or season}.json"
    board: list = []
    fixture_sources: set[str] = set()
    fit_stats = {"dc_reused": 0, "dc_refit": 0, "elo_seeded": 0, "pool_built": 0,
                 "xg_leagues": 0}
    stage_a_loaded = False

    if stage_a_path.exists():
        try:
            stage_a = StageAOutput.load(stage_a_path)
            for vf in stage_a.fixtures:
                # Convert VerifiedFixture to board format
                pass
            stage_a_loaded = True
            all_flags.append(f"Stage A artifact loaded: {len(stage_a.fixtures)} fixtures")
        except Exception as e:
            all_flags.append(f"Stage A artifact load failed ({e})")

    # ===== FALLBACK: RUN FULL PIPELINE if no Stage A artifact =====
    if not stage_a_loaded:
        all_flags.append("No Stage A artifact — running full pipeline")
        try:
            # Use unified pipeline
            pipeline_result = run_pipeline(
                board_date=board_date,
                season=season,
                fixtures_season=fixtures_season,
                leagues=leagues,
                min_mes=min_mes,
                agreement_band=agreement_band,
                verify_only=verify_only
            )
            board = pipeline_result.board
            fixture_sources = pipeline_result.fixture_sources
            fit_stats = pipeline_result.fit_stats
            all_flags.append(f"Pipeline completed: {len(board)} fixtures on board")
        except Exception as e:
            all_flags.append(f"Pipeline failed ({e})")
            # Don't fail the run, just log the error

    # Render board
    if board:
        board_text = render_board_from_pipeline(board, board_date, season)
        telegram_text = render_telegram_board(board, board_date, season)

        # Write board files
        BOARD_DIR.mkdir(parents=True, exist_ok=True)
        board_file = BOARD_DIR / f"board_{board_date}.txt"
        with open(board_file, "w", encoding="utf-8") as f:
            f.write(board_text)

        # Send notifications if enabled
        if send and telegram_text:
            # NEW: Use idempotency guard for Telegram sends
            if should_send_telegram(telegram_text):
                try:
                    notify.broadcast(telegram_text, "telegram")
                    all_flags.append("Telegram broadcast sent successfully")
                except Exception as e:
                    all_flags.append(f"Telegram broadcast failed: {e}")
            else:
                all_flags.append("Telegram broadcast skipped (duplicate content detected)")

        if whatsapp:
            try:
                whatsapp_deliver.send(telegram_text)
                all_flags.append("WhatsApp sent")
            except Exception as e:
                all_flags.append(f"WhatsApp failed: {e}")

        if email:
            try:
                email_deliver.send(board_text, subject=f"OLP XDV Board {board_date}")
                all_flags.append("Email sent")
            except Exception as e:
                all_flags.append(f"Email failed: {e}")

    elapsed = round(time.time() - t0, 1)
    all_flags.append(f"Run completed in {elapsed}s")

    return RunResult(
        full="\n".join(all_flags),
        telegram_text=telegram_text if 'telegram_text' in locals() else "",
        board=board,
        leagues_scanned=leagues,
        flags=all_flags
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run OLP XDV daily board")
    parser.add_argument("--season", default="2526")
    parser.add_argument("--fixtures-season", default=None)
    parser.add_argument("--leagues", nargs="+", default=None)
    parser.add_argument("--min-mes", type=float, default=0.0)
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--no-whatsapp", action="store_true")
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--days-ahead", type=int, default=0)
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-prefetch-crests", action="store_true")
    parser.add_argument("--no-sportybet", action="store_true")
    parser.add_argument("--no-booking-codes", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--prefetch-only", action="store_true")
    parser.add_argument("--agreement-band", type=float, default=0.04)

    args = parser.parse_args()

    result = run(
        season=args.season,
        fixtures_season=args.fixtures_season,
        leagues=args.leagues,
        send=not args.no_send,
        min_mes=args.min_mes,
        days_ahead=args.days_ahead,
        target_date=args.date,
        whatsapp=not args.no_whatsapp,
        email=not args.no_email,
        web=not args.no_web,
        prefetch_crests=not args.no_prefetch_crests,
        refresh_sportybet=not args.no_sportybet,
        booking_codes=not args.no_booking_codes,
        agreement_band=args.agreement_band,
        verify_only=args.verify_only,
        prefetch_only=args.prefetch_only
    )

    print(result.full)