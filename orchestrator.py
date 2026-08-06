"""
Matchday orchestrator — runs pull -> fit -> scan -> board -> log, end to end,
per the OPERATING PROTOCOL (no stop-and-ask at each step; near-zero deploys is
correct behaviour, not failure).

ID402 "wide eyes, narrow hands": run_all_leagues() scans every league on the
ID401 whitelist (15 leagues) into ONE combined board. THE CALL (deploy
shortlist) still only ever draws from softness A/B and is capped at 6 total
across ALL leagues combined — scanning wide never widens the deploy pool.

Usage:
    python orchestrator.py --all --season 2526          # full 15-league scan
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

from data.football_data_source import load_league, MatchResult, UNCOVERED_LEAGUES
from data import thesportsdb_fixtures as tsdb
from data import api_football_results as apif
from data import xg_source
from engine import cross_league as xleague
from engine import elo as elo_engine
from engine.consensus import compute_consensus
from engine.dixon_coles import fit, predict, unrated_reason, FIT_VERSION
from brain.store import (Brain, content_hash, elo_to_payload, elo_from_payload,
                         dc_to_payload, dc_from_payload)
from engine.softness import (SOFTNESS_TIER, softness_tier, is_deploy_eligible,
                              build_deploy_shortlist)
from engine.mes import trigger_price
from verification.id403 import verify, SourcedDatum, Tier
from output.produce_bet import BoardFixture, render_produce_bet
from clv.clv_logger import CLVLog
from config import PHASE_LABEL

# The full ID401 whitelist (15 leagues) — same set engine/softness.py tiers.
FULL_WHITELIST = list(SOFTNESS_TIER.keys())


def next_season_code(season: str) -> str:
    """'2526' -> '2627'. The model is fit on the last COMPLETED season, but
    fixtures come from the one now being played — conflating the two is why a
    finished season yields a permanently empty board."""
    if len(season) != 4 or not season.isdigit():
        raise ValueError(f"Season code must be 4 digits like '2526', got {season!r}")
    return f"{int(season[:2]) + 1:02d}{int(season[2:]) + 1:02d}"


def _unrated_detail(model, home: str, away: str) -> str:
    """Precise, per-side reason a fixture could not be modelled."""
    reasons = [r for r in (unrated_reason(model, home), unrated_reason(model, away))
               if r]
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
            softness_tier=softness_tier(league),
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
                    return [], flags
            except Exception as e:
                flags.append(f"{league}: NO DATA — PENDING (no history source: {e})")
                return [], flags

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

    if cross_model is not None:
        results, skipped = [], []
    elif fallback_history is not None:
        results, skipped = fallback_history, []
    else:
        try:
            results, skipped = load_league(league, season)
        except Exception as e:
            flags.append(f"{league}: results fetch failed ({e}) — NO DATA — PENDING")
            # No history to rate on, but the league's FIXTURES still belong on
            # the board as NO DATA rows (HR35 wide-eyes) — not silently dropped.
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

    # Second engine (ID82 Elo, ratified 2026-08-04). Built from the SAME match
    # history the goals model was fitted on, so the two are reading identical
    # evidence through different mathematics — which is what makes their
    # disagreement meaningful rather than an artefact of different inputs.
    # Incremental when the brain holds a snapshot: rate_through(seed_from=...)
    # consumes only matches strictly newer than the snapshot's last_date and
    # skips burn-in (already burned in on the snapshot).
    elo_source = results if cross_model is None else pooled
    elo_model = None
    try:
        elo_row = brain.load_model_state(f"elo:{league}") if brain else None
        seed = elo_from_payload(elo_row["payload"]) if elo_row else None
        elo_model = elo_engine.rate_through(elo_source, seed_from=seed)
        if stats is not None:
            stats["elo_seeded"] = bool(seed)
        if elo_model is not None and brain:
            brain.save_model_state(
                f"elo:{league}", "elo", elo_engine.STATE_VERSION,
                content_hash(elo_source, salt=f"elo:{league}:{season}"),
                elo_model.n_matches, elo_model.last_date, None,
                elo_to_payload(elo_model))
    except Exception as e:
        elo_model = None
        flags.append(f"{league}: Elo second opinion unavailable ({str(e)[:60]})")

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
    tier = softness_tier(league)
    board: list[BoardFixture] = []

    for home, away in upcoming_fixtures:
        probs = predict(model, home, away)
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
        mes = None
        if probs is not None:
            best_prob = max(probs.p_home, probs.p_draw, probs.p_away,
                             probs.p_over_15, 1 - probs.p_over_15)
            mes = trigger_price(best_prob)

        board.append(BoardFixture(
            fixture=f"{home} v {away} ({league})",
            probs=probs,
            verification=v,
            softness_tier=tier,
            model_engine="cross" if cross_model is not None else "dc",
            on_deploy_shortlist=(probs is not None and is_deploy_eligible(league)
                                  and v.tier not in (Tier.CONFLICT, Tier.NO_DATA)),
            mes_trigger_price=mes,
            kickoff_date=fixture_dates.get((home, away)),
            elo_probs=elo_p,
            xg_probs=xg_t,
            # ID412: majority vote across whatever engines priced the fixture.
            # Pure display + brain data — never changes what is logged. Only
            # for a RATED fixture (DC must have an opinion for a consensus to
            # mean anything); unrated fixtures stay NO DATA — PENDING.
            consensus=compute_consensus(probs, elo_p, xg_t) if probs else None,
            engine_divergence=elo_engine.divergence(elo_p, probs),
            rejection_reason=(
                _unrated_detail(model, home, away) if probs is None
                else None if is_deploy_eligible(league)
                else f"softness tier {tier} — scan-only"
            ),
        ))

    # Surface unmapped names ONCE per league, with the model's actual roster
    # beside them. A naming mismatch and a genuinely new club are
    # indistinguishable from inside the model, but obvious to a human the
    # moment the two lists sit next to each other.
    unmapped = sorted({t for h, a in upcoming_fixtures for t in (h, a)
                       if t not in model.teams and t not in model.thin_teams})
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
    ap.add_argument("--all", action="store_true", help="scan the full 15-league ID401 whitelist")
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
