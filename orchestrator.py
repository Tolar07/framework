"""
Matchday orchestrator — runs pull -> fit -> scan -> board -> log, end to end,
per the OPERATING PROTOCOL (no stop-and-ask at each step; near-zero deploys is
correct behaviour, not failure).

ID401 (unified pool, 2026-08-10): run_all_leagues() scans every league on the
whitelist (18 leagues incl. Conference League, added 2026-08-10) into ONE
combined board. Every whitelisted league is deploy-eligible — there is no
softness tier, and THE CALL (deploy shortlist) carries no cap: scanning wide
IS the deploy pool.

Usage:
    python orchestrator.py --all --season 2526          # full 18-league scan
    python orchestrator.py --league "Scottish Premiership" --season 2526

Network note: fetching live data requires outbound internet, which this
sandbox does not have. Run this in Claude Code, locally, or on a scheduled
job. Everything downstream of a MatchResult list (engine, verification,
output, CLV) has no network dependency and is fully testable here.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data.football_data_source import (load_league, load_second_division,
                                       MatchResult, UNCOVERED_LEAGUES)
from data import thesportsdb_fixtures as tsdb
from data import api_football_results as apif
from data import xg_source
from data import clubelo_source
from engine import cross_league as xleague
from engine import elo as elo_engine
from engine.consensus import compute_consensus
from engine.dixon_coles import (fit, predict, predict_adjusted,
                                 unrated_reason, FIT_VERSION,
                                 FixtureProbabilities)
from brain.store import (Brain, content_hash, elo_to_payload, elo_from_payload,
                         dc_to_payload, dc_from_payload)
from engine.leagues import (WHITELISTED_LEAGUES, is_deploy_eligible,
                            build_deploy_shortlist)
from engine.mes import trigger_price, mes_numeric
from booking.bridge import load_all_sportybet_fixtures, get_sportybet_odds_for_leg
from verification.id403 import verify, SourcedDatum, Tier
from output.produce_bet import BoardFixture, render_produce_bet
from clv.clv_logger import CLVLog
from config import PHASE_LABEL

# The full ID401 whitelist — the unified pool (engine/leagues.py).
FULL_WHITELIST = list(WHITELISTED_LEAGUES)

# Promoted-club level adjustment (Architect 2026-08-07): a club whose
# parameters were fit ONLY on second-division play is dampened against
# top-flight opposition — its goals came against weaker defences. Conservative
# by design (HR35: better a cautious number than a confident wrong one); the
# exact gap is a modelling judgement, so both scales are named constants.
PROMOTION_SCALE = 0.90          # the promoted side's goal expectancy
PROMOTION_OPPONENT_SCALE = 1.08  # the top-flight side facing the promotion


def next_season_code(season: str) -> str:
    """'2526' -> '2627'. The model is fit on the last COMPLETED season, but
    fixtures come from the one now being played — conflating the two is why a
    finished season yields a permanently empty board."""
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2526', got {season!r}")
    return f"{int(season[:2]) + 1:02d}{int(season[2:]) + 1:02d}"


def previous_season_code(season: str) -> str:
    """'2526' -> '2425'. The season before the one the model is fit on — the
    carry-over fit for promoted clubs reads this (a club relegated after 2425
    and re-promoted for 2627 has no 2526 history, but a full prior-season fit
    still knows it)."""
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2526', got {season!r}")
    return f"{int(season[:2]) - 1:02d}{int(season[2:]) - 1:02d}"


def _unrated_detail(model, home: str, away: str) -> str:
    """Precise, per-side reason a fixture could not be modelled.

    The engine-level `unrated_reason` deliberately does NOT guess whether an
    unknown name is a mapping gap or a genuinely new club — from inside the
    model they look identical. This caller HAS the fitted roster, so it
    resolves the two per-side: a close alias match means the fixtures source
    spells the club differently (a REAL mapping gap worth a TEAM_ALIASES
    entry); no match means the club is genuinely new to the top flight and NO
    alias can rate it — that stays honest NO DATA until it has top-flight
    history. Never guessing a mapping either way is HR35."""
    reasons = []
    for team in (home, away):
        r = unrated_reason(model, team)
        if r is None:
            continue
        if "does not appear in the fitted data at all" in r:
            hits = xleague.suggest_aliases(team, sorted(model.teams))
            if hits:
                cand, score = hits[0]
                r = (f"'{team}' is likely '{cand}' (name similarity {score:.2f}) "
                     f"— a fixtures/results name-mapping gap. Verify and add to "
                     f"TEAM_ALIASES in data/thesportsdb_fixtures.py")
            else:
                r = (f"'{team}' is newly promoted with no top-flight history in "
                     f"the fit window — no alias can rate it. It becomes "
                     f"rateable once it has played enough top-flight matches")
        reasons.append(r)
    return "NO DATA — PENDING: " + "; ".join(reasons)


def _render_unrated_fixtures(league: str,
                             upcoming_fixtures: list[tuple[str, str]],
                             fixture_dates: dict) -> list[BoardFixture]:
    """Fixtures for a league with NO usable history, shown as NO DATA rows.

    The wide-eyes board lists every fixture it finds (HR35: missing data reads
    NO DATA — PENDING, never a guess). A league with fixtures but no history to
    fit on (e.g. the EFL Cup, which has no football-data CSV) must still show
    its matches on the board — dropping them makes a real fixture invisible,
    which is exactly the gap the EFL Cup surfaced. The row is deliberately
    unrated: no probs, no price, an explicit reason."""
    board: list[BoardFixture] = []
    for home, away in upcoming_fixtures:
        v = verify([SourcedDatum(domain="thesportsdb.com",
                                 value=f"{home} v {away}",
                                 url="https://www.thesportsdb.com",
                                 structured=True)])
        board.append(BoardFixture(
            fixture=f"{home} v {away} ({league})",
            probs=None,
            verification=v,
            model_engine="dc",
            on_deploy_shortlist=False,
            mes_trigger_price=None,
            kickoff_date=fixture_dates.get((home, away)),
            elo_probs=None,
            xg_probs=None,
            engine_divergence=None,
            rejection_reason="NO DATA — PENDING: no fitted history for this "
                             "league — fixture listed, not rated",
        ))
    return board


def scan_one_league(league: str, season: str,
                     upcoming_fixtures: list[tuple[str, str]] | None = None,
                     api_football_season: int | None = None,
                     fixtures_season: str | None = None,
                     days_ahead: int = 14,
                     brain: Optional[Brain] = None,
                     stats: Optional[dict] = None
                     ) -> tuple[list[BoardFixture], list[str]]:
    """Returns (board_fixtures_for_this_league, data_flags). Never raises for
    an ordinary data gap (uncovered league, thin history, fetch failure) —
    those become data_flags and an empty board slice, per HR35: a gap is
    reported, not skipped silently and not guessed around.

    `season` is the season the Dixon-Coles model is FIT on (history).
    `fixtures_season` is the season fixtures are pulled from (defaults to the
    season after `season`).
    `days_ahead` is the fixture window in days from today (0 = today's matches
    only). The daily board runs today-only; tooling that plans ahead keeps the
    14-day default."""
    flags: list[str] = []
    fixture_dates: dict[tuple[str, str], str] = {}

    # football-data.co.uk carries no continental competitions and no Croatia.
    # API-Football fills that gap for HISTORY (ratified 2026-08-03), but a
    # continental competition still cannot be fitted as a standalone league —
    # see api_football_results.is_cross_league for why.
    fallback_history = None
    cross_model = None
    pooled = None  # the cross-league pool — built ONCE, reused for fit + Elo
    if league in UNCOVERED_LEAGUES:
        if apif.is_cross_league(league):
            # Fitted on the pooled European graph — domestic results plus the
            # league phases of all three continental competitions, which are
            # what put clubs from different leagues on one scale.
            try:
                pooled, pool_info, xflags = xleague.build_pool(league)
                flags += xflags
                if stats is not None:
                    stats["pool_built"] = True
                pool_hash = content_hash(pooled, salt=f"cross:{league}:{season}")
                row = brain.load_model_state(f"cross:{league}") if brain else None
                if row is not None and row["content_hash"] == pool_hash:
                    # Same rows + same config -> provably identical fit (BUG6
                    # reproducibility). Reuse the cached parameters verbatim.
                    cross_model = dc_from_payload(row["payload"])
                    cross_model.league = league
                    if stats is not None:
                        stats["dc_reused"] = True
                else:
                    cross_model, _info, fit_flags = xleague.fit_cross_league(
                        league, pool=(pooled, pool_info))
                    flags += fit_flags
                    if cross_model is None:
                        return [], flags
                    if brain:
                        brain.save_model_state(
                            f"cross:{league}", "cross", FIT_VERSION, pool_hash,
                            cross_model.n_matches_fit,
                            min(r.date for r in pooled),
                            max(r.date for r in pooled),
                            dc_to_payload(cross_model))
                    if stats is not None:
                        stats["dc_refit"] = True
            except Exception as e:
                flags.append(f"{league}: cross-league fit failed ({str(e)[:70]}) "
                             f"— NO DATA — PENDING")
                return [], flags
        else:
            try:
                fallback_history, hflags = apif.load_results(league)
                flags += hflags
                if len(fallback_history) < 20:
                    flags.append(f"{league}: fallback history too thin "
                                 f"({len(fallback_history)}) — NO DATA — PENDING")
                    fallback_history = None
            except Exception as e:
                flags.append(f"{league}: NO DATA — PENDING (no history source: {e})")
                # Fall through to the fixture scan (2026-08-10): a league with
                # no usable history (e.g. the EFL Cup) must still have its
                # FIXTURES listed as NO DATA rows (HR35 wide-eyes). Early
                # returning here dropped a real fixture (Plymouth v Exeter on
                # 2026-08-10) that the SportyBet cache carried — the history
                # gap must never make a real fixture invisible.
                fallback_history = None

    if upcoming_fixtures is None:
        fx_season = fixtures_season or next_season_code(season)
        # Multi-source fixtures failover (data/multi_source_concrete.py):
        # TheSportsDB (season feed, then eventsday for today-only) -> odds-derived
        # fixtures -> API-Football (paid plan). Each provider is tried in priority
        # order with circuit breakers; the first that returns fixtures wins. This
        # replaces the hand-rolled try-chain so one provider going down degrades
        # to the next source instead of an immediate NO DATA (HR35: a real gap is
        # still reported, never guessed). Kickoff dates ride along so a logged
        # leg can be settled against THIS match, not a same-pairing prior-season
        # fixture.
        from data.multi_source_concrete import get_fixtures
        errors: list[str] = []
        upcoming_fixtures = []
        try:
            fx = get_fixtures(league, fx_season, days_ahead=days_ahead,
                              api_football_season=api_football_season)
            upcoming_fixtures = fx.get("fixtures") or []
            fixture_dates.update(fx.get("dates") or {})
            src = fx.get("source", "?")
            if fx.get("skipped"):
                flags.append(f"{league}: {fx['skipped']} fixture rows "
                             f"skipped/malformed")
            if src != "thesportsdb":
                # The primary source is the default; any backup provider that
                # had to be used is worth a line so the board is honest about
                # which source produced today's fixtures.
                flags.append(f"{league}: fixtures via {src}")
        except Exception as e:
            errors.append(f"multi-source fixtures: {e}")

        if not upcoming_fixtures:
            detail = " | ".join(errors) if errors else "no fixtures in window"
            flags.append(f"{league}: no upcoming fixtures ({detail}) — NO DATA — PENDING")
            # SportyBet cached-fixture fallback: the Playwright cache builder
            # navigates the real SportyBet league pages, so its fixtures are a
            # genuine, independently-captured source — not a guess (HR35). A
            # fresh cache fills the board when every other provider is down
            # (e.g. API-Football season lock + Odds API quota), keeping wide
            # eyes without spending a single paid credit. Odds ride along in
            # the cache, so SportyBet MES still populates.
            try:
                from booking.bridge import (load_sportybet_fixtures,
                                            sportybet_fixtures_to_pairs)
                # Use generous max_age_hours (48h) on fallback — the
                # cache builder runs twice daily; when it's the ONLY
                # source we should be lenient rather than lose fixtures.
                sb_pairs = sportybet_fixtures_to_pairs(
                    league, days_ahead=45, max_age_hours=48)
                if sb_pairs:
                    upcoming_fixtures = sb_pairs
                    for f in load_sportybet_fixtures(
                            league, days_ahead=45, max_age_hours=48):
                        if f.kickoff_utc:
                            fixture_dates[(f.home_team, f.away_team)] = \
                                f.kickoff_utc[:10]
                    flags.append(
                        f"{league}: fixtures via SportyBet cache "
                        f"({len(sb_pairs)} — primary sources failed)")
            except Exception:
                pass  # a missing cache/fault is a miss, not a new error

    if cross_model is not None:
        results, skipped = [], []
    elif fallback_history is not None:
        results, skipped = fallback_history, []
    else:
        try:
            results, skipped = load_league(league, season)
        except Exception as e:
            # football-data doesn't carry this league (HNL, continental comps) —
            # fall back to the results multi-source (API-Football -> TheSportsDB
            # single-source T2) before declaring NO DATA. The fallback stamps its
            # own source on each MatchResult, so the board stays honest about it.
            try:
                from data.multi_source_concrete import get_historical_results
                results = get_historical_results(league, season)
                skipped = []
                flags.append(f"{league}: history via multi-source "
                             f"({results[0].source if results else '?'})")
            except Exception:
                flags.append(f"{league}: results fetch failed ({e}) — "
                             f"NO DATA — PENDING")
                # No history to rate on, but the league's FIXTURES still belong
                # on the board as NO DATA rows (HR35 wide-eyes) — never silently
                # dropped.
                return _render_unrated_fixtures(
                    league, upcoming_fixtures, fixture_dates), flags

    if skipped:
        flags.append(f"{league}: {len(skipped)} source rows skipped/malformed")

    if cross_model is None and len(results) < 20:
        flags.append(f"{league}: insufficient match history ({len(results)} results) "
                      f"— NO DATA — PENDING rather than a thin fit")
        # No history to fit on — fixtures still belong on the board as NO DATA
        # rows (HR35 wide-eyes), never silently dropped.
        return _render_unrated_fixtures(
            league, upcoming_fixtures, fixture_dates), flags

    # Dixon-Coles: reuse the brain's cached fit ONLY when the training rows are
    # provably identical (same content hash + same fit config). Otherwise refit.
    # This is reuse, not approximation — the identical-fit guarantee (BUG6)
    # means the cached params ARE what a fresh fit would produce.
    if cross_model is not None:
        model = cross_model
    else:
        dc_hash = content_hash(results, salt=f"dc:{league}:{season}")
        row = brain.load_model_state(f"dc:{league}") if brain else None
        if row is not None and row["content_hash"] == dc_hash:
            model = dc_from_payload(row["payload"])
            if stats is not None:
                stats["dc_reused"] = True
        else:
            model = fit(results)
            if brain:
                brain.save_model_state(
                    f"dc:{league}", "dc", FIT_VERSION, dc_hash,
                    model.n_matches_fit,
                    min(r.date for r in results), max(r.date for r in results),
                    dc_to_payload(model))
            if stats is not None:
                stats["dc_refit"] = True

    # Promoted-club carry-over (Architect 2026-08-07): a secondary model fit on
    # the PREVIOUS completed season, used ONLY to rate a fixture the primary
    # model cannot (a club relegated after the prior season and re-promoted for
    # this one has no history in the primary fit window). The primary model is
    # untouched, so its recency and calibration baseline are preserved — a full
    # two-season fit would dilute form for EVERY team; carry-over only widens
    # coverage where the primary has nothing. The carry-over model is a real DC
    # fit on real prior-season data, never a guess; a fixture rated through it
    # is flagged on the board so it is visibly distinct from a primary rating.
    carry_model = None
    carry_flags: list[str] = []
    clubelo_flags: list[str] = []
    carry_promoted: set[str] = set()  # teams known ONLY from 2nd-division rows
    if cross_model is None:
        try:
            carry_season = previous_season_code(season)
            carry_results, _ = load_league(league, carry_season)
            # Second-division history for promoted clubs (Architect 2026-08-07).
            # A club promoted to the top flight has no top-flight history in
            # the carry window; its second-division season is real data that
            # rates it. A team present ONLY in the second-division rows is a
            # promotion — recorded so the level adjustment applies at predict
            # time. Leagues whose second division football-data no longer
            # publishes return ([], []) and simply keep the current coverage.
            sec_results, _ = load_second_division(league, carry_season)
            if sec_results:
                top_flight = ({r.home_team for r in carry_results}
                              | {r.away_team for r in carry_results})
                sec_teams = ({r.home_team for r in sec_results}
                             | {r.away_team for r in sec_results})
                carry_promoted = sec_teams - top_flight
                carry_results = carry_results + sec_results
            carry_hash = content_hash(
                carry_results, salt=f"dc:{league}:carry:{carry_season}")
            row = brain.load_model_state(f"dc:{league}:carry") if brain else None
            if row is not None and row["content_hash"] == carry_hash:
                carry_model = dc_from_payload(row["payload"])
            else:
                carry_model = fit(carry_results)
                if brain:
                    try:
                        brain.save_model_state(
                            f"dc:{league}:carry", "dc", FIT_VERSION, carry_hash,
                            carry_model.n_matches_fit,
                            min(r.date for r in carry_results),
                            max(r.date for r in carry_results),
                            dc_to_payload(carry_model))
                    except Exception:
                        pass  # a cache-write failure is not a rating failure
        except Exception:
            # A missing prior-season CSV, a network blip — the board simply
            # has no carry-over; HR35 keeps the NO DATA row. Not an error.
            carry_model = None

    # Second engine (ID82 Elo, ratified 2026-08-04). Built from the SAME match
    # history the goals model was fitted on, so the two are reading identical
    # evidence through different mathematics — which is what makes their
    # disagreement meaningful rather than an artefact of different inputs.
    # Incremental when the brain holds a snapshot: rate_through(seed_from=...)
    # consumes only matches strictly newer than the snapshot's last_date and
    # skips burn-in (already burned in on the snapshot).
    elo_source = results if cross_model is None else pooled
    # Phase 3.2 — the cross-league ELO blend weight. A continental club's 38
    # domestic matches would otherwise speak exactly as loudly as its 8
    # European ones when a continental fixture is priced, which is how a
    # weak-league dominant gets rated above a strong-league club (the pool's
    # own calibration caveat). The optimiser (xleague.fit_blend_weight) finds
    # the weight on continental matches relative to domestic that minimises
    # out-of-sample Brier on the pooled continental record, and leaves the
    # weight at 1.0 unless that is provably beaten. Cached on the pooled
    # content-hash so it is fitted once, not on every daily run.
    elo_weight = 1.0
    blend_flags: list[str] = []
    if cross_model is not None:
        try:
            blend_hash = content_hash(pooled, salt=f"blend:{league}:{season}")
            brow = brain.load_model_state(f"blend:{league}") if brain else None
            if brow is not None and brow["content_hash"] == blend_hash:
                elo_weight = float(brow["payload"].get("w", 1.0))
                if elo_weight != 1.0:
                    blend_flags.append(f"{league}: Elo continental blend "
                                       f"w={elo_weight} (cached)")
            else:
                elo_weight, b_info = xleague.fit_blend_weight(pooled)
                if b_info.get("flag"):
                    blend_flags.append(b_info["flag"])
                if brain:
                    brain.save_model_state(
                        f"blend:{league}", "blend", 1, blend_hash,
                        b_info.get("n_scored", 0),
                        min(r.date for r in pooled),
                        max(r.date for r in pooled),
                        {"w": elo_weight, "applied": b_info.get("applied", False),
                         "brier_w1": b_info.get("brier_w1"),
                         "brier_best": b_info.get("brier_best"),
                         "n_scored": b_info.get("n_scored", 0)})
        except Exception as e:
            blend_flags.append(f"{league}: Elo blend fit failed "
                               f"({str(e)[:60]}) — weight left at 1.0")
            elo_weight = 1.0

    elo_model = None
    try:
        elo_row = brain.load_model_state(f"elo:{league}") if brain else None
        seed = elo_from_payload(elo_row["payload"]) if elo_row else None
        mw = xleague.continental_weight(elo_weight) if elo_weight != 1.0 else None
        elo_model = elo_engine.rate_through(elo_source, seed_from=seed,
                                            match_weight=mw)
        if stats is not None:
            stats["elo_seeded"] = bool(seed)
        if elo_model is not None and brain:
            salt = f"elo:{league}:{season}"
            if elo_weight != 1.0:
                salt += f":w{elo_weight}"  # a changed weight forces a refit
            brain.save_model_state(
                f"elo:{league}", "elo", elo_engine.STATE_VERSION,
                content_hash(elo_source, salt=salt),
                elo_model.n_matches, elo_model.last_date, None,
                elo_to_payload(elo_model))
    except Exception as e:
        elo_model = None
        flags.append(f"{league}: Elo second opinion unavailable ({str(e)[:60]})")
    flags += blend_flags

    # Third engine: xG (expected goals) via Understat. FREE source, covers the
    # Big-5 leagues + RFPL only. Quality-adjusted signal — reads the quality of
    # chances, not the goals they produced. A genuinely independent third
    # reading (score patterns / result history / chance quality). Falls back
    # silently when a league isn't covered — the board omits the xG line, DC
    # and Elo still work (HR35: never fabricate xG).
    xg_ratings = None
    xg_probs = None
    if xg_source.is_covered(league):
        try:
            xg_ratings = xg_source.fit_xg(league, season)
            if xg_ratings and stats is not None:
                stats["xg_leagues"] = True
        except Exception as e:
            flags.append(f"{league}: xG third opinion unavailable "
                         f"({str(e)[:60]})")
    board: list[BoardFixture] = []

    for home, away in upcoming_fixtures:
        probs = predict(model, home, away)
        # Promoted-club fallback: the primary 2526 fit has no history for a
        # re-promoted club, but the prior-season carry-over model does. The
        # rating is real (a DC fit on real data), and it is named on the board
        # so it is never mistaken for a primary-window rating. If BOTH fail the
        # row stays NO DATA — PENDING (HR35 unchanged).
        carry_rated = False
        if probs is None and carry_model is not None:
            if home in carry_promoted or away in carry_promoted:
                # Promoted-club level adjustment: the club's parameters were
                # fit on second-division play, so its goal expectancy is
                # dampened and the top-flight side's boosted before the matrix
                # is built (predict_adjusted — never a guess, HR35).
                carry_p = predict_adjusted(
                    carry_model, home, away,
                    scale_home=(PROMOTION_SCALE if home in carry_promoted
                                else PROMOTION_OPPONENT_SCALE),
                    scale_away=(PROMOTION_SCALE if away in carry_promoted
                                else PROMOTION_OPPONENT_SCALE))
            else:
                carry_p = predict(carry_model, home, away)
            if carry_p is not None:
                probs = carry_p
                carry_rated = True
                carry_flags.append(f"{home} v {away}")
        # rating_source provenance: None = primary DC fit, "carry" = prior-
        # season carry-over fit (promoted clubs), "clubelo" = ClubElo stretch.
        # The board labels the source so a stretch rating is never mistaken
        # for a fitted one (Architect 2026-08-12, bookable + labeled).
        rating_source = "carry" if carry_rated else None
        # ClubElo stretch fallback: a keyless current-season Elo snapshot is a
        # real rating (ID414 — a seed IS a rating), so a fixture neither the
        # primary fit nor the carry-over model covers is still rated rather
        # than left NO DATA. Both clubs must carry a real ClubElo value (HR35:
        # a missing side keeps the row NO DATA — PENDING). Only its 1X2
        # probabilities count — goals markets stay None, so a stretch-rated
        # fixture is never priced on a goals market it has no opinion on.
        if probs is None:
            cl_h = clubelo_source.elo_for(home)
            cl_a = clubelo_source.elo_for(away)
            if cl_h is not None and cl_a is not None:
                cl_p = elo_engine.EloModel(
                    ratings={home: cl_h, away: cl_a}).probabilities(home, away)
                if cl_p is not None:
                    ph, pd, pa = cl_p
                    probs = FixtureProbabilities(
                        home_team=home, away_team=away,
                        lambda_home=0.0, lambda_away=0.0,
                        p_home=ph, p_draw=pd, p_away=pa,
                        modal_scoreline=(0, 0))
                    rating_source = "clubelo"
                    clubelo_flags.append(f"{home} v {away}")
        # The fixture itself comes from TheSportsDB (ratified T2), so that's
        # what gets stamped — crediting football-data.co.uk here would claim a
        # corroboration that didn't happen. One source => ○ SINGLE-SOURCE.
        v = verify([SourcedDatum(domain="thesportsdb.com",
                                  value=f"{home} v {away}",
                                  url="https://www.thesportsdb.com",
                                  structured=True)])
        elo_p = elo_model.probabilities(home, away) if elo_model else None
        xg_p = (xg_source.predict_xg(home, away, xg_ratings, league=league)
                if xg_ratings else None)
        xg_t = (xg_p.home, xg_p.draw, xg_p.away) if xg_p else None
        # Phase 3.4: xG's goals-market read (O1.5/O2.5/O3.5/BTTS) from the SAME
        # prediction as xg_t — chance quality on the goals markets, not just
        # 1X2. DC's goals markets stay canonical for what is logged; this is
        # the independent second opinion shown beside them, never blended.
        xg_goals = (xg_p.over15, xg_p.over25, xg_p.over35, xg_p.btts) \
            if xg_p else None
        mes = None
        if probs is not None:
            # A STRETCH 1X2-only rating (ClubElo fallback) has no goals
            # opinion — p_over_15 is None, so the goals markets contribute
            # nothing to best_prob rather than crashing (HR35).
            over15 = probs.p_over_15
            best_prob = max(probs.p_home, probs.p_draw, probs.p_away,
                            over15 if over15 is not None else 0.0,
                            1 - over15 if over15 is not None else 0.0)
            mes = trigger_price(best_prob)

        # Fetch SportyBet odds for this fixture to compute actual MES and enable CLV.
        # get_sportybet_odds_for_leg matches on MODEL keys (PipelineFixture
        # home_team/away_team), so we pass `home`/`away` directly — resolving to
        # the SportyBet spelling first would silently fail every fixture whose
        # bookmaker name differs from the model key.
        sb_odds = None
        sb_mes = None
        if probs is not None:
            for market_key, prob_attr in [("1X2_HOME", "p_home"), ("1X2_DRAW", "p_draw"), ("1X2_AWAY", "p_away")]:
                market_prob = getattr(probs, prob_attr)
                if market_prob:
                    sb_price = get_sportybet_odds_for_leg(home, away, league, market_key)
                    if sb_price:
                        sb_mes_val = mes_numeric(market_prob, sb_price)
                        if sb_mes is None or (sb_mes_val is not None and sb_mes_val > sb_mes):
                            sb_mes = sb_mes_val
                        if sb_odds is None:
                            sb_odds = {"home": None, "draw": None, "away": None}
                        if market_key == "1X2_HOME":
                            sb_odds["home"] = sb_price
                        elif market_key == "1X2_DRAW":
                            sb_odds["draw"] = sb_price
                        elif market_key == "1X2_AWAY":
                            sb_odds["away"] = sb_price

        board.append(BoardFixture(
            fixture=f"{home} v {away} ({league})",
            probs=probs,
            verification=v,
            model_engine="cross" if cross_model is not None else "dc",
            on_deploy_shortlist=(probs is not None and is_deploy_eligible(league)
                                  and v.tier not in (Tier.CONFLICT, Tier.NO_DATA)),
            mes_trigger_price=mes,
            kickoff_date=fixture_dates.get((home, away)),
            elo_probs=elo_p,
            xg_probs=xg_t,
            # Phase 3.4: xG goals read + DC-vs-xG goals divergence (display
            # only — never changes what is logged).
            xg_goals=xg_goals,
            goals_divergence=(xg_source.goals_divergence(probs, xg_p)
                              if (probs is not None and xg_p is not None)
                              else None),
            # ID412: majority vote across whatever engines priced the fixture.
            # Pure display + brain data — never changes what is logged. Only
            # for a RATED fixture (DC must have an opinion for a consensus to
            # mean anything); unrated fixtures stay NO DATA — PENDING.
            consensus=compute_consensus(probs, elo_p, xg_t) if probs else None,
            engine_divergence=elo_engine.divergence(elo_p, probs),
            rejection_reason=(
                # Unrated: honest NO DATA reason. Every whitelisted league is
                # deploy-eligible in the unified pool (2026-08-10), so a RATED
                # fixture is never rejected on league eligibility.
                _unrated_detail(model, home, away) if probs is None
                else None
            ),
            # Provenance: None=DC fit, "carry"=carry-over, "clubelo"=stretch.
            # The board labels it so a stretch rating is never mistaken for a
            # fitted one (bookable, labeled — Architect 2026-08-12).
            rating_source=rating_source,
            # SportyBet odds and MES
            sb_home_odds=sb_odds.get("home") if sb_odds else None,
            sb_draw_odds=sb_odds.get("draw") if sb_odds else None,
            sb_away_odds=sb_odds.get("away") if sb_odds else None,
            sb_mes_ev=sb_mes,
        ))

    if carry_flags:
        flags.append(f"{league}: {len(carry_flags)} fixture(s) rated on the "
                     f"previous season's carry-over model (promoted clubs): "
                     f"{', '.join(carry_flags)}")

    if clubelo_flags:
        flags.append(f"{league}: {len(clubelo_flags)} fixture(s) rated on the "
                     f"ClubElo stretch fallback (keyless current-season Elo): "
                     f"{', '.join(clubelo_flags)}")

    # Surface unmapped names ONCE per league, with the model's actual roster
    # beside them. A naming mismatch and a genuinely new club are
    # indistinguishable from inside the model, but obvious to a human the
    # moment the two lists sit next to each other. Teams a fixture was
    # successfully rated through the carry-over model or the ClubElo stretch
    # are excluded — they are not unmapped, they were rated on real data.
    carry_teams = {t for fx in carry_flags for t in fx.split(" v ")}
    clubelo_teams = {t for fx in clubelo_flags for t in fx.split(" v ")}
    unmapped = sorted({t for h, a in upcoming_fixtures for t in (h, a)
                       if t not in model.teams and t not in model.thin_teams
                       and t not in carry_teams and t not in clubelo_teams})
    if unmapped:
        # Suggest likely pool matches for each unknown name (read-only — a human
        # verifies and adds to the alias tables; never auto-applied, HR35).
        suggestions = []
        for t in unmapped:
            hits = xleague.suggest_aliases(t, sorted(model.teams))
            suggestions.append(
                f"{t} -> {hits[0][0]} ({hits[0][1]:.2f})" if hits
                else f"{t} -> no close match in the model pool")
        flags.append(
            f"{league}: {len(unmapped)} team name(s) in the fixtures feed not found "
            f"in the fitted data — {', '.join(unmapped)}. Suggestions: "
            f"{'; '.join(suggestions)}. If a suggestion is right, verify and add "
            f"it to TEAM_ALIASES in data/thesportsdb_fixtures.py (or "
            f"CONTINENTAL_ALIASES in engine/cross_league.py); if it is newly "
            f"promoted, it correctly has no rating yet.")

    return board, flags


def run_all_leagues(season: str = "2526", leagues: list[str] | None = None,
                     fixtures_season: str | None = None):
    """Scans every whitelisted league into ONE combined board. This is the
    'wide eyes' half of ID402 — every league on the list gets scanned every
    run, whether or not its season has started, whether or not it's deploy-
    eligible. Leagues with no data this week simply show as NO DATA — PENDING
    rather than being silently dropped from the run."""
    leagues = leagues or FULL_WHITELIST
    fixtures_season = fixtures_season or next_season_code(season)
    combined_board: list[BoardFixture] = []
    all_flags: list[str] = []

    print(f"Fitting on season {season}; pulling fixtures for season {fixtures_season}")
    if tsdb.using_test_key():
        all_flags.append(
            "THESPORTSDB_KEY not set — running on TheSportsDB's shared public "
            "test key (rate-limited, truncated directory). Register free at "
            "thesportsdb.com/register.php and set THESPORTSDB_KEY."
        )
    for league in leagues:
        print(f"Scanning {league}...")
        board_slice, flags = scan_one_league(league, season,
                                              fixtures_season=fixtures_season)
        combined_board.extend(board_slice)
        all_flags.extend(flags)

    # Global ID402 pool cap — 6 total across ALL leagues combined, not 6 per league.
    shortlisted = [b for b in combined_board if b.on_deploy_shortlist]
    capped_ids = set(id(b) for b in build_deploy_shortlist(shortlisted))
    for b in combined_board:
        if b.on_deploy_shortlist and id(b) not in capped_ids:
            b.on_deploy_shortlist = False

    clv = CLVLog()
    status = clv.phase2_status()

    output = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL,
        leagues_scanned=leagues,
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"],
        data_flags=all_flags,
        board=combined_board,
    )
    print("\n" + "=" * 60 + "\n")
    print(output)
    return output


def run(league: str, season: str, upcoming_fixtures: list[tuple[str, str]] | None = None,
        api_football_season: int | None = None, fixtures_season: str | None = None):
    """Single-league entry point — kept for the earlier smoke-test workflow
    and for ad-hoc single-league checks. run_all_leagues() is the real daily
    driver now."""
    board, flags = scan_one_league(league, season, upcoming_fixtures,
                                    api_football_season, fixtures_season)
    if not board and flags:
        print("\n".join(flags))
        return

    clv = CLVLog()
    status = clv.phase2_status()
    output = render_produce_bet(
        mode="Mode A", phase=PHASE_LABEL,
        leagues_scanned=[league],
        calibration_count=status["legs_with_clv"],
        mean_clv=status["mean_clv_pct"],
        data_flags=flags,
        board=board,
    )
    print("\n" + "=" * 60 + "\n")
    print(output)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="scan the full 18-league ID401 whitelist")
    ap.add_argument("--league", default="Scottish Premiership")
    ap.add_argument("--season", default="2526",
                     help="season the model is FIT on (last completed season)")
    ap.add_argument("--fixtures-season", default=None,
                     help="season fixtures are pulled from (default: the season after --season)")
    args = ap.parse_args()

    if args.all:
        run_all_leagues(season=args.season, fixtures_season=args.fixtures_season)
    else:
        run(args.league, args.season, fixtures_season=args.fixtures_season)
