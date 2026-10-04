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
import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PHASE_LABEL, PAPER_PHASE
from data.football_data_source import load_league
from engine.slate import (WHITELIST_LEAGUES, build_deploy_shortlist, market_blocked,
                          in_deploy_band, DEPLOY_ODDS_MIN, DEPLOY_ODDS_MAX,
                          DEPLOY_MIN_MODEL_PROB, AGREE_PP, BANKER_MIN,
                          CERTAINTY_HIGH_PP, MODEL_WEIGHT)
from engine import market_implied as mi
from engine import full_markets as fm

UNDER_PREF_PP = 0.03   # see ARCHITECT PREFERENCE in the selection loop
EV_PREF_PP = 0.02      # see VALUE-AWARE PICK in the selection loop
DRIFT_DEMOTE = 0.05    # see PRICE DRIFT (backtest/MARKET_STUDY.md Q2)
# DRAW GUARD (Architect 2026-10-04, backtest/DRAW_STUDY.md): real draws ran
# +0.8 pts above the closing price across leagues, +3 pts in Belgium and the
# Netherlands (both test periods). A pick that LOSES on a draw ("X or Y",
# straight wins, -handicaps) is marked down by that allowance, and a pick that
# survives a draw (1X / X2, draw no bet, +handicaps) within DRAW_PREF_PP wins.
DRAW_PREF_PP = 0.03
DRAW_ALLOWANCE_DEFAULT = 0.008
DRAW_ALLOWANCE = {"Belgian Pro League": 0.03, "Eredivisie": 0.03}
NEWS_SWAP_PP = 0.06    # see TEAM NEWS: a weakened pick swaps to a safe alternative
from engine.mes import mes_numeric
from engine import markets as mkt
from engine.form import compute_table, fixture_form, form_support as _form_support
from clv.clv_logger import CLVLog, compute_clv
from output.produce_bet import (render_produce_bet, render_verify_results,
                                render_canonical_board, render_heartbeat)
from output import notify
import orchestrator
import pipeline.odds as odds_mod
from pipeline import odds_verify
from verification import fixture_check
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


def _new_run_id(now: datetime | None = None) -> str:
    """OLPXDV-<UTC yyyymmdd-hhmm>-<6 hex>: printed at the start of the run and
    written to the run log, so every board traces to the run that built it
    (HR59; Telegram Output Spec §1)."""
    now = now or datetime.now(timezone.utc)
    return f"OLPXDV-{now:%Y%m%d-%H%M}-{secrets.token_hex(3)}"


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


def grade_open_legs(log: CLVLog, season: str,
                    fs_events: list | None = None) -> tuple[str, list[str]]:
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
    for lg in {l.league for l in pending} - {"ARCHITECT-FED"}:
        # ARCHITECT-FED = a /log leg on no board: no league to load; it is
        # graded from Flashscore by its match date below.
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
        table = results_by_league.get(leg.league) or {}
        try:
            home, away = [s.strip() for s in leg.fixture.split(" v ", 1)]
        except ValueError:
            continue
        # FLASHSCORE FALLBACK (2026-10-02): football-data has no FA Cup / UNL and
        # publishes days late. Settle from Flashscore's regular-time result; it
        # carries no closing price, so CLV stays NO DATA for these legs.
        if leg.match_date and (home, away, leg.match_date) not in table and fs_events:
            from data.flashscore_results import find_result
            ev = find_result(fs_events, home, away, leg.match_date)
            if ev and ev["finished_regular"]:
                hit = _settle(leg.market, ev["fthg"], ev["ftag"])
                if hit is not None:
                    log.log_result(leg.leg_id, ft_result=f'{ev["fthg"]}-{ev["ftag"]}', hit=hit)
                    graded += 1
                    rows.append({"fixture": leg.fixture, "ft": f'{ev["fthg"]}-{ev["ftag"]}',
                                 "onextwo": leg.market, "goals": f"entry {leg.entry_odds}",
                                 "btts": "CLV NO DATA (Flashscore has no prices)",
                                 "tally": "HIT" if hit else "MISS"})
            continue
        if not table:
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
    # Ladder picks (engine.full_markets keys "SB:...") are logged as the leg the
    # board actually deploys, with the consensus probability it was chosen on.
    for bf in board:
        k = bf.best_market_key
        if (not bf.on_deploy_shortlist or not k or not k.startswith("SB:")
                or not bf.best_price or not bf.kickoff_date):
            continue
        fixture_name = bf.fixture.split(" (")[0]
        if (fixture_name, k) in already:
            continue
        log.log_entry(league=bf.fixture.split("(")[-1].rstrip(")"),
                      fixture=fixture_name, market=k,
                      model_prob=bf.best_model_prob, entry_odds=bf.best_price,
                      entry_capture_path="CL-LIVE", phase=PAPER_PHASE,
                      stake=None, match_date=bf.kickoff_date)
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


_DRAW_CACHE: dict = {}


def _loses_on_draw(key: str) -> bool:
    """True if the outcome loses on EVERY draw (0-0, 1-1 and 2-2): "X or Y",
    straight wins, minus handicaps. A push is not a loss."""
    if key in _DRAW_CACHE:
        return _DRAW_CACHE[key]
    out = False
    if key and key.startswith("SB:"):
        pk = fm.parse_key(key)
        rule = fm.rule_for(*pk) if pk else None
        out = bool(rule) and all(rule(g, g) == "lose" for g in (0, 1, 2))
    else:
        out = all(mkt.settle(key, g, g) is False for g in (0, 1, 2))
    _DRAW_CACHE[key] = out
    return out


def run(season: str = "2526", fixtures_season: str | None = None,
        leagues: list[str] | None = None, send: bool = True,
        min_mes: float = 0.0, only_production: bool = False,
        heartbeat: bool = False, target_date: str | None = None) -> str:
    leagues = leagues or DEPLOY_LEAGUES
    today = date.today().isoformat()
    # The day the board is FOR. Defaults to today (the morning run); the evening
    # run passes tomorrow so the 10pm board targets the next day's card.
    target = target_date or today
    runlog = _mark_started()
    run_id = _new_run_id()
    print(f"  run_id={run_id}")
    _mark(runlog, f"run_id={run_id} target={target}")
    log = CLVLog()
    all_flags: list[str] = []

    # --- grade yesterday first, so the board reports an up-to-date gate ---
    # Flashscore results (last 7 days) settle the picks ledger and any CLV leg
    # football-data can't (FA Cup, UNL, late-published leagues).
    fs_events: list = []
    scorecard_text = None
    try:
        from data.flashscore_results import results_since
        fs_events = results_since(7)
    except Exception as e:  # noqa: BLE001 — grading degrades, the run does not
        all_flags.append(f"Flashscore results unavailable ({e}) — grading deferred")
    verify_block, gflags = grade_open_legs(log, season, fs_events)
    all_flags += gflags
    try:
        from engine import picks_ledger
        all_flags += picks_ledger.grade_all(fs_events)
        scorecard_text = picks_ledger.scorecard(7)
    except Exception as e:  # noqa: BLE001
        all_flags.append(f"picks scorecard unavailable ({e})")

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
            continue
        # PRICE CHECK (ID403 F2, on since 2026-10-03): each SportyBet price on
        # the board's day is checked against bet365 (football-data) and
        # DraftKings (ESPN), margin removed. A label only — nothing branches
        # on it (pipeline/odds_verify.py SCOPE).
        try:
            all_flags += odds_verify.check_prices(lg, fixtures, {target})
        except Exception as e:  # noqa: BLE001 — a check never blocks the board
            all_flags.append(f"{lg}: price check unavailable ({e})")

    # --- scan every league into one board (ID402 wide eyes) ---
    board: list = []
    for lg in leagues:
        slice_, flags = orchestrator.scan_one_league(
            lg, season, fixtures_season=fixtures_season)
        board += slice_
        all_flags += flags

    # TARGET DAY filter: when a specific day is requested (the evening run targets
    # tomorrow), keep only fixtures kicking off ON that date. A fixture with no
    # kickoff date can't be confirmed for the target day, so it's excluded (HR35 —
    # never assume a date). The morning run passes no target and scans the full
    # upcoming window as before.
    if target_date:
        before = len(board)
        board = [b for b in board
                 if b.kickoff_date and b.kickoff_date[:10] == target_date]
        all_flags.append(
            f"TARGET DAY {target_date}: {len(board)} fixture(s) kicking off that day "
            f"({before - len(board)} outside the target day excluded)")

    # FIXTURE CHECK (ID403 F2): every fixture is looked up in ESPN and
    # football-data; two independent sources agreeing -> ✓ VERIFIED. A match
    # another source lists POSTPONED/CANCELLED is a CONFLICT and comes off the
    # deploy list here, before any pick or booking code is made for it.
    try:
        all_flags += fixture_check.check_board(board)
    except Exception as e:  # noqa: BLE001 — a check never blocks the board
        all_flags.append(f"fixture check unavailable ({e}) — fixtures stay single-source")

    # Attach the best-EV live market to each fixture so HR30's numerical MES
    # can actually be stated, rather than falling back to an HR30 exception.
    ladder_fixtures = ladder_rejected = 0
    # AUTOMATIC LEARNING (improvement #6, engine.learning): every graded pick
    # corrects the next board. A market family or league whose picks won less
    # often than we said gets its chances cut (and can fall below the 50%
    # floor); one that beat them gets a small lift. Degrades to no correction.
    try:
        from engine import learning
        from engine.picks_ledger import LEDGER_DIR as _LD
        learned = learning.learn(_LD)
        learning_line = learning.summary(learned)
        all_flags.append(learning_line)
    except Exception as e:  # noqa: BLE001 — learning is optional, the run is not
        learning, learned, learning_line = None, {}, None
        all_flags.append(f"learning from results unavailable ({e})")
    for bf in board:
        if bf.probs is None:
            continue
        fx = odds_index.get((bf.probs.home_team, bf.probs.away_team))
        if fx is None:
            continue
        # Kickoff time for the board (order 28): SportyBet's event start; the
        # team-news step later uses FotMob's for deploy picks.
        if not getattr(bf, "kickoff_utc", None):
            bf.kickoff_utc = getattr(fx, "kickoff_utc", None) or None
        bf.price_check = getattr(fx, "verification", "") or None
        bf.price_note = getattr(fx, "price_note", "") or None
        p = bf.probs
        market_only = bf.prob_source == "market"
        _lg = bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
        sh = ((lambda k, _lg=_lg: learning.shift(learned, k, _lg)) if learned
              else (lambda k: 0.0))
        # Every in-band market, scored on CONSENSUS = average of the model and
        # the de-vigged market (engine.slate PICK TIERS; backtest/
        # SELECTION_STUDY.md). The price must sit inside the Architect's band
        # 1.20–2.00 and the consensus must be >= 50% ("winnable").
        cands: list = []   # (cons, ev, market, model_p, market_p, quote)
        for market in mkt.DEPLOYABLE:
            quote = mkt.quote(market, fx)
            model_p = mkt.model_prob(market, p)
            if quote is None or not quote.available or model_p is None:
                continue
            if not in_deploy_band(quote.price):
                continue
            market_p = mi.market_prob(market, fx)
            cons = (model_p if (market_only or market_p is None)
                    else market_p + MODEL_WEIGHT * (model_p - market_p)) + sh(market)
            if cons < DEPLOY_MIN_MODEL_PROB:   # never deploy a pick expected to lose
                continue
            ev = mes_numeric(cons, quote.price)
            cands.append((cons, ev if ev is not None else -1.0, market, model_p,
                          market_p, quote))
        # FULL MARKET LADDER (engine.full_markets): when SportyBet's whole
        # ladder is quoted, score EVERY full-time outcome in the band —
        # handicaps, Draw No Bet, team goals, clean sheets, Multigoals, combos —
        # on its WIN probability, averaged over the model's scoreline grid and
        # the bookmaker's (fitted to its 1X2 + O/U 2.5). A void (stake back) is
        # NOT a win: ranking on "no loss" picked bets that mostly just void
        # ("Home No Bet: Draw" — 98% no-loss, ~10% to actually win).
        ladder = fm.ladder(getattr(fx, "raw_markets", None))
        if ladder:
            ladder_fixtures += 1
            mgrid = fm.market_matrix(fx)
            dgrid = None if market_only else getattr(p, "matrix", None)
            cands = []
            for k, price, rule in ladder:
                if not in_deploy_band(price):
                    continue
                mk = fm.evaluate(mgrid, rule) if mgrid is not None else None
                # LINE CONSISTENCY GUARD: if the bookmaker's own 1X2 + goals
                # prices make this outcome far likelier than ITS price implies,
                # the line is mislabeled or stale (2026-10-03: N. Macedonia v
                # Scotland's -1.5 line mirrored the +1.5 line — "Scotland +1.5"
                # @1.32 was really ~30% to win). Never pick such a line.
                if mk is not None and mk[1] < 1:
                    if mk[0] / (1 - mk[1]) - 1 / price > fm.LINE_TOLERANCE:
                        ladder_rejected += 1
                        continue
                md = fm.evaluate(dgrid, rule) if dgrid is not None else mk
                if md is None:
                    continue
                cw, cp = md if mk is None else (mk[0] + MODEL_WEIGHT * (md[0] - mk[0]),
                                                mk[1] + MODEL_WEIGHT * (md[1] - mk[1]))
                win = round(cw + sh(k), 4)
                if win < DEPLOY_MIN_MODEL_PROB:
                    continue
                cands.append((win, cw * price + cp - 1, k, md[0],
                              None if (mk is None or market_only) else mk[0],
                              odds_mod.MarketQuote(price=price, bookmaker="sportybet",
                                                   n_books=1)))
        if not cands:
            continue

        # DRAW GUARD: mark draw-losing outcomes down by the league's draw allowance.
        _dallow = DRAW_ALLOWANCE.get(_lg, DRAW_ALLOWANCE_DEFAULT)
        cands = [((round(c[0] - _dallow, 4),) + c[1:]) if _loses_on_draw(c[2]) else c
                 for c in cands]
        cands = [c for c in cands if c[0] >= DEPLOY_MIN_MODEL_PROB] or cands

        def _agree(c):
            return c[4] is not None and abs(c[3] - c[4]) <= AGREE_PP

        bankers = [c for c in cands if not market_only
                   and c[2] in (mkt.HOME, mkt.AWAY, "SB:1||Home", "SB:1||Away")
                   and _agree(c) and c[0] >= BANKER_MIN]
        # ARCHITECT PREFERENCE (2026-10-02): Under-goals picks are disliked —
        # an early goal or two leaves them exposed. When a non-Under outcome is
        # within UNDER_PREF_PP of the top win probability, prefer it.
        def _is_under(k):
            return "|Under" in k or "& Under" in k or k in (mkt.UNDER_25, mkt.UNDER_15, mkt.UNDER_35)

        def _prefer_non_under(pool):
            if not pool:
                return pool
            top = max(c[0] for c in pool)
            near = [c for c in pool if c[0] >= top - UNDER_PREF_PP and not _is_under(c[2])]
            return near or pool

        # VALUE-AWARE PICK (Architect 2026-10-02, "positive EV"): among the
        # outcomes within EV_PREF_PP of the top win probability, take the one
        # with the best expected value (chance x price). Safety stays first —
        # only near-equal outcomes compete — so heavy-margin markets give way.
        # Narrowed 4 -> 2 pts after backtest/MARKET_STUDY.md Q3: a 4-pt window
        # cost ~2 pts of hit rate for no real gain in value.
        def _best(pool):
            top = max(c[0] for c in pool)
            pick = max((c for c in pool if c[0] >= top - EV_PREF_PP),
                       key=lambda c: (c[1], c[0]))
            # DRAW GUARD: a draw-safe outcome within DRAW_PREF_PP beats one
            # that loses on a draw (4 Oct: five "X or Y" picks lost to draws).
            if _loses_on_draw(pick[2]):
                safe = [c for c in pool if not _loses_on_draw(c[2])
                        and c[0] >= pick[0] - DRAW_PREF_PP]
                if safe:
                    return max(safe, key=lambda c: (c[0], c[1]))
            return pick

        # Every winnable in-band outcome, kept for the alternative market (order
        # 10), the team-news swap (order 24) and the bet365 board (order 29).
        # The Under preference below narrows the pool to within 3 pts of the
        # top for CHOOSING the pick only: on 2026-10-04 a learned +7.8 pt
        # Double Chance boost left nothing else within 3 pts, so 11 of 13
        # fixtures showed no alternative market.
        full_pool = list(cands)
        cands = _prefer_non_under(cands) if len(cands) > 1 else cands
        agreeing = _prefer_non_under([c for c in cands if _agree(c)])
        if bankers:
            best, tier = _best(bankers), "BANKER"
        elif market_only:
            best, tier = _best(cands), "MARKET"
        elif agreeing:
            # The strongest market the model AND the bookmaker both back.
            best, tier = _best(agreeing), "SAFE"
        else:
            # Model and bookmaker disagree on every in-band market. Follow the
            # BOOKMAKER's strongest outcome (Architect 2026-10-02: every
            # fixture in production). Backtest/SELECTION_STUDY.md: the
            # bookmaker's pick won 73.1% vs the model's 71.0%.
            book = [c for c in cands if c[4] is not None
                    and c[4] + sh(c[2]) >= DEPLOY_MIN_MODEL_PROB]
            if book:
                best = max(book, key=lambda c: (c[4] + sh(c[2]), c[1]))
                tier = "BOOK"
                # show the bookmaker's probability (with the learned correction)
                best = (round(best[4] + sh(best[2]), 4),) + best[1:]
            else:
                best, tier = max(cands), "SPLIT"
        # ALTERNATIVE MARKET: the next-best in-band market from a DIFFERENT
        # family than the pick (a real alternative, not 1.5 vs 2.5 of one line).
        fam = lambda k: k.split("|")[0] if k.startswith("SB:") else k.split("_")[0]
        alts = sorted((c for c in full_pool if fam(c[2]) != fam(best[2])), reverse=True)
        if alts:
            bf.alt_market = mkt.display(alts[0][2], p.home_team, p.away_team)
            bf.alt_price = alts[0][5].price
        bf.cand_pool = [c for c in full_pool if c[0] >= DEPLOY_MIN_MODEL_PROB]
        cons, ev, market, model_p, market_p, quote = best
        bf.best_market = mkt.display(market, p.home_team, p.away_team)
        bf.best_market_key = market
        bf.best_price = quote.price
        bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
        bf.best_mes_ev, bf.best_model_prob = (ev if ev != -1.0 else None), cons
        bf.tier, bf.pick_model_prob, bf.pick_market_prob = tier, model_p, market_p
        # CERTAINTY: how sure we are the % is right — two independent sources
        # agreeing tightly is the evidence. One source (market-implied) or a
        # disagreement (BOOK/SPLIT) can't be cross-checked, so it's LOW.
        if tier in ("BOOK", "SPLIT", "MARKET") or market_only or market_p is None:
            bf.certainty = "LOW"
        else:
            gap = abs(model_p - market_p)
            bf.certainty = ("HIGH" if gap <= CERTAINTY_HIGH_PP
                            else "MEDIUM" if gap <= AGREE_PP else "LOW")
        if tier == "SPLIT":
            # Model and market disagree: shown on the board, never deployed.
            # market_p can be None (no market price); formatting it with :.0%
            # used to crash the whole run, so it reads PENDING (HR35).
            bf.on_deploy_shortlist = False
            market_txt = "PENDING" if market_p is None else f"{market_p:.0%}"
            bf.rejection_reason = (
                f"SPLIT: model {model_p:.0%} vs market {market_txt} on "
                f"{bf.best_market} — disagreement > {AGREE_PP:.0%}, not deployed")

    if ladder_fixtures:
        all_flags.append(
            f"full market ladder: {ladder_fixtures} fixture(s) scored on every "
            f"full-time SportyBet market; {ladder_rejected} in-band line(s) skipped "
            f"as inconsistent with the book's own 1X2/goals prices")

    # --- TEAM TACTICAL PROFILES (engine.profiles, Architect 2026-10-04) ---
    # Each deploy pick gets its two teams' style over their last 20 games
    # (goals for/against, draws, BTTS, 3+ goals, clean sheets, shots on
    # target) as context on the board. Context only: backtest/DRAW_STUDY.md
    # found the profiles add nothing to the market's draw price, so they never
    # change a probability.
    try:
        import glob as _glob
        from engine import profiles as prof
        from engine import name_match as _nm
        _books: dict = {}
        profiled = 0
        for b in board:
            if not (b.on_deploy_shortlist and b.probs is not None):
                continue
            lg = b.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
            if lg not in _books:
                if lg in getattr(orchestrator.intl, "INTERNATIONAL_LEAGUES", set()):
                    _books[lg] = prof.ProfileBook(prof.national_rows())
                else:
                    files = sorted(_glob.glob(str(prof.CACHE / f"{lg.replace(' ', '_')}_[0-9]*.csv")))
                    _books[lg] = prof.ProfileBook(prof.club_rows(files[-3:])) if files else None
            book = _books[lg]
            if book is None:
                continue
            h, a = b.probs.home_team, b.probs.away_team
            names = _nm.resolve([h, a], list(book.by_team))
            mp = prof.match_profile(book, names.get(h, h), names.get(a, a))
            if mp.draw_tendency is not None:
                b.profile_line = mp.line()
                profiled += 1
        all_flags.append(f"team profiles: {profiled} deploy pick(s) profiled (last 20 games each side)")
    except Exception as e:  # noqa: BLE001 — context only, never blocks the run
        all_flags.append(f"team profiles unavailable ({str(e)[:60]})")

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

    # DEPLOY ODDS BAND gate: a single is deployable only if it found an in-band
    # pick (best_market_key set by the band-aware selection above). A deploy-
    # eligible fixture whose only priced markets sit outside 1.20–2.00 — or which
    # has no live price at all — drops out of THE CALL here, with the reason
    # surfaced. It still appears in the scan; it just isn't a capital single.
    band_dropped = 0
    for b in board:
        if b.on_deploy_shortlist and b.best_market_key is None:
            b.on_deploy_shortlist = False
            band_dropped += 1
            if b.best_price is not None:
                b.rejection_reason = (
                    f"no deploy: best price {b.best_price:.2f} outside the "
                    f"{DEPLOY_ODDS_MIN:.2f}–{DEPLOY_ODDS_MAX:.2f} odds band")
            else:
                b.rejection_reason = (b.rejection_reason
                    or "no deploy: no live price in the 1.20–2.00 odds band")
    if band_dropped:
        all_flags.append(
            f"deploy odds band {DEPLOY_ODDS_MIN:.2f}–{DEPLOY_ODDS_MAX:.2f}: "
            f"{band_dropped} fixture(s) dropped from THE CALL (price out of band)")

    shortlisted = [b for b in board if b.on_deploy_shortlist]
    capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
    for b in board:
        if b.on_deploy_shortlist and id(b) not in capped:
            b.on_deploy_shortlist = False

    # --- TEAM NEWS (improvement #2): injuries / suspensions / lineups ---
    # FotMob's predicted (later confirmed) XI and unavailable players, weighted
    # by market value. A pick whose team is missing key players is flagged and
    # its certainty drops a level; nothing is auto-dropped — the pre-kickoff
    # check (news_check.py) re-tests every pick once the XI is confirmed.
    try:
        from data import fotmob
        from engine import team_news as tn
        fm_matches = fotmob.matches_on(target)
        checked = flagged = swapped = 0
        for b in board:
            if not b.on_deploy_shortlist or b.probs is None or not b.best_market_key:
                continue
            m = fotmob.find_match(fm_matches, b.probs.home_team, b.probs.away_team)
            if not m:
                continue
            b.fotmob_id, b.kickoff_utc = m["id"], m["kickoff_utc"]
            try:
                news = fotmob.team_news(m["id"])
            except Exception:  # noqa: BLE001 — one match's news is optional
                news = None
            checked += 1
            b.team_news = news      # the bet365 board re-tests its own picks
            res = tn.assess(b.best_market_key, news)
            # A pick that depends on a WEAKENED team swaps to the likeliest
            # alternative the news doesn't touch (within NEWS_SWAP_PP), as
            # done by hand on 2026-10-02 (Bosnia v Sweden, Ukraine v N. Ireland).
            if res["level"] in ("CAUTION", "RISK") and news:
                for c in sorted(getattr(b, "cand_pool", []), reverse=True):
                    if c[2] == b.best_market_key or c[0] < b.best_model_prob - NEWS_SWAP_PP:
                        continue
                    if tn.assess(c[2], news)["level"] == "OK":
                        old_pick = b.best_market
                        b.best_market_key, b.best_price = c[2], c[5].price
                        b.best_market = mkt.display(c[2], b.probs.home_team, b.probs.away_team)
                        b.best_model_prob = c[0]
                        b.best_mes_ev = c[1] if c[1] != -1.0 else None
                        b.pick_model_prob, b.pick_market_prob = c[3], c[4]
                        # The tier and certainty follow the NEW pick: BANKER is a
                        # straight win only (order 11), and a pick with one
                        # source or a disagreement is LOW (order 15).
                        agree = c[4] is not None and abs(c[3] - c[4]) <= AGREE_PP
                        if b.tier == "BANKER" and c[2] not in (
                                mkt.HOME, mkt.AWAY, "SB:1||Home", "SB:1||Away"):
                            b.tier = "SAFE" if agree else "BOOK"
                        if (b.tier in ("BOOK", "SPLIT", "MARKET") or c[4] is None
                                or b.prob_source == "market"):
                            b.certainty = "LOW"
                        else:
                            gap = abs(c[3] - c[4])
                            b.certainty = ("HIGH" if gap <= CERTAINTY_HIGH_PP
                                           else "MEDIUM" if gap <= AGREE_PP else "LOW")
                        swapped += 1
                        res = {"level": "OK", "note": f"swapped from {old_pick} ({res['note']})"}
                        break
            b.news_level, b.news_note = res["level"], res["note"]
            if news:
                b.predicted_xi = {"home": news["home"]["xi_value"],
                                  "away": news["away"]["xi_value"]}
            if res["level"] in ("CAUTION", "RISK"):
                flagged += 1
                b.certainty = ("LOW" if res["level"] == "RISK" or b.certainty != "HIGH"
                               else "MEDIUM")
        all_flags.append(f"team news (FotMob): {checked} pick(s) checked, "
                         f"{flagged} flagged for injuries/suspensions, "
                         f"{swapped} swapped to an alternative the news doesn't touch")
    except Exception as e:  # noqa: BLE001 — news degrades, the run does not
        all_flags.append(f"team news unavailable ({e})")

    # --- PRICE DRIFT since the previous board for this day (MARKET_STUDY Q2) ---
    # The 7am refresh re-prices the picks the 10pm board published. A pick
    # whose price has drifted out DRIFT_DEMOTE+ since then lost -10.9% in the
    # backtest (shortened 5%+: +2.6%), so it drops to LOW certainty — out of
    # the 50%+ accas and the AI Survivor's first choices, stake halved.
    try:
        from engine.picks_ledger import LEDGER_DIR as _LD2
        _prev = _LD2 / f"picks_{target}.json"
        if _prev.exists():
            import json as _json
            prior = {(x["fixture"], x["market"]): (x.get("first_price") or x["price"])
                     for x in _json.loads(_prev.read_text(encoding="utf-8"))["singles"]
                     if x.get("price")}
            drifted = steamed = 0
            for b in board:
                if not (b.on_deploy_shortlist and b.best_market_key and b.best_price):
                    continue
                p0 = prior.get((b.fixture.split(" (")[0], b.best_market_key))
                if not p0:
                    continue
                b.first_price = p0
                b.drift_pct = round((b.best_price / p0 - 1) * 100, 1)
                if b.drift_pct >= DRIFT_DEMOTE * 100:
                    b.certainty = "LOW"
                    drifted += 1
                elif b.drift_pct <= -DRIFT_DEMOTE * 100:
                    steamed += 1
            all_flags.append(f"price drift since the last board: {drifted} pick(s) drifted "
                             f"{DRIFT_DEMOTE:.0%}+ (demoted to LOW), {steamed} shortened "
                             f"{DRIFT_DEMOTE:.0%}+ (market agrees)")
    except Exception as e:  # noqa: BLE001
        all_flags.append(f"price-drift check skipped ({e})")

    # --- SWITCH SHAKY PICKS (Architect 2026-10-04, standing order 32) ---
    # A pick that doesn't sit well — its price drifted out 5%+ since the last
    # board, the two prediction models disagree on the result it depends on,
    # or its certainty is LOW (model and SportyBet disagree) — moves to its
    # steadier alternative when one exists: a different market where model and
    # SportyBet agree, the news doesn't touch it, at most 5 pts less likely.
    # The original is kept on the record (switched_from, orig_market) and
    # graded too, so the weekly review shows whether switching pays.
    from output.produce_bet import steadier_pick as _steadier
    from engine import team_news as _tn
    _switched = 0
    for b in board:
        if not (b.on_deploy_shortlist and b.probs is not None and b.best_market_key):
            continue
        _drift = getattr(b, "drift_pct", None)
        if _drift is not None and _drift >= DRIFT_DEMOTE * 100:
            why = f"price drifted out {_drift:+.1f}% since the last board"
        elif b.engine_divergence and _tn.pick_side(b.best_market_key):
            why = "the two prediction models disagree on the result"
        elif b.certainty == "LOW":
            why = ("model and SportyBet disagree" if b.tier in ("BOOK", "SPLIT")
                   else "LOW certainty")
        else:
            continue
        c = _steadier(b, no_side=why.startswith("the two prediction"))
        if not c:
            continue
        win, ev, key, model_p, market_p, quote = c
        old_label = b.best_market
        b.orig_market_key = b.best_market_key
        b.best_market_key, b.best_price = key, quote.price
        b.best_market = mkt.display(key, b.probs.home_team, b.probs.away_team)
        b.best_model_prob, b.best_mes_ev = win, (ev if ev != -1.0 else None)
        b.pick_model_prob, b.pick_market_prob = model_p, market_p
        b.certainty = ("HIGH" if abs(model_p - market_p) <= CERTAINTY_HIGH_PP else "MEDIUM")
        b.tier = ("BANKER" if key in (mkt.HOME, mkt.AWAY, "SB:1||Home", "SB:1||Away")
                  and win >= BANKER_MIN else "SAFE")
        b.switched_from = f"{old_label} ({why})"
        _switched += 1
    all_flags.append(f"switched shaky picks: {_switched} moved to a steadier market (order 32)")

    # ALTERNATIVE MARKET after team news (order 31): Table 1's "Alt market" is
    # the same leg the alt-market accas book — a different market family from
    # the (possibly swapped) pick, never one the team news flags.
    from output.produce_bet import alt_leg as _alt_leg
    for b in board:
        if b.on_deploy_shortlist and b.probs is not None:
            _a = _alt_leg(b)
            b.alt_market = (mkt.display(_a[0], b.probs.home_team, b.probs.away_team)
                            if _a else None)
            b.alt_price = _a[2] if _a else None

    # --- VALUE: how many picks are positive-EV on our own chance ---
    _dep = [b for b in board if b.on_deploy_shortlist and b.best_mes_ev is not None]
    if _dep:
        _pos = sum(b.best_mes_ev > 0 for b in _dep)
        all_flags.append(
            f"value: {_pos}/{len(_dep)} picks positive EV on our chance x price "
            f"(avg EV {100 * sum(b.best_mes_ev for b in _dep) / len(_dep):+.1f}%); "
            f"the scorecard tracks whether +EV picks really return more")

    # --- STAKING (improvement #7): % of bankroll tied to each tier's proven edge ---
    staking_line = None
    try:
        from engine import staking
        from engine.picks_ledger import LEDGER_DIR
        tstats = staking.tier_stats(LEDGER_DIR)
        for b in board:
            if b.on_deploy_shortlist and b.tier:
                b.stake_pct, b.stake_why = staking.single_stake(
                    b.tier, b.certainty, b.best_price, tstats)
        staking_line = staking.summary(tstats)
        all_flags.append(staking_line)
    except Exception as e:  # noqa: BLE001 — guidance only; never blocks the run
        all_flags.append(f"staking guidance unavailable ({e})")

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
    acca_codes: dict = {}
    safe3_codes: dict = {}
    mega_codes = None          # dict once the picks are split into mega slips
    extra_codes: dict = {}     # per-table mega codes (Architect 2026-10-03)
    alt_codes: dict = {}       # alt-market accas (order 31)
    _sb_index_holder: dict = {"index": None}
    try:
        from output.produce_bet import (_build_accas, _build_alt_accas, _build_megas,
                                        _build_safe3)
        from pipeline import sportybet_booking as sbk

        def _leg(b):
            # Book the SAME in-band market the board deploys (best_market_key),
            # not the price-agnostic model pick — the code must match the single.
            league = b.fixture.rsplit("(", 1)[-1].rstrip(")").strip()
            return (league, b.probs.home_team, b.probs.away_team, b.best_market_key)

        finalists = [b for b in board if b.on_deploy_shortlist and b.probs is not None]
        if finalists:
            sb_index = _sb_index_holder["index"] = sbk._event_index()
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
                deploy = [b for b in board if b.on_deploy_shortlist]

                def _book(groups) -> dict:
                    out = {}
                    for name, legs, _combo in groups:
                        ls = [_leg(bf) for bf, _pick, _prob in legs]
                        if all(l[3] for l in ls):
                            code, _ = sbk.code_for_legs(sb_index, ls)
                            if code:
                                out[name] = code
                    return out

                accas = _build_accas(deploy)
                acca_codes = _book(accas)
                acca_code = acca_codes.get("Acca A")
                safe3 = _build_safe3(deploy)
                safe3_codes = _book(safe3)
                if len(safe3) > 1:      # Table 3A mega: every 50%+ acca on one slip
                    _all3 = [(b3, p3, q3) for _n, ls3, _c in safe3 for b3, p3, q3 in ls3]
                    extra_codes.update({k.replace("ALL", "safe3_mega"): v for k, v in
                                        _book([("ALL", _all3, 0)]).items()})
                all_flags.append(f"50%+ accas: {len(safe3_codes)}/{len(safe3)} booked "
                                 f"(3 legs, high-certainty legs only)")
                alt_accas = _build_alt_accas(deploy)
                for _name, _legs, _c in alt_accas:
                    _ls = [(bf.fixture.rsplit("(", 1)[-1].rstrip(")").strip(),
                            bf.probs.home_team, bf.probs.away_team, key)
                           for bf, _pick, _prob, key, _price in _legs]
                    _code, _ = sbk.code_for_legs(sb_index, _ls)
                    if _code:
                        alt_codes[_name] = _code
                all_flags.append(f"alt-market accas: {len(alt_codes)}/{len(alt_accas)} booked "
                                 f"(a different market from each fixture's main pick)")
                megas = _build_megas(deploy)
                if len(megas) > 1:
                    mega_codes = _book(megas)
                else:
                    board_legs = [l for l in (_leg(b) for b in finalists) if l[3]]
                    board_code, _ = sbk.code_for_legs(sb_index, board_legs)
                all_flags.append(
                    f"SportyBet booking codes: {booked}/{len(finalists)} singles, "
                    f"{len(acca_codes)}/{len(accas)} accas, "
                    + (f"{len(mega_codes)}/{len(megas)} mega slips" if len(megas) > 1
                       else f"board code {'set' if board_code else 'PENDING'}"))
    except Exception as e:  # noqa: BLE001 — codes are optional; the run is not
        all_flags.append(f"booking-code step skipped ({e}) — codes shown as PENDING")

    # --- PICKS LEDGER: record exactly what this board recommends, for grading ---
    try:
        from engine import picks_ledger
        from output.produce_bet import _build_accas, _build_megas, _build_safe3
        for b in board:     # SportyBet identity, for the closing-price capture (#5)
            if b.probs is None:
                continue
            fx = odds_index.get((b.probs.home_team, b.probs.away_team))
            b.sb_event_id = getattr(fx, "event_id", None) if fx else None
            if fx and not getattr(b, "kickoff_utc", None):
                b.kickoff_utc = fx.kickoff_utc
            b.sb_tid = SPORTYBET_TOURNAMENT_ID.get(
                b.fixture.rsplit("(", 1)[-1].rstrip(")").strip())
        dep = [b for b in board if b.on_deploy_shortlist]
        megas_l = _build_megas(dep)
        from output.produce_bet import _build_alt_accas as _alt_accas
        picks_ledger.write_ledger(target, board, _build_accas(dep), _build_safe3(dep),
                                  megas_l if len(megas_l) > 1 else [],
                                  acca_codes, safe3_codes, mega_codes,
                                  alts=_alt_accas(dep), alt_codes=alt_codes)
    except Exception as e:  # noqa: BLE001
        all_flags.append(f"picks ledger not written ({e})")

    # --- AI SURVIVOR: the heartbeat lineage (engine.survivor) ---
    # Grade the lineages' picks, breed the winners, and give every free living
    # lineage one of today's board singles. A --no-send (dry) run works on a
    # throwaway copy so it never changes the real lineage.
    survivor_text = None
    try:
        import shutil
        import tempfile
        from engine import survivor
        sdir = survivor.STATE_DIR
        if not send:
            sdir = Path(tempfile.mkdtemp()) / "survivor"
            if survivor.STATE_DIR.exists():
                shutil.copytree(survivor.STATE_DIR, sdir)
        survivor_text, sflags = survivor.daily(board, target, fs_events, state_dir=sdir)
        all_flags += sflags
        # AI SURVIVOR MEGA CODE: every lineage pick for the day on one slip
        # (each pick also keeps its own single code).
        _spop, _shist = survivor.load(sdir)
        _spicks = [h for h in _shist if h["date"] == target and h.get("result") == "PENDING"]
        if len(_spicks) > 1 and _sb_index_holder["index"]:
            from pipeline import sportybet_booking as _sbk
            _scode, _ = _sbk.code_for_legs(_sb_index_holder["index"],
                                           [(h["league"], h["home"], h["away"], h["market_key"])
                                            for h in _spicks])
            survivor_text += (f"\nAI Survivor mega code (all {len(_spicks)} lineage picks): "
                              f"{_scode or 'PENDING'}")
    except Exception as e:  # noqa: BLE001 — the lineage never blocks the board
        all_flags.append(f"AI Survivor step skipped ({e})")

    # The Telegram message is the Architect's canonical ##########OLP XDV#########
    # board (four tables + honest footer). The detailed HR53 per-fixture audit
    # (render_produce_bet) is preserved in the SAVED board as an appendix, so
    # the repo record keeps the full MES / Elo / divergence trail while the
    # phone gets the clean canonical board.
    telegram_text = render_canonical_board(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board,
        acca_code=acca_code, board_code=board_code, board_date=target,
        acca_codes=acca_codes, mega_codes=mega_codes, safe3_codes=safe3_codes,
        extra_codes=extra_codes, run_id=run_id, alt_codes=alt_codes)

    detail_text = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL, leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"], data_flags=all_flags, board=board)

    full = (telegram_text
            + "\n\n" + "=" * 60 + "\n\n" + verify_block
            + "\n\n" + "=" * 60 + "\n\n"
            + "DETAIL — HR53 full per-fixture audit (not sent to Telegram)\n\n"
            + detail_text)
    path = BOARD_DIR / f"board_{target}.txt"

    # --only-production: deliver only when the run actually produced picks. This
    # keeps the phone quiet on the empty paper-calibration slates (no odds, no
    # deploy-eligible fixtures) while still committing every board to the repo.
    produced = _has_production(board, logged_count)
    deliver_now = send and (produced or not only_production)
    board_delivered = False

    if deliver_now:
        # SEND GATE (HR59, standing order 30): no valid Run ID, no Telegram.
        # The board is still saved; the run fails so the failure alert fires.
        gate = notify.board_gate(telegram_text)
        if gate:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(full, encoding="utf-8")
            _mark(runlog, f"RUN FAILED — {gate}")
            raise RuntimeError(gate)
        # The Architect's chat and every subscriber chat (order 33, via
        # notify.deliver). One subscriber failing is logged; it never fails the run.
        delivered, notes = notify.deliver(telegram_text, save_to=None)
        board_delivered = delivered
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

    # bet365 BOARD (standing order 29): the same picks limited to bets bet365
    # offers, saved beside the board and sent as its OWN message, only to the
    # Architect's own chat — never to a subscriber.
    # Best-effort like the heartbeat: it never fails the run.
    try:
        from output import bet365_board
        b365_text = bet365_board.render(board, board_date=target, run_id=run_id)
        b365_path = BOARD_DIR / f"bet365_{target}.txt"
        b365_path.parent.mkdir(parents=True, exist_ok=True)
        b365_path.write_text(b365_text, encoding="utf-8")
        b365_gate = notify.board_gate(b365_text)
        # The Architect's own chat ONLY (order 29): TELEGRAM_OWNER_CHAT_ID if
        # set, else TELEGRAM_CHAT_ID — the Architect's chat — and never a
        # subscriber chat (TELEGRAM_SUBSCRIBER_CHAT_IDS).
        owner_chat = (os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
                      or os.environ.get("TELEGRAM_CHAT_ID", "").strip())
        if b365_gate:
            _mark(runlog, f"bet365 board: {b365_gate}")
        elif not owner_chat:
            _mark(runlog, "bet365 board saved, NOT sent: no Architect chat configured")
        elif deliver_now and bet365_board.picks(board)[0]:
            b_ok, b_notes = notify.send_telegram(b365_text, chat_id=owner_chat)
            for n in b_notes:
                _mark(runlog, f"bet365 board: {n}")
            print("  bet365 board " + ("delivered" if b_ok else "NOT delivered"))
    except Exception as e:  # noqa: BLE001 — the bet365 board never blocks the run
        _mark(runlog, f"bet365 board error ({e})")

    # HEARTBEAT — a short 'system alive' ping sent EVERY day (even dry days), so
    # silence never looks like a dead system. Best-effort: a heartbeat that fails
    # to send is logged but does NOT fail the run — the board carries the hard
    # delivery gate; the heartbeat is informational. Subscribers get it too
    # (order 33, via notify.deliver).
    if heartbeat and send:
        try:
            hb = render_heartbeat(PHASE_LABEL, leagues, status["legs_with_clv"],
                                  status["mean_clv_pct"], board, board_delivered,
                                  board_date=target,
                                  scorecard="\n\n".join(x for x in (scorecard_text, staking_line,
                                                                  learning_line, survivor_text)
                                                        if x))
            hb_ok, hb_notes = notify.deliver(hb, save_to=None)
            for n in hb_notes:
                _mark(runlog, f"heartbeat: {n}")
            print("  heartbeat " + ("delivered" if hb_ok else "NOT delivered"))
            _mark(runlog, "heartbeat delivered" if hb_ok else "heartbeat NOT delivered")
        except Exception as e:  # noqa: BLE001 — heartbeat is best-effort
            _mark(runlog, f"heartbeat error ({e})")

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
    ap.add_argument("--heartbeat", action="store_true",
                     help="send a short 'system alive' heartbeat every day, even on "
                          "dry days (in addition to the board on pick days)")
    ap.add_argument("--target-date", default=None,
                     help="build the board for this day only (YYYY-MM-DD): keep only "
                          "fixtures kicking off on it. Default: full upcoming window.")
    ap.add_argument("--next-day", action="store_true",
                     help="target tomorrow's fixtures (the evening run's job); "
                          "shorthand for --target-date <tomorrow>")
    a = ap.parse_args()
    tgt = a.target_date
    if a.next_day and not tgt:
        from datetime import timedelta
        tgt = (date.today() + timedelta(days=1)).isoformat()
    print(f"OLP XDV daily run — for {tgt or date.today().isoformat()} — {PHASE_LABEL}")
    out = run(season=a.season, fixtures_season=a.fixtures_season,
              leagues=a.leagues, send=not a.no_send, min_mes=a.min_mes,
              only_production=a.only_production, heartbeat=a.heartbeat,
              target_date=tgt)
    print("\n" + out)
