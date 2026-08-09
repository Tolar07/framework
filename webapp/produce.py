"""Real-time fixture prediction production — the 'BET Production' trigger.

Admin searches for fixtures, selects them, and clicks Produce. This module
calls the engine in real time and returns predictions without writing to the
board store (the daily run owns the ledger — this is a preview/what-if tool).

Phase-2 constraints:
  - NEVER stakes capital (config.assert_paper_only untouched)
  - NEVER logs legs or predictions (daily run owns the ledger)
  - NEVER writes board files (preview only — admin reviews then publishes)
  - DEPLOY_POOL_CAP=6 enforced on the produced board
  - HR35: missing history → honest NO DATA — PENDING, never guessed
"""
from __future__ import annotations

import time
from typing import Optional


def search_fixtures(league: Optional[str] = None, query: str = "",
                    days: int = 7, date: str = "") -> dict:
    """Search available fixtures across whitelisted leagues.

    `date` (ISO YYYY-MM-DD) narrows the result to fixtures kicking off on
    exactly that day (read from the sources' dates map). Empty date keeps the
    whole `days` window — the "produce for a chosen day" flow passes a date.

    Returns {"ok": True, "leagues": [...], "flags": [...]} or
    {"ok": False, "error": "..."}."""
    from engine.softness import SOFTNESS_TIER

    if league:
        leagues = [league] if league in SOFTNESS_TIER else []
        if not leagues:
            return {"ok": False, "error": f"'{league}' not in whitelisted leagues"}
    else:
        leagues = sorted(SOFTNESS_TIER.keys())

    try:
        from orchestrator import next_season_code
        fx_season = next_season_code("2526")
    except Exception:
        fx_season = "2627"

    results = []
    flags = []

    for lg in leagues:
        try:
            from data.multi_source_concrete import get_fixtures
            data = get_fixtures(lg, fx_season, days_ahead=days)
            pairs = data.get("fixtures", [])
            dates = data.get("dates", {})
            # Filter by search query
            if query:
                q = query.lower()
                pairs = [(h, a) for h, a in pairs
                         if q in h.lower() or q in a.lower() or q in lg.lower()]
            # Narrow to a chosen day when the caller asked for one — the
            # "produce the bet for that day" flow. A fixture whose date we
            # don't know is kept only for the whole-window view (HR35: we
            # never guess a date to keep it).
            if date:
                pairs = [(h, a) for h, a in pairs
                         if dates.get((h, a)) == date]
            fixtures = []
            for h, a in pairs:
                date_str = dates.get((h, a), "")
                fixtures.append({"home": h, "away": a, "date": date_str})
            if fixtures:
                results.append({"name": lg, "fixtures": fixtures})
        except Exception as e:
            flags.append(f"{lg}: fixture search failed — {str(e)[:80]}")

    return {"ok": True, "leagues": results, "flags": flags}


def produce_selection(groups: list[dict], season: str = "2526") -> dict:
    """Produce predictions for user-selected fixtures.

    `groups` = [{"league": str, "fixtures": [{"home", "away", "date"}]}]

    Returns {"ok": True, "board": [...], "flags": [...], "elapsed_s": ...}
    or {"ok": False, "error": "..."}."""
    t0 = time.time()
    board: list = []
    all_flags: list[str] = []
    fixture_dates: dict[tuple[str, str], str] = {}

    # Validate input
    from engine.softness import SOFTNESS_TIER
    total_fixtures = 0
    for g in groups:
        lg = g.get("league", "")
        if lg not in SOFTNESS_TIER:
            return {"ok": False, "error": f"'{lg}' not in whitelisted leagues"}
        for f in g.get("fixtures", []):
            if not f.get("home") or not f.get("away"):
                return {"ok": False, "error": "Each fixture must have home and away team"}
            total_fixtures += 1
            if f.get("date"):
                fixture_dates[(f["home"], f["away"])] = f["date"]
    # The 'Select All' flow can push a full day across all ~17 approved
    # leagues past the old 25 cap — a normal weekend is 30-50 fixtures.
    if total_fixtures > 80:
        return {"ok": False, "error": f"Too many fixtures ({total_fixtures} > 80 limit)"}
    if total_fixtures == 0:
        return {"ok": False, "error": "No fixtures selected"}

    try:
        from brain.store import Brain
        from orchestrator import scan_one_league
        from engine.softness import build_deploy_shortlist
        from webapp import schema as S
        from webapp import render as R
        from output.produce_bet import render_fixture_block

        brain = Brain()
        try:
            for g in groups:
                lg = g["league"]
                pairs = [(f["home"], f["away"]) for f in g.get("fixtures", [])]
                try:
                    slice_, lflags = scan_one_league(
                        lg, season,
                        upcoming_fixtures=pairs,
                        brain=brain, stats={})
                    # Set kickoff dates from the search results
                    for bf in slice_:
                        home_team = bf.probs.home_team if bf.probs else ""
                        away_team = bf.probs.away_team if bf.probs else ""
                        key = (home_team, away_team)
                        if key in fixture_dates and bf.kickoff_date is None:
                            bf.kickoff_date = fixture_dates[key]
                    board += slice_
                    all_flags += lflags
                except Exception as e:
                    all_flags.append(f"{lg}: engine error — {str(e)[:100]}")

            # Try to attach live odds for priced EV (best-effort)
            try:
                import pipeline.odds as odds_mod
                from engine.softness import DEPLOY_ELIGIBLE_TIERS, SOFTNESS_PAUSED, SOFTNESS_TIER
                from run_daily import _retry_transient

                odds_leagues = set()
                for bf in board:
                    if bf.probs is not None:
                        lg = bf.fixture.split(" (")[-1].rstrip(")") if " (" in bf.fixture else ""
                        if SOFTNESS_PAUSED:
                            odds_leagues.add(lg)  # all whitelisted rated fixtures
                        else:
                            if SOFTNESS_TIER.get(lg) in DEPLOY_ELIGIBLE_TIERS:
                                odds_leagues.add(lg)

                odds_index: dict = {}
                for lg in sorted(odds_leagues):
                    try:
                        fixtures, oflags = _retry_transient(
                            lambda lg=lg: odds_mod.fetch_odds(lg),
                            f"{lg} live odds", None)
                        odds_index.update(odds_mod.index_by_fixture(fixtures))
                        all_flags += oflags
                    except Exception:
                        pass  # odds failure is not fatal

                # Apply EV to priced fixtures
                if odds_index:
                    from engine import markets as mkt
                    from engine.consensus import compute_consensus
                    from engine.mes import mes_numeric
                    from engine import recalibration as recal

                    cal = {}
                    try:
                        cal = brain.calibration_by_market()
                    except Exception:
                        pass

                    def _market_implied(market, fx):
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
                        bf.market_probs = mkt.implied_1x2(fx)
                        if bf.market_probs is not None:
                            bf.consensus = compute_consensus(
                                bf.probs, bf.elo_probs, bf.xg_probs, bf.market_probs)
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
                            mp = _market_implied(market, fx)
                            p_ev = mkt.blend_toward_market(
                                recal.apply(raw_p, cal.get(market)), mp)
                            ev = mes_numeric(p_ev, quote.price)
                            if ev is not None and (best is None or ev > best[0]):
                                best = (ev, market, raw_p, quote)
                        if best:
                            ev, market, raw_p, quote = best
                            bf.best_market = mkt.display(market, p.home_team, p.away_team)
                            bf.best_price = quote.price
                            bf.best_bookmaker, bf.best_n_books = quote.bookmaker, quote.n_books
                            bf.best_mes_ev = ev
                            bf.best_model_prob = raw_p
                            bf.best_market_key = market
                            bf.cal_adjustment = cal.get(market, 0.0)
            except Exception as e:
                all_flags.append(f"Odds attach failed — {str(e)[:80]}")

            # Apply deploy pool cap
            shortlisted = [b for b in board if b.on_deploy_shortlist]
            capped = {id(b) for b in build_deploy_shortlist(shortlisted)}
            for b in board:
                if b.on_deploy_shortlist and id(b) not in capped:
                    b.on_deploy_shortlist = False

            # Render results — grouped into the same trust tiers as THE CALL,
            # with the Architect's requested summary at the end of production.
            bd = [S.fixture_to_dict(b) for b in board]
            cards_html = R._tier_grouped_call(bd)
            from engine.softness import SOFTNESS_PAUSED
            if SOFTNESS_PAUSED:
                summary_html = (
                    '<div class="produce-summary">'
                    '<h3>Summary — how to read this production (SOFTNESS PAUSED)</h3>'
                    '<ul>'
                    '<li><b>Today\'s fixtures only</b> (standing rule '
                    '2026-08-09) — the BET is the day\'s slate, nothing else. '
                    'The full 3-day production stays visible as reference.</li>'
                    '<li><b>All whitelisted leagues</b> are deploy-eligible '
                    '(softness PAUSED).</li>'
                    '<li><b>No deploy pool cap</b> — every eligible fixture '
                    'with a pick appears in the CALL.</li>'
                    '<li><b>ID405 market gate</b> still active: away win, '
                    'Over 2.5, and home win stay blocked from capital.</li>'
                    '<li><b>Paper only</b> — Phase 2, zero capital. Nothing '
                    'here is placed; capital opens only at Phase 3 (30 paper '
                    'legs with logged CLV, positive CLV, V7 sign-off) and only '
                    'the Architect deploys.</li>'
                    '</ul>'
                    '<div class="honest-line">Honest edge line: a rigorous '
                    'informed process, NOT a demonstrated profitable edge.</div>'
                    '</div>')
            else:
                summary_html = (
                    '<div class="produce-summary">'
                    '<h3>Summary — how to read this production</h3>'
                    '<ul>'
                    '<li><b>Today\'s fixtures only</b> (standing rule '
                    '2026-08-09) — the BET is the day\'s slate, nothing else.</li>'
                    '<li><b>Tier A &amp; B</b> — deploy-eligible leagues. '
                    'The only leagues that can ever carry capital.</li>'
                    '<li><b>Tier C &amp; D</b> — scan-only: fully predicted, '
                    'never a capital pick.</li>'
                    '<li><b>DEPLOY</b> — this fixture made today\'s deploy pool '
                    '(softness A/B, cap 6).</li>'
                    '<li><b>Paper only</b> — Phase 2, zero capital. Nothing here '
                    'is placed; capital opens only at Phase 3 (30 paper legs with '
                    'logged CLV, positive CLV, V7 sign-off) and only the '
                    'Architect deploys.</li>'
                    '</ul>'
                    '<div class="honest-line">Honest edge line: a rigorous '
                    'informed process, NOT a demonstrated profitable edge.</div>'
                    '</div>')
            rendered_text = "\n\n".join(
                render_fixture_block(b, i) for i, b in enumerate(board, 1))

            return {
                "ok": True,
                "board": bd,
                "cards_html": cards_html,
                "summary_html": summary_html,
                "rendered_text": rendered_text,
                "flags": all_flags,
                "elapsed_s": round(time.time() - t0, 1),
                "n_rated": sum(1 for b in board if b.probs is not None),
                "n_deploy": sum(1 for b in board if b.on_deploy_shortlist),
                "phase": "PHASE 2 · PAPER — preview only, zero capital; "
                         "the daily run owns the board"
            }
        finally:
            brain.close()

    except Exception as e:
        return {"ok": False, "error": f"Engine error: {str(e)[:200]}"}
