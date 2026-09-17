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
import traceback
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
# Derives the fixtures season from the fit season ('2526' -> '2627'); needed by
# the Stage A artifact path, which previously reused the fit season by mistake.
from orchestrator_DEPRECATED import next_season_code
from output.board_validator import filter_board_for_telegram
from output.render_fixture_list import render_fixture_list
from booking.verify_fixtures import _parse_bet365_datetime
from output import whatsapp_deliver
from output import email_deliver
import bets.produced_bet as produced_bet
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

# Booking drives Playwright against SportyBet, which has hung for 10+ minutes in
# practice. Bounded so a stuck browser cannot hold the run open indefinitely --
# the board is already written by the time booking starts, so a timeout costs
# the codes, not the board.
BOOKING_TIMEOUT_S = 600
LOG_DIR = Path(__file__).parent / "logs"


def _mark_started() -> Path:
    """Mark the start of a run by creating a runlog file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    runlog = LOG_DIR / f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
    with open(runlog, "w", encoding="utf-8", errors="replace") as f:
        f.write(f"Run started at {datetime.now(timezone.utc).isoformat()}\n")
    return runlog


def _acca_to_dict(acca) -> dict:
    """One Acca as the shape booking_codes._load_acca_payload expects.

    Contract taken from a known-good payload (acca_2026-08-09.json) rather than
    invented: label / combined_odds / combined_prob / n_legs / legs[], with each
    leg carrying fixture, league, market_key, market_name, price, prob, ev and
    sportybet_fixture_id.
    """
    legs = []
    for lg in (getattr(acca, "legs", None) or []):
        legs.append({
            "fixture": lg.fixture,
            "league": lg.league,
            "market_key": lg.market_key,
            "market_name": lg.market_name,
            "price": lg.price,
            "prob": lg.prob,
            "ev": lg.ev,
            # Carried through so the booker can skip resolution when the
            # pre-production gate already identified the SportyBet fixture.
            "sportybet_fixture_id": getattr(lg, "sportybet_fixture_id", None),
        })
    return {
        "label": getattr(acca, "label", "Acca"),
        "combined_odds": getattr(acca, "combined_odds", None),
        "combined_prob": getattr(acca, "combined_prob", None),
        "n_legs": len(legs),
        "legs": legs,
    }


def _write_acca_payload(board_date: str, stage_b) -> Optional[Path]:
    """Write output/boards/acca_<date>.json from Stage B's acca route.

    Returns the path, or None when there is nothing capital-eligible to book --
    in which case no file is written at all. An empty payload would be worse
    than none: booking would read it, find no legs, and report a clean "nothing
    added" that is indistinguishable from a successful run with no selections.
    """
    route = getattr(stage_b, "acca_route", None)
    if route is None:
        return None

    # Read the full list. Taking acca_a/acca_b only would cap the BOOKING
    # payload at two regardless of how many the route carries, so accas C and D
    # would render on the board and then never reach booking_codes — visible to
    # the Architect, silently unbookable.
    accas = [a for a in (getattr(route, "accas", None) or [])
             if a is not None and (getattr(a, "legs", None) or [])]
    if not accas:
        accas = [a for a in (getattr(route, "acca_a", None), getattr(route, "acca_b", None))
                 if a is not None and (getattr(a, "legs", None) or [])]

    # The single best standalone leg rides along as its own one-leg acca, the
    # same way the booker treats singles.
    slv = getattr(route, "slv", None)
    if slv is not None:
        from engine.acca import Acca as _Acca
        accas.append(_Acca(label=f"SINGLE — {slv.fixture}", legs=[slv]))

    if not accas:
        return None

    payload = {
        "date": board_date,
        "n_accas": len(accas),
        "accas": [_acca_to_dict(a) for a in accas],
    }
    BOARD_DIR.mkdir(parents=True, exist_ok=True)
    path = BOARD_DIR / f"acca_{board_date}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _run_heartbeat_lineage(board_date: str, stage_b) -> tuple[str, list[str]]:
    """Produce the day's heartbeat(s) and advance the lineage population.

    WHY THIS EXISTS (2026-09-17): the heartbeat/lineage subsystem was complete
    and correct-ish in `engine/heartbeat_lineage.py` and `output/heartbeat.py`,
    and NOTHING CALLED IT. `run_daily.py` contained zero references to either
    module, and `daily_analysis_agent.py` -- the only other caller -- is not
    scheduled anywhere (no reference in any .py/.bat/.ps1/.yml). So the daily
    07:00 heartbeat the analysis agent reports on was never generated by the
    daily run at all.

    The evidence of that gap: data/heartbeat/history.jsonl stops on 2026-09-01,
    lineage_ledger.jsonl stops on 2026-09-01, and data/heartbeat/lineage.json
    holds a single genesis lineage born 2026-09-03 that has been alive and
    unfed ever since -- 0W-0L, no fixture, no pick -- while the analysis agent
    reported "No heartbeat record found" and "Alive: 0/0".

    Ordering matters: BREED first (yesterday's winners reproduce into today's
    population), then SELECT (assign today's fixtures to the living lineages).
    Breeding after selection would hand today's fixtures to lineages that are
    about to be replaced.

    Returns (report_text, flags). Never raises -- a heartbeat failure must not
    take down a board that is otherwise ready to publish.
    """
    flags: list[str] = []
    try:
        from engine import heartbeat_lineage as HL
        from output.heartbeat import render_heartbeat_telegram, save_heartbeat_record

        board = list(getattr(getattr(stage_b, "layer2", None), "fixtures", []) or [])
        if not board:
            flags.append("heartbeat: SKIPPED — Stage B produced no board fixtures")
            return "", flags

        # 1. Breed: yesterday's winners reproduce, losers stay dead.
        pop = HL.breed_next_generation(board, target_date=board_date)

        # 2. Select: assign today's highest-EDGE priced candidates to the living
        #    lineages. require_priced stays at its default (True) -- an unpriced
        #    pick cannot be settled and has no measured edge, so it must not
        #    become a heartbeat just to keep the streak alive (HR35).
        heartbeats = HL.select_daily_heartbeats(board, target_date=board_date)

        if not heartbeats:
            n_living = len(pop.living())
            flags.append(
                f"heartbeat: NO QUALIFYING CANDIDATE for {board_date} — "
                f"{len(board)} fixture(s) scanned, none priced with positive edge; "
                f"{n_living} lineage(s) skip a generation"
            )
            return HL.render_lineage_report(), flags

        # 3. Record the selections (result stays PENDING until graded).
        for hb in heartbeats:
            save_heartbeat_record(hb, result="PENDING")

        flags.append(
            f"heartbeat: {len(heartbeats)} selected for {board_date} "
            f"(top edge {heartbeats[0].edge:+.2%} on {heartbeats[0].fixture})"
        )

        parts = [render_heartbeat_telegram(hb) for hb in heartbeats]
        parts.append(HL.render_lineage_report())
        return "\n\n".join(parts), flags

    except Exception as e:
        flags.append(f"heartbeat: FAILED ({type(e).__name__}: {e})")
        return "", flags


def _mark(runlog: Path, message: str) -> None:
    """Append a message to the runlog.

    Encoding is pinned to UTF-8 with a replacement fallback because this is the
    function the failure paths call. Without it, open() takes the Windows
    default (cp1252), and a message carrying characters cp1252 cannot encode
    raises UnicodeEncodeError *inside the except block* that was handling a
    recoverable error -- turning "SportyBet cache refresh failed, continue" into
    a fatal pipeline crash. Playwright's own "please run playwright install"
    notice is drawn with box characters, so it triggered exactly that.
    """
    with open(runlog, "a", encoding="utf-8", errors="replace") as f:
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
    _mark(runlog, f"DEBUG: board_date in _prefetch_stage = {board_date}")

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

    # 5. Pre-fetch injury/squad lists from TheSportsDB - SKIPPED due to missing function
    _mark(runlog, f"Fetching injury/squad data...")
    all_flags.append("Injury/squad data prefetch skipped (function not implemented)")
    _mark(runlog, f"  Injuries: SKIPPED")

    elapsed = round(time.time() - t0, 1)
    _mark(runlog, f"PREFETCH COMPLETE — {elapsed}s")
    all_flags.append(f"Prefetch completed in {elapsed}s — data/cache/ populated for {board_date}")

    return RunResult(
        full="\n".join(all_flags),
        telegram_text=f"Prefetch completed for {board_date} in {elapsed}s",
        board=[],
        leagues_scanned=leagues,
    )


def _refresh_sportybet_cache(runlog: Path, leagues: Optional[list] = None) -> Optional[str]:
    """Refresh SportyBet fixture cache with headless browser.

    `leagues` should be the competitions the board actually references. The
    cache exists to price THIS board, and SportyBet throttles: scraping 30
    competitions to serve a board that names 4 is what gets a pass refused
    part-way, leaving the cache half-filled with no indication why. Falls back
    to SCAN_LEAGUES when the caller has nothing more specific.
    """
    try:
        from booking.bridge import refresh_sportybet_cache
        targets = list(leagues) if leagues else SCAN_LEAGUES
        _mark(runlog, f"Refreshing SportyBet cache ({len(targets)} competitions)...")
        import asyncio
        # Run the async function in a new event loop
        result = asyncio.run(refresh_sportybet_cache(leagues=targets, days_ahead=3))
        total = sum(result.values()) if result else 0
        _mark(runlog, f"SportyBet cache refreshed: {total} fixtures")
        return f"SportyBet cache refreshed: {total} fixtures across {len(result)} leagues"
    except Exception as e:
        _mark(runlog, f"SportyBet cache refresh failed: {e}")
        _mark(runlog, f"Full traceback: {traceback.format_exc()}")
        # Return degraded status instead of letting it bubble up and crash the run
        return f"SportyBet cache refresh degraded: {e}"


def grade_open_legs(log: CLVLog, season: str) -> tuple[str, list[str]]:
    """Grade open legs and return verification block and flags."""
    flags = []
    try:
        # Use grade_all_pending which is the actual method name in CLVLog
        summary, gflags = log.grade_all_pending(season)
        flags.extend(gflags)
        verify_block = f"Automated CLV grading: {summary.get('graded', 0)} leg(s) settled"
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
        # Scrape only the competitions this board references. The Stage A
        # artifact already knows them -- it is the verified slate for this
        # date -- so read the leagues off it rather than scraping everything.
        _cache_leagues = None
        try:
            _sa = Path(__file__).parent / "data" / "stage_a_output" / \
                f"fixtures_{board_date}_{fixtures_season or next_season_code(season)}.json"
            if _sa.exists():
                _cache_leagues = sorted({
                    f.get("league") for f in json.loads(
                        _sa.read_text(encoding="utf-8")).get("fixtures", [])
                    if f.get("league")
                })
        except Exception:
            # Falling back to the full list is safe; it is only slower.
            _cache_leagues = None

        flag = _refresh_sportybet_cache(runlog, leagues=_cache_leagues)
        if flag:
            all_flags.append(flag)

    # --- grade yesterday first ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- Calibration tracking: record outcomes for all settled legs ---
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
    # `season` is the season the MODEL is fit on (the last COMPLETED one);
    # fixtures come from the season now being played. This path used
    # `fixtures_season or season`, and fixtures_season is None unless
    # --fixtures-season is passed explicitly, so it looked for
    # fixtures_<date>_2526.json while Stage A writes fixtures_<date>_2627.json.
    # The artifact was therefore never found on a default invocation, the run
    # logged "No Stage A artifact" and fell through to the demonstration
    # fallback in olp_xdv_pipeline -- which publishes hardcoded probabilities.
    # Derive it properly instead of silently reusing the fit season.
    _fixtures_season = fixtures_season or next_season_code(season)
    stage_a_path = Path(__file__).parent / "data" / "stage_a_output" / f"fixtures_{board_date}_{_fixtures_season}.json"
    board: list = []
    # Initialised up front: both the Stage A/Stage B branch and the fallback
    # assign these conditionally, and the render block below now tests them, so
    # leaving them undefined until one branch happens to run risks a NameError
    # on the path where Stage B loads but returns no text.
    board_text: str = ""
    telegram_text: str = ""
    heartbeat_text: str = ""
    # True only when render_production_board actually produced messages.
    #
    # SEND GATE (spec §0/§1, Architect 2026-09-17). The ratified spec names
    # render_production_board as the ONLY Telegram render path and requires the
    # send gate to reject anything without a valid run_id — "a code-level gate,
    # not a review step". Until now the gate was NEGATIVE: it blocked the one
    # known-bad path (the demonstration fallback) and let everything else
    # through, so any OTHER degraded path still published. That is how the
    # legacy five-league "Phase 2 — paper calibration" board kept reaching
    # Telegram: Stage B falling back to the old renderer is not the fallback
    # pipeline, so fallback_is_unpublishable stayed False and delivery went
    # ahead.
    #
    # Positive gating is the difference between "block what we know is bad" and
    # "send only what we know is good". Only the second one holds when a new
    # failure mode appears.
    production_board_ok: bool = False
    fixture_sources: set[str] = set()
    fit_stats = {"dc_reused": 0, "dc_refit": 0, "elo_seeded": 0, "pool_built": 0,
                 "xg_leagues": 0}
    stage_a_loaded = False

    if stage_a_path.exists():
        try:
            stage_a = StageAOutput.load(stage_a_path)

            # This loop used to be a bare `pass` with the comment "Convert
            # VerifiedFixture to board format" -- the conversion was never
            # implemented. It walked every fixture, did nothing, and then set
            # stage_a_loaded = True, which ALSO suppressed the fallback below.
            # So both paths produced nothing: with an artifact the board stayed
            # empty, without one run_pipeline returned an empty structure. That
            # is why no board had been written since 2026-08-21, the date of the
            # last Stage A artifact on disk.
            #
            # pipeline.production_stage_b.run_stage_b already implements the
            # whole of Stage B -- enrichment, the acca route, the pick and the
            # four-table render. It simply was never called from here.
            from pipeline.production_stage_b import run_stage_b, render_stage_b_output

            stage_b = run_stage_b(
                stage_a_path=stage_a_path,
                season=season,
                fixtures_season=fixtures_season,
            )
            # StageBOutput exposes layer2/layer1/acca_route/the_pick, not a
            # `board` list -- the rendered text IS the deliverable here.
            stage_b_text = render_stage_b_output(stage_b)
            if stage_b_text:
                board_text = stage_b_text
                telegram_text = stage_b_text

            # TELEGRAM: the ratified FINAL TELEGRAM OUTPUT SPEC (§0) names
            # render_production_board + render_acca_route as the ONLY Telegram
            # render path and SUSPENDS the four-table blend that
            # render_stage_b_output emits. stage_b_text stays as board_text --
            # it is still the on-disk board artifact -- but what goes to
            # Telegram is the stacked per-fixture format.
            #
            # Falls back to stage_b_text if the spec renderer returns nothing,
            # because an empty Telegram payload would suppress the board
            # entirely and a suppressed board is worse than an old format.
            try:
                from output.production_board import render_production_board
                _msgs = render_production_board(
                    list(getattr(getattr(stage_b, "layer2", None), "fixtures", []) or []),
                    board_date,
                    run_id,
                    acca_route=getattr(stage_b, "acca_route", None),
                )
                if _msgs:
                    telegram_text = "\n\n".join(_msgs)
                    production_board_ok = True
                    all_flags.append(
                        f"production board rendered: {len(_msgs)} Telegram "
                        f"message(s) per ratified spec"
                    )
                else:
                    all_flags.append(
                        "production board EMPTY — every fixture held off the "
                        "board (spec §2 requires a confirmed kickoff); "
                        "falling back to the Stage B render"
                    )
            except Exception as e:
                all_flags.append(
                    f"production board render failed ({type(e).__name__}: {e}) "
                    f"— falling back to the Stage B render"
                )
            n_rows = len(getattr(getattr(stage_b, "layer2", None), "rows", []) or [])

            # Persist the acca payload booking reads. Nothing wrote
            # acca_<date>.json -- only readers existed -- so booking_codes
            # always raised FileNotFoundError on today's date and fell back to
            # whatever stale file was on disk (the newest was 2026-08-31).
            try:
                _acca_path = _write_acca_payload(board_date, stage_b)
                if _acca_path:
                    all_flags.append(f"acca payload written: {_acca_path.name}")
            except Exception as e:
                all_flags.append(f"acca payload write failed ({type(e).__name__}: {e})")

            # Heartbeat + lineage. Previously never invoked from here at all,
            # which is why no heartbeat has been produced since 2026-09-01.
            _hb_text, _hb_flags = _run_heartbeat_lineage(board_date, stage_b)
            all_flags.extend(_hb_flags)
            if _hb_text:
                heartbeat_text = _hb_text

            fixture_sources.update(
                s for vf in stage_a.fixtures for s in (vf.source or "").split("+") if s
            )
            stage_a_loaded = True
            all_flags.append(
                f"Stage A artifact loaded: {len(stage_a.fixtures)} fixtures; "
                f"Stage B rendered {len(stage_b_text)} chars, {n_rows} grid row(s)"
            )
        except Exception as e:
            # Stage A existing but Stage B failing must not silently fall
            # through to the empty fallback and look like a normal quiet day.
            all_flags.append(f"Stage A artifact load failed ({type(e).__name__}: {e})")

    # ===== FALLBACK: RUN FULL PIPELINE if no Stage A artifact =====
    #
    # HR35/HR59 GUARD (2026-09-16). This branch calls olp_xdv_pipeline.run_pipeline,
    # whose Agent 5 does NOT run the engines. It assigns a hardcoded table of
    # (market, probability, odds) tuples -- its own comments read "sample
    # positive EV selections for demonstration", "In a real implementation,
    # this would come from the engine/models" and "Ensure we always have some
    # positive EV selections for testing" -- onto whatever real fixture names
    # it holds.
    #
    # On 2026-09-16 a default `python run_daily.py` took this branch (the Stage
    # A path above was looking for the wrong season) and BROADCAST the result to
    # Telegram: eleven legs carrying probabilities of exactly 85.0/80.0/75.0/70.0
    # percent, six of them priced "@ 0.00", the same fixture listed twice under
    # two different leagues, stamped "Decision: CEO_APPROVE".
    #
    # Fabricated output reaching a delivery channel is the exact failure HR35
    # and HR59 exist to prevent, so this branch is now barred from publishing.
    # It may still run and write a board for inspection, but it cannot send.
    # Remove this guard only when Agent 5 computes probabilities from the
    # engines rather than from a literal table.
    fallback_is_unpublishable = False
    if not stage_a_loaded:
        fallback_is_unpublishable = True
        all_flags.append("No Stage A artifact — running full pipeline")
        all_flags.append(
            "HR35 GUARD: fallback pipeline uses hardcoded demonstration "
            "probabilities, not engine output — delivery suppressed, board is "
            "NOT a real call"
        )
        try:
            # Use unified pipeline
            state = run_pipeline(
                season=season,
                fixtures_season=fixtures_season,
                # NOTE: this flag is currently INERT. run_pipeline() stores it
                # in state["dry_run"] and no agent ever reads it, so it does not
                # actually suppress network calls -- the previous comment here
                # ("use dry-run to avoid network calls for testing") describes
                # behaviour that does not exist and reads like production is in
                # test mode. Left as-is pending an Architect decision on whether
                # dry-run should be wired up or the parameter removed.
                dry_run=True
            )
            # Render board and telegram from pipeline state
            board_text = render_board_from_pipeline(state)
            telegram_text = board_text
        except Exception as e:
            all_flags.append(f"Pipeline failed ({e})")
            # Don't fail the run, just log the error
            board_text = ""
            telegram_text = ""
        else:
            # Counting fixtures is reporting, not production. It used to sit
            # inside the try above, where it crashed with "'list' object has no
            # attribute 'get'" -- run_pipeline() defines state["payloads"] as a
            # LIST of per-agent dicts, but this line indexed it like a dict
            # keyed by agent number. The except branch then reset board_text to
            # "", discarding the board render on the line above, which had
            # already succeeded. That is why boards were written as 0 bytes on
            # 2026-09-05/06/08/09: the board was built correctly, then thrown
            # away because a status-string failed to format. Counting now runs
            # in `else` so it can never discard a good board.
            try:
                agent5 = next(
                    (p for p in reversed(state.get("payloads", []))
                     if isinstance(p, dict) and p.get("agent") == 5),
                    {},
                )
                n_fixtures = len(agent5.get("fixture_reports", {}))
                all_flags.append(f"Pipeline completed: {n_fixtures} fixtures processed")
            except Exception as e:
                all_flags.append(f"Pipeline completed (fixture count unavailable: {e})")

    # Render board.
    #
    # Condition includes board_text so the Stage B path reaches the write and
    # notify steps below. Stage B returns its output as rendered text rather
    # than as a `board` list, so gating purely on `board` meant a successful
    # Stage B run produced a full four-table board in memory and then wrote
    # nothing to disk and sent nothing -- indistinguishable, from the outside,
    # from the pipeline not running at all.
    if board or board_text:
        board_artifacts = render_board_from_pipeline(
            board=board,
            date_str=board_date
        ) if board else {}
        # Only take this renderer's output if Stage B did not already produce
        # the board. Stage B emits the full four-table structure (market grid,
        # layer-1 compact, acca route, the pick); this renderer emits the
        # thinner summary. Overwriting unconditionally would silently discard
        # the richer board whenever both ran.
        rendered_board = board_artifacts.get(f"board_{board_date}.txt", "")
        rendered_telegram = board_artifacts.get(f"telegram_{board_date}.txt", "")
        if not board_text:
            board_text = rendered_board
        if not telegram_text:
            telegram_text = rendered_telegram

        # Append the heartbeat to the Telegram payload. It rides with the board
        # rather than as a second broadcast: the heartbeat is the day's single
        # trackable pick and is meaningless without the board it came from.
        # Gated on telegram_text so a heartbeat can never be broadcast on its
        # own from an otherwise empty/suppressed run.
        if heartbeat_text and telegram_text:
            telegram_text = f"{telegram_text}\n\n{'-' * 32}\n\n{heartbeat_text}"

        # Write board files
        BOARD_DIR.mkdir(parents=True, exist_ok=True)
        board_file = BOARD_DIR / f"board_{board_date}.txt"
        with open(board_file, "w", encoding="utf-8") as f:
            f.write(board_text)

        # Heartbeat artifact. Written whenever one was produced, so the day's
        # heartbeat is inspectable on disk next to the board rather than only
        # existing inside a Telegram message.
        if heartbeat_text:
            heartbeat_file = BOARD_DIR / f"heartbeat_{board_date}.txt"
            with open(heartbeat_file, "w", encoding="utf-8") as f:
                f.write(heartbeat_text)
            all_flags.append(f"heartbeat artifact written: {heartbeat_file.name}")

        # ===== BOOKING CODES =====
        # The `booking_codes` flag was declared in run(), passed to _run(),
        # declared again in its signature and read NOWHERE, so codes were never
        # generated no matter how the flag was set. Wired up here.
        #
        # Gated on `not fallback_is_unpublishable` for the same reason delivery
        # is: a booking code is a REAL, placeable artefact. Generating one from
        # the demonstration fallback's hardcoded probabilities would be worse
        # than publishing that board, because a code can be acted on directly.
        if booking_codes and not fallback_is_unpublishable:
            acca_file = BOARD_DIR / f"acca_{board_date}.json"
            if not acca_file.exists():
                all_flags.append(
                    "booking codes skipped — no capital-eligible acca for "
                    f"{board_date} (nothing to book, not a failure)")
            else:
                try:
                    import subprocess
                    # Run as a subprocess: booking drives Playwright and can
                    # hang on SportyBet, and a stuck browser must not take the
                    # board down after it has already been written to disk.
                    proc = subprocess.run(
                        [sys.executable, "-m", "booking.booking_codes",
                         "--date", board_date],
                        cwd=str(Path(__file__).parent),
                        capture_output=True, text=True, timeout=BOOKING_TIMEOUT_S,
                    )
                    codes_file = BOARD_DIR / f"acca_{board_date}_codes.json"
                    if codes_file.exists():
                        got = json.loads(codes_file.read_text(encoding="utf-8"))
                        n_ok = sum(1 for r in (got.get("results") or [])
                                   if r.get("code"))
                        n_tot = len(got.get("results") or [])
                        all_flags.append(
                            f"booking codes: {n_ok}/{n_tot} generated")
                    else:
                        all_flags.append(
                            "booking codes: produced no codes file "
                            f"(exit {proc.returncode})")
                except subprocess.TimeoutExpired:
                    all_flags.append(
                        f"booking codes: timed out after {BOOKING_TIMEOUT_S}s — "
                        "board is unaffected, codes read NO DATA — PENDING")
                except Exception as e:
                    all_flags.append(
                        f"booking codes failed ({type(e).__name__}: {e})")
        elif booking_codes and fallback_is_unpublishable:
            all_flags.append(
                "booking codes SUPPRESSED — board came from the demonstration "
                "fallback; a code must never be generated from fabricated "
                "probabilities (HR35)")

        # Send notifications if enabled.
        # `not fallback_is_unpublishable` enforces the HR35 guard above: a board
        # built from the fallback's hardcoded demonstration probabilities is
        # written to disk for inspection but never delivered.
        if fallback_is_unpublishable and send:
            all_flags.append(
                "Telegram/WhatsApp/email delivery SUPPRESSED — board came from "
                "the demonstration fallback, not the engines (HR35)"
            )

        # POSITIVE SEND GATE (spec §0/§1). Nothing goes out unless the ratified
        # production board rendered it. The board is still written to disk for
        # inspection either way — suppressing DELIVERY is not the same as
        # losing the run.
        if send and not production_board_ok and not fallback_is_unpublishable:
            all_flags.append(
                "Telegram/WhatsApp/email delivery SUPPRESSED — the ratified "
                "production board did not render, so the only thing available "
                "to send was the superseded legacy format (spec §0). Board "
                "written to disk; nothing delivered."
            )

        if send and telegram_text and production_board_ok and not fallback_is_unpublishable:
            # NEW: Use idempotency guard for Telegram sends
            if should_send_telegram(telegram_text):
                try:
                    notify.broadcast(telegram_text, "telegram")
                    all_flags.append("Telegram broadcast sent successfully")
                except Exception as e:
                    all_flags.append(f"Telegram broadcast failed: {e}")
            else:
                all_flags.append("Telegram broadcast skipped (duplicate content detected)")

        # Both channels carry the same HR35 guard as Telegram — suppressing one
        # delivery path while leaving two others open would not be a guard.
        # They now carry the POSITIVE production-board gate for the same reason:
        # gating Telegram alone would just move the superseded legacy board onto
        # WhatsApp and email instead of stopping it.
        if whatsapp and production_board_ok and not fallback_is_unpublishable:
            try:
                whatsapp_deliver.send(telegram_text)
                all_flags.append("WhatsApp sent")
            except Exception as e:
                all_flags.append(f"WhatsApp failed: {e}")

        if email and production_board_ok and not fallback_is_unpublishable:
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