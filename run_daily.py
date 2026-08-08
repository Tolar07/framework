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
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brain.store import Brain
from config import PHASE_LABEL, PAPER_PHASE
from data.football_data_source import load_league
from engine.softness import (SOFTNESS_TIER, DEPLOY_ELIGIBLE_TIERS,
                             build_deploy_shortlist, market_blocked)
from engine.mes import mes_numeric
from engine import markets as mkt
from engine.consensus import compute_consensus
from engine import recalibration as recal
from clv.clv_logger import CLVLog, compute_clv
from clv.closing_capture import capture_closing_lines
from output.produce_bet import (render_produce_bet, render_verify_results,
                                render_telegram_board)
from output import notify
from output import whatsapp_deliver
from output import email_deliver
import orchestrator
import pipeline.odds as odds_mod

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


# SCAN is "wide eyes" (ID402): every whitelisted league is pulled and shown,
# approved competition or not — capturing a fixture is what the board is for.
# DEPLOY stays "narrow hands": build_deploy_shortlist below still draws THE CALL
# only from softness A/B, capped at 6. Decoupling the two is what lets an
# approved league appear on the board without silently widening what can carry
# capital — showing a competition is not staking it.
SCAN_LEAGUES = list(SOFTNESS_TIER.keys())


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

def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, days_ahead: int = 3,
        whatsapp: bool = True, email: bool = True,
        web: bool = True, prefetch_crests: bool = False) -> RunResult:
    """Run the daily board end to end.

    Opens the brain, seeds the ledger + corrections mirrors, records the run
    as 'running', and marks it FAILED on any exception — a board that never
    reached the phone is not a completed run, so the launcher can alert.

    `prefetch_crests` (default OFF so library/test callers stay offline) fetches
    missing club badges from TheSportsDB after the web payload is written. The
    CLI enables it by default (env OLP_PREFETCH_CRESTS=0 disables)."""
    leagues = leagues or SCAN_LEAGUES
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
                    leagues, send, min_mes, days_ahead, whatsapp, email, web,
                    prefetch_crests)
    except Exception:
        brain.update_run(run_id, status="failed")
        raise
    finally:
        brain.close()


def _run(run_id: str, started: str, t0: float, brain: Brain,
         season: str, fixtures_season: str | None, leagues: list[str],
         send: bool, min_mes: float, days_ahead: int,
         whatsapp: bool = True, email: bool = True,
         web: bool = True, prefetch_crests: bool = False) -> RunResult:
    """The body of the daily run (wrapped by run() for brain bookkeeping)."""
    today = date.today().isoformat()
    runlog = _mark_started()
    log = CLVLog()
    all_flags: list[str] = []

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- scan every league into one board (ID402 wide eyes). The board is the
    # --- next 3 days' matches (days_ahead=3, ratified 2026-08-07): a rolling
    # --- window like ScoreGPT, so a quiet midweek still shows the weekend round
    # --- and preseason still shows the first fixtures of the season. Today-only
    # --- (days_ahead=0) was reversed — it produced empty boards in early
    # --- August when no league has a fixture literally today.
    # --- Each league reports its fit outcome (reused vs refit, seeded vs cold)
    # --- so the run row proves the brain's speed win rather than assuming it.
    fit_stats = {"dc_reused": 0, "dc_refit": 0, "elo_seeded": 0, "pool_built": 0,
                 "xg_leagues": 0}
    board: list = []
    fixture_sources: set[str] = set()
    for lg in leagues:
        st: dict = {}
        slice_, flags = orchestrator.scan_one_league(
            lg, season, fixtures_season=fixtures_season, days_ahead=days_ahead,
            brain=brain, stats=st)
        board += slice_
        all_flags += flags
        for k in fit_stats:
            fit_stats[k] += int(st.get(k, False))
        if st.get("fixture_source"):
            fixture_sources.add(st["fixture_source"])

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

    # --- live entry prices, pulled ONLY for leagues that actually produced a
    # --- rated fixture today. Scan-only leagues' prices can never be deployed,
    # --- so pulling them burns quota for nothing; and a deploy league with no
    # --- fixtures today (a quiet midweek) needs no price pull either — the old
    # --- order fetched all 6 deploy leagues before the scan, and today wasted
    # --- ~10s doing so. Fixture LISTS are already cached (6h) inside the scan.
    def _league_of(bf) -> str:
        return bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture \
            else "—"
    odds_leagues = {_league_of(bf) for bf in board if bf.probs is not None
                    and SOFTNESS_TIER.get(_league_of(bf)) in DEPLOY_ELIGIBLE_TIERS}
    odds_index: dict = {}
    for lg in sorted(odds_leagues):
        try:
            # Retry a transient network blip once before degrading to NO DATA.
            fixtures, oflags = _retry_transient(
                lambda lg=lg: odds_mod.fetch_odds(lg), f"{lg} live odds", runlog)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags += oflags
        except odds_mod.QuotaExhausted as e:
            all_flags.append(f"{lg}: {e}")
        except Exception as e:
            all_flags.append(f"{lg}: odds fetch failed ({e}) — NO DATA — PENDING")

    # ID414: widen bookmaker coverage — pull odds for ONE scan-only league
    # if quota permits. The free plan allows 500 req/mo (~16/day); A/B pulls
    # use ~10/day. One scan-league pull (2 credits) leaves ~4/day headroom.
    # Priority: Championship > Serie A > Bundesliga > Ligue 1 > Primeira Liga
    # > Premier League > La Liga > Champions League (all scan-only tiers).
    if not odds_leagues:
        # No deploy fixtures today — still try the top scan league if quota OK.
        scan_only_leagues = [lg for lg in SCAN_LEAGUES
                             if SOFTNESS_TIER.get(lg) not in DEPLOY_ELIGIBLE_TIERS]
    else:
        scan_only_leagues = [lg for lg in SCAN_LEAGUES
                             if lg not in odds_leagues
                             and SOFTNESS_TIER.get(lg) not in DEPLOY_ELIGIBLE_TIERS]
    # Priority order for scan leagues (biggest interest first)
    priority = ["Championship", "Serie A", "Bundesliga", "Ligue 1",
                "Primeira Liga", "Premier League", "La Liga", "Champions League"]
    for lg in priority:
        if lg in scan_only_leagues:
            # Check quota first without spending
            try:
                used, remaining = odds_mod.check_quota()
                if remaining >= odds_mod.QUOTA_FLOOR:
                    try:
                        fixtures, oflags = _retry_transient(
                            lambda lg=lg: odds_mod.fetch_odds(lg),
                            f"{lg} scan odds", runlog)
                        odds_index.update(odds_mod.index_by_fixture(fixtures))
                        all_flags += oflags
                        all_flags.append(f"Scan odds: {lg} pulled (quota {remaining})")
                    except odds_mod.QuotaExhausted as e:
                        all_flags.append(f"{lg}: {e}")
                    except Exception as e:
                        all_flags.append(f"{lg}: scan odds failed ({e})")
                    break  # only ONE scan league per run
                else:
                    all_flags.append(f"Scan odds skipped — quota {remaining} < floor {odds_mod.QUOTA_FLOOR}")
            except Exception as e:
                all_flags.append(f"Scan odds quota check failed: {e}")
            break

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
    def _market_implied(market: str, fx) -> Optional[float]:
        if mkt.MARKETS_1X2.get(market) is not None:
            p1x2 = mkt.implied_1x2(fx)
            return p1x2[mkt.MARKETS_1X2[market]] if p1x2 else None
        if market in (mkt.OVER_25, mkt.UNDER_25):
            price = fx.over25.price if market == mkt.OVER_25 else fx.under25.price
            other = fx.under25.price if market == mkt.OVER_25 else fx.over25.price
            if price and other:
                s = 1 / price + 1 / other
                return (1 / price) / s if s > 1.0 else None
        return None

    for bf in board:
        if bf.probs is None:
            continue
        fx = odds_index.get((bf.probs.home_team, bf.probs.away_team))
        if fx is None:
            continue
        p = bf.probs

        # BOOKMAKER (ID413) + MARKET-ANCHORED PROBABILITY (ID414): compute
        # the devigged implied 1X2 and the blend before the EV loop so both
        # are available for every market decision.
        bf.market_probs = mkt.implied_1x2(fx)
        if bf.market_probs is not None:
            bf.consensus = compute_consensus(
                bf.probs, bf.elo_probs, bf.xg_probs, bf.market_probs)
            if bf.probs is not None:
                mh, md, ma = bf.market_probs
                bp = (mkt.blend_toward_market(p.p_home, mh),
                      mkt.blend_toward_market(p.p_draw, md),
                      mkt.blend_toward_market(p.p_away, ma))
                if any(abs(bp[i] - v) > 0.005
                       for i, v in enumerate((p.p_home, p.p_draw, p.p_away))):
                    bf.blend_probs = bp

        best = None
        for market in mkt.DEPLOYABLE:
            quote = mkt.quote(market, fx)
            raw_p = mkt.model_prob(market, p)
            if quote is None or not quote.available or raw_p is None:
                continue
            # EV is priced on the BLEND — the honest probability when model
            # and market disagree (ID414). Ledger keeps RAW model_est via
            # best_model_prob; calibration stays inert (no feedback loop).
            mp = _market_implied(market, fx)
            p_ev = mkt.blend_toward_market(recal.apply(raw_p, cal.get(market)), mp)
            ev = mes_numeric(p_ev, quote.price)
            if ev is not None and (best is None or ev > best[0]):
                best = (ev, market, raw_p, quote)
        if best:
            ev, market, raw_p, quote = best
            bf.best_market = mkt.display(market, p.home_team, p.away_team)
            bf.best_price = quote.price
            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
            bf.best_mes_ev = ev  # priced on the blend; raw prob on the ledger
            bf.best_model_prob = raw_p  # ledger keeps the RAW model estimate
            bf.best_market_key = market  # canonical key for the brain's ledger
            bf.cal_adjustment = cal.get(market, 0.0)

    # --- never forget a prediction: persist every rated board prediction ---
    n_preds = _predictions_from_board(board, run_id, started, brain)

    shortlisted = [b for b in board if b.on_deploy_shortlist]
    capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
    for b in board:
        if b.on_deploy_shortlist and id(b) not in capped:
            b.on_deploy_shortlist = False

    # --- log the paper legs (the point of Phase 2) ---
    _, lflags = log_paper_legs(log, board, odds_index, min_mes=min_mes)
    all_flags += lflags

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
    all_flags.append(
        f"Phase 3 gate: {status['legs_with_clv']} of {status['gate_requirement']} "
        f"legs with logged CLV; mean CLV "
        f"{status['mean_clv_pct'] if status['mean_clv_pct'] is not None else 'NO DATA — PENDING'}")

    # ID414: ScoreGPT parity data — yesterday's graded fixtures + 7-day rolling
    # stats, computed once and shared by the Telegram push and the web payload.
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    yesterday_graded = brain.graded_yesterday(yesterday)
    rolling_7d = brain.rolling_7d()

    telegram_text = render_telegram_board(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board,
        yesterday_graded=yesterday_graded, rolling_7d=rolling_7d)

    board_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    full = board_text + "\n\n" + "=" * 60 + "\n\n" + verify_block
    path = BOARD_DIR / f"board_{today}.txt"

    # The web dashboard (webapp/) reads board_<today>.json — the local server
    # and the hosted static export both consume it, so today's board is
    # available without re-running the pipeline. Additive and cheap; written
    # whether or not delivery happens. Toggled by --no-web / web=False.
    if web:
        try:
            from webapp import schema as web_schema
            from output.produce_bet import render_daily_recommendation
            web_schema.write_payload(
                web_schema.build_payload(
                    date=today, phase=PHASE_LABEL, leagues_scanned=leagues,
                    board=board, data_flags=all_flags,
                    gate=brain.gate_status(),
                    telemetry=brain.leg_telemetry(),
                    calibration_count=status["legs_with_clv"],
                    mean_clv=status["mean_clv_pct"],
                    recommendation=render_daily_recommendation(board),
                    yesterday_graded=yesterday_graded,
                    rolling_7d=rolling_7d),
                BOARD_DIR / f"board_{today}.json")
            if prefetch_crests:
                # Best-effort club-badge prefetch so the dashboard carries real
                # TheSportsDB crests, not just initials. Never raises; a failed
                # lookup is a miss, not a fault (HR35).
                try:
                    from webapp import crests as _crests
                    n = len(_crests.prefetch(
                        _crests.teams_from_board(
                            BOARD_DIR / f"board_{today}.json")))
                    _mark(runlog, f"crest prefetch added {n} badge(s)")
                except Exception as e:
                    _mark(runlog, f"crest prefetch skipped ({e})")
        except Exception as e:
            _mark(runlog, f"web payload write failed ({e}) — txt board unaffected")

    if send:
        # BOARD_URL (set once the dashboard is hosted) appends a link to the
        # Telegram push so the phone goes from summary to full board in one tap.
        board_url = os.environ.get("BOARD_URL", "").strip()
        push_text = (f"{telegram_text}\n\nFull board: {board_url}"
                     if board_url else telegram_text)
        delivered, notes = notify.deliver(push_text, save_to=None)
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
    _mark(runlog, "run completed OK")
    brain.update_run(
        run_id, status="ok",
        finished_at=datetime.now(timezone.utc).isoformat(),
        leagues_scanned=len(leagues), fixtures_seen=len(board),
        predictions_logged=n_preds,
        legs_logged=status["legs_logged_total"],
        fit_seconds=round(time.time() - t0, 1),
        warnings=json.dumps(all_flags),
        **fit_stats)
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
                    softness_tier=bf.softness_tier,
                    on_deploy_shortlist=int(bf.on_deploy_shortlist),
                    entry_odds=None, bookmaker=None, ev=None,
                    cal_adjustment=None)
        for key, prob in (("1X2_HOME", p.p_home), ("1X2_DRAW", p.p_draw),
                          ("1X2_AWAY", p.p_away), ("OVER_1_5", p.p_over_15),
                          ("OVER_2_5", p.p_over_25), ("BTTS_YES", p.p_btts_yes)):
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
    ap.add_argument("--days-ahead", type=int, default=3,
                    help="fixture window in days from today (3 = next 3 days)")
    ap.add_argument("--no-prefetch-crests", action="store_true",
                    help="skip the club-badge prefetch even when the web board is written")
    a = ap.parse_args()
    print(f"OLP XDV daily run — {date.today().isoformat()} — {PHASE_LABEL}")
    # The CLI pre-warms club badges by default (real runs have the network);
    # env OLP_PREFETCH_CRESTS=0 or --no-prefetch-crests turns it off.
    prefetch = (not a.no_prefetch_crests
                and os.environ.get("OLP_PREFETCH_CRESTS", "1") != "0")
    out = run(season=a.season, fixtures_season=a.fixtures_season,
              leagues=a.leagues, send=not a.no_send, min_mes=a.min_mes,
              days_ahead=a.days_ahead,
              whatsapp=not a.no_whatsapp, email=not a.no_email,
              web=not a.no_web, prefetch_crests=prefetch)
    print("\n" + out.full)
