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
from engine import recalibration as recal
from clv.clv_logger import CLVLog, compute_clv
from output.produce_bet import (render_produce_bet, render_verify_results,
                                render_telegram_board)
from output import notify
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

def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, days_ahead: int = 0) -> RunResult:
    """Run the daily board end to end.

    Opens the brain, seeds the ledger + corrections mirrors, records the run
    as 'running', and marks it FAILED on any exception — a board that never
    reached the phone is not a completed run, so the launcher can alert."""
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
                    leagues, send, min_mes, days_ahead)
    except Exception:
        brain.update_run(run_id, status="failed")
        raise
    finally:
        brain.close()


def _run(run_id: str, started: str, t0: float, brain: Brain,
         season: str, fixtures_season: str | None, leagues: list[str],
         send: bool, min_mes: float, days_ahead: int) -> RunResult:
    """The body of the daily run (wrapped by run() for brain bookkeeping)."""
    today = date.today().isoformat()
    runlog = _mark_started()
    log = CLVLog()
    all_flags: list[str] = []

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    verify_block, gflags = grade_open_legs(log, season)
    all_flags += gflags

    # --- scan every league into one board (ID402 wide eyes). The board is the
    # --- day's matches (days_ahead=0): 'today's board', not a 14-day lookahead.
    # --- Each league reports its fit outcome (reused vs refit, seeded vs cold)
    # --- so the run row proves the brain's speed win rather than assuming it.
    fit_stats = {"dc_reused": 0, "dc_refit": 0, "elo_seeded": 0, "pool_built": 0,
                 "xg_leagues": 0}
    board: list = []
    for lg in leagues:
        st: dict = {}
        slice_, flags = orchestrator.scan_one_league(
            lg, season, fixtures_season=fixtures_season, days_ahead=days_ahead,
            brain=brain, stats=st)
        board += slice_
        all_flags += flags
        for k in fit_stats:
            fit_stats[k] += int(st.get(k, False))

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
            fixtures, oflags = odds_mod.fetch_odds(lg)
            odds_index.update(odds_mod.index_by_fixture(fixtures))
            all_flags += oflags
        except odds_mod.QuotaExhausted as e:
            all_flags.append(f"{lg}: {e}")
        except Exception as e:
            all_flags.append(f"{lg}: odds fetch failed ({e}) — NO DATA — PENDING")

    # CLV-gated recalibration: the engine's probabilities for THE CALL's EV are
    # nudged by settled-leg evidence ONLY where a market has enough logged CLV
    # legs (engine/recalibration.py). Inert until that evidence exists — right
    # now it is entirely dormant. The ledger still stores the RAW model_prob.
    cal = recal.adjustments_for(brain.calibration_by_market())
    if cal:
        all_flags.append("Calibration active: "
                         + ", ".join(f"{m} {d:+.1%}" for m, d in sorted(cal.items()))
                         + " (from settled-leg CLV evidence, bounded ±3pts)")

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
            raw_p = mkt.model_prob(market, p)
            if quote is None or not quote.available or raw_p is None:
                continue
            # EV is priced on the CALIBRATED probability; the raw estimate is
            # what the ledger records (no feedback loop).
            ev = mes_numeric(recal.apply(raw_p, cal.get(market)), quote.price)
            if ev is not None and (best is None or ev > best[0]):
                best = (ev, market, raw_p, quote)
        if best:
            ev, market, raw_p, quote = best
            bf.best_market = mkt.display(market, p.home_team, p.away_team)
            bf.best_price = quote.price
            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
            bf.best_mes_ev = ev  # computed on the calibrated probability
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

    status = log.phase2_status()
    all_flags.append(
        f"Phase 3 gate: {status['legs_with_clv']} of {status['gate_requirement']} "
        f"legs with logged CLV; mean CLV "
        f"{status['mean_clv_pct'] if status['mean_clv_pct'] is not None else 'NO DATA — PENDING'}")

    telegram_text = render_telegram_board(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    board_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    full = board_text + "\n\n" + "=" * 60 + "\n\n" + verify_block
    path = BOARD_DIR / f"board_{today}.txt"
    if send:
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
    return brain.append_predictions(rows)


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
    print("\n" + out.full)
