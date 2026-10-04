"""
Matchday orchestrator — runs pull -> fit -> scan -> board -> log, end to end,
per the OPERATING PROTOCOL (no stop-and-ask at each step; near-zero deploys is
correct behaviour, not failure).

ID402 "wide eyes, narrow hands": run_all_leagues() scans every league on the
ID401 whitelist (15 leagues) into ONE combined board. THE CALL (deploy
shortlist) is ranked by model conviction and capped at 6 total across ALL
leagues combined — scanning wide never widens the deploy pool. (Softness
tiering was retired 2026-09-30; every whitelisted league is equally eligible.)

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
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data.football_data_source import load_league, MatchResult, UNCOVERED_LEAGUES
from data.fixtures_source import fetch_upcoming, as_pairs
from data import international_source as intl
from data import thesportsdb_fixtures as tsdb
from data import api_football_results as apif
from engine import cross_league as xleague
from engine import elo as elo_engine
from engine.dixon_coles import fit, predict, unrated_reason
from engine import name_match
from engine.slate import (WHITELIST_LEAGUES, is_deploy_eligible,
                          build_deploy_shortlist)
from engine.mes import trigger_price
from verification.id403 import verify, SourcedDatum, Tier
from output.produce_bet import BoardFixture, render_produce_bet
from clv.clv_logger import CLVLog
from config import PHASE_LABEL

# The full ID401 whitelist (15 leagues), all now equally deploy-eligible.
FULL_WHITELIST = list(WHITELIST_LEAGUES)

# Domestic models fit on last season + the current season, exponentially
# weighted to recent matches (backtest/RECENCY_STUDY.md: 240 days beat 120 and
# the last-season-only model on accuracy, coverage and market agreement).
RECENCY_HALF_LIFE_DAYS = 240.0
RECENCY_MAX_MATCHES = 800


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


# Competitions with no single-league history to fit (a cup mixing every tier).
# Every fixture is priced MARKET-IMPLIED from SportyBet (engine.market_implied).
MARKET_ONLY_LEAGUES = {"FA Cup"}


def _odds_by_pair(league: str) -> tuple[dict, list[str]]:
    """{(home, away): FixtureOdds} from the live odds chain, for market-implied
    pricing. Empty on any failure (the caller keeps NO DATA, never a guess)."""
    try:
        import pipeline.odds as _odds
        quotes, oflags = _odds.fetch_odds_chained(league)
        return {(q.home_team, q.away_team): q for q in quotes}, oflags
    except Exception as e:  # noqa: BLE001
        return {}, [f"{league}: odds unavailable for market-implied pricing ({e})"]


def _market_board(league: str, pairs, dates: dict, odds: dict
                  ) -> tuple[list[BoardFixture], int]:
    """BoardFixtures priced market-implied. Returns (board, n_priced)."""
    from engine.market_implied import implied_probs
    board, n = [], 0
    for home, away in pairs:
        probs = implied_probs(odds.get((home, away)))
        v = verify([SourcedDatum(domain="sportybet.com", value=f"{home} v {away}",
                                 url="https://www.sportybet.com", structured=True)])
        n += probs is not None
        board.append(BoardFixture(
            fixture=f"{home} v {away} ({league})", probs=probs, verification=v,
            on_deploy_shortlist=(probs is not None and is_deploy_eligible(league)),
            kickoff_date=dates.get((home, away)), prob_source="market",
            rejection_reason=(None if probs is not None else
                              "NO DATA — PENDING: core markets not all priced on SportyBet"),
        ))
    return board, n


def scan_one_league(league: str, season: str,
                     upcoming_fixtures: list[tuple[str, str]] | None = None,
                     api_football_season: int | None = None,
                     fixtures_season: str | None = None
                     ) -> tuple[list[BoardFixture], list[str]]:
    """Returns (board_fixtures_for_this_league, data_flags). Never raises for
    an ordinary data gap (uncovered league, thin history, fetch failure) —
    those become data_flags and an empty board slice, per HR35: a gap is
    reported, not skipped silently and not guessed around.

    `season` is the season the Dixon-Coles model is FIT on (history).
    `fixtures_season` is the season fixtures are pulled from (defaults to the
    season after `season`)."""
    flags: list[str] = []
    fixture_dates: dict[tuple[str, str], str] = {}
    recency_fit = False

    if league in MARKET_ONLY_LEAGUES:
        import pipeline.odds as _odds
        pairs, dates, oflags = _odds.fixtures_from_odds(league)
        flags += oflags
        odds, of2 = _odds_by_pair(league)
        board, n = _market_board(league, pairs, dates, odds)
        flags.append(f"{league}: {n}/{len(pairs)} fixture(s) priced MARKET-IMPLIED "
                     f"(cup across tiers — no single-league model; no edge claimed)")
        return board, flags

    # football-data.co.uk carries no continental competitions and no Croatia.
    # API-Football fills that gap for HISTORY (ratified 2026-08-03), but a
    # continental competition still cannot be fitted as a standalone league —
    # see api_football_results.is_cross_league for why.
    fallback_history = None
    cross_model = None
    if league in UNCOVERED_LEAGUES:
        if apif.is_cross_league(league):
            # Fitted on the pooled European graph — domestic results plus the
            # league phases of all three continental competitions, which are
            # what put clubs from different leagues on one scale.
            try:
                cross_model, _info, xflags = xleague.fit_cross_league(league)
                flags += xflags
                if cross_model is None:
                    return [], flags
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

    # Which feed the fixture list came from — what ID403 stamps. Only
    # TheSportsDB/API-Football are T1/T2; an odds-derived list is not.
    fixture_domain = "thesportsdb.com"
    if upcoming_fixtures is None:
        fx_season = fixtures_season or next_season_code(season)
        # TheSportsDB first (ratified HR34 2026-08-03) — it's the only free
        # source that can see the CURRENT season. API-Football is kept as the
        # fallback for whoever runs this on a paid plan.
        errors: list[str] = []
        upcoming_fixtures = []
        try:
            fixtures, fx_skipped = tsdb.fetch_upcoming(league, fx_season)
            upcoming_fixtures = tsdb.as_pairs(fixtures)
            # Kickoff dates, so a logged leg can be settled against THIS match
            # and not a same-pairing fixture from a previous season.
            fixture_dates.update({(f.home_team, f.away_team): f.date for f in fixtures})
            if fx_skipped:
                flags.append(f"{league}: {len(fx_skipped)} fixture rows skipped/malformed")
        except Exception as e:
            errors.append(f"thesportsdb: {e}")
            # Fall back to deriving fixtures from the ODDS feed. A priced event
            # is an upcoming fixture, so a league with history and live prices
            # but no fixtures-source league ID (Ekstraklasa) is recovered
            # rather than scanning as NO DATA.
            try:
                import pipeline.odds as _odds
                pairs, dates, oflags = _odds.fixtures_from_odds(league)
                if pairs:
                    upcoming_fixtures = pairs
                    fixture_dates.update(dates)
                    flags += oflags
                    fixture_domain = "sportybet.com"
            except Exception as e2:
                errors.append(f"odds-derived fixtures: {e2}")
                try:
                    season_year = api_football_season or int(f"20{fx_season[:2]}")
                    upcoming_fixtures = as_pairs(fetch_upcoming(league, season_year))
                    fixture_domain = "api-football.com"
                except Exception as e3:
                    errors.append(f"api-football: {e3}")

        if not upcoming_fixtures:
            detail = " | ".join(errors) if errors else "no fixtures in window"
            flags.append(f"{league}: no upcoming fixtures ({detail}) — NO DATA — PENDING")

    if cross_model is not None:
        results, skipped = [], []
    elif fallback_history is not None:
        results, skipped = fallback_history, []
    else:
        try:
            if league in intl.INTERNATIONAL_LEAGUES:
                # National teams: international results dataset (see
                # data/international_source.py), with its provenance flag.
                results, skipped, iflags = intl.load_results(league)
                flags += iflags
            else:
                results, skipped = load_league(league, season)
                # RECENCY (backtest/RECENCY_STUDY.md, 2026-10-02): also fit on
                # the season being played now, weighted to recent matches, so
                # the model sees this season's squads, managers and promoted
                # clubs instead of last season's. Missing current season
                # (e.g. before a league starts) just leaves last season.
                try:
                    current, cur_skipped = load_league(league, next_season_code(season))
                except Exception:
                    current, cur_skipped = [], []
                if current:
                    results = sorted(results + current, key=lambda r: r.date)
                    results = results[-RECENCY_MAX_MATCHES:]
                    skipped = list(skipped) + list(cur_skipped)
                    recency_fit = True
                    flags.append(f"{league}: model fitted on last season + {len(current)} "
                                 f"match(es) of this season, weighted to recent "
                                 f"(half-life {RECENCY_HALF_LIFE_DAYS} days)")
        except Exception as e:
            flags.append(f"{league}: results fetch failed ({e}) — NO DATA — PENDING")
            return [], flags

    if skipped:
        flags.append(f"{league}: {len(skipped)} source rows skipped/malformed")

    if cross_model is None and len(results) < 20:
        flags.append(f"{league}: insufficient match history ({len(results)} results) "
                      f"— NO DATA — PENDING rather than a thin fit")
        return [], flags

    if cross_model is not None:
        model = cross_model
    elif recency_fit:
        model = fit(results, half_life_days=RECENCY_HALF_LIFE_DAYS,
                    ref_date=date.today().isoformat())
    else:
        model = fit(results)

    # Second engine (ID82 Elo, ratified 2026-08-04). Built from the SAME match
    # history the goals model was fitted on, so the two are reading identical
    # evidence through different mathematics — which is what makes their
    # disagreement meaningful rather than an artefact of different inputs.
    elo_source = results if cross_model is None else xleague.build_pool(league)[0]
    try:
        elo_model = elo_engine.rate_through(elo_source)
    except Exception as e:
        elo_model = None
        flags.append(f"{league}: Elo second opinion unavailable ({str(e)[:60]})")
    board: list[BoardFixture] = []

    # Feed spellings the model knows under another name ("Blackpool FC" ->
    # "Blackpool"): rate with the model's name, keep the feed name on the
    # board so odds/booking lookups are unchanged. Strict, unique matches
    # only (engine/name_match.py); each one is flagged for checking.
    feed_names = sorted({t for pair in upcoming_fixtures for t in pair})
    model_names = sorted(set(model.teams) | set(model.thin_teams))
    rename = name_match.resolve(feed_names, model_names)
    if rename:
        flags.append(f"{league}: {len(rename)} feed name(s) matched to the model's "
                     f"spelling — " + ", ".join(f"{k} -> {v}" for k, v in sorted(rename.items())))

    for home, away in upcoming_fixtures:
        m_home, m_away = rename.get(home, home), rename.get(away, away)
        probs = predict(model, m_home, m_away)
        if probs is not None and (m_home, m_away) != (home, away):
            probs.home_team, probs.away_team = home, away
        # Stamp the feed the fixture actually came from — one source =>
        # ○ SINGLE-SOURCE here. run_daily then looks each fixture up in ESPN
        # and football-data (verification/fixture_check.py); two independent
        # T1/T2 sources agreeing upgrades it to ✓ VERIFIED.
        v = verify([SourcedDatum(domain=fixture_domain,
                                  value=f"{home} v {away}",
                                  url=f"https://www.{fixture_domain}",
                                  structured=True)])
        elo_p = elo_model.probabilities(m_home, m_away) if elo_model else None
        mes = None
        if probs is not None:
            best_prob = max(probs.p_home, probs.p_draw, probs.p_away,
                             probs.p_over_15, 1 - probs.p_over_15)
            mes = trigger_price(best_prob)

        board.append(BoardFixture(
            fixture=f"{home} v {away} ({league})",
            probs=probs,
            verification=v,
            on_deploy_shortlist=(probs is not None and is_deploy_eligible(league)
                                  and v.tier not in (Tier.CONFLICT, Tier.NO_DATA)),
            mes_trigger_price=mes,
            kickoff_date=fixture_dates.get((home, away)),
            elo_probs=elo_p,
            engine_divergence=elo_engine.divergence(elo_p, probs),
            rejection_reason=_unrated_detail(model, m_home, m_away) if probs is None else None,
        ))

    # xG BLEND (improvement #3, backtest/XG_STUDY.md): for the top-5 leagues the
    # model's scoreline grid = average of Dixon-Coles and an xG rating (more
    # accurate than goals alone in both test seasons).
    try:
        from engine import xg_model
        if league in xg_model.UNDERSTAT:
            xr = xg_model.ratings_for(league, fixtures_season or next_season_code(season))
            blended = 0
            for b in board:
                if b.probs is None or b.prob_source != "model":
                    continue
                xm = xr.matrix(b.probs.home_team, b.probs.away_team) if xr else None
                if xm is not None:
                    b.probs = xg_model.blend(b.probs, xm)
                    blended += 1
            flags.append(f"{league}: {blended} fixture(s) blended with xG ratings (Understat)")
    except Exception as e:  # noqa: BLE001 — xG is an enhancement, never a blocker
        flags.append(f"{league}: xG ratings unavailable ({str(e)[:60]}) — goals model only")

    # NATIONAL TEAMS (Architect 2026-10-04, backtest/NATIONAL_STUDY.md): the
    # scoreline grid = average of the UEFA Dixon-Coles fit and a national Elo
    # rated on every international since 1990 (competition-weighted, goal
    # margin, home advantage). On 450 unseen competitive UEFA internationals the
    # blend had the best 1X2 Brier and near-best goals accuracy. A fixture the
    # Dixon-Coles fit can't rate is rated by the national Elo alone.
    if league in intl.INTERNATIONAL_LEAGUES:
        try:
            from engine import national_elo, xg_model
            nat = national_elo.build()
            blended = elo_only = 0
            for b in board:
                home, away = b.fixture.rsplit(" (", 1)[0].split(" v ", 1)
                n_home, n_away = rename.get(home, home), rename.get(away, away)
                ne_p = national_elo.predict(nat, n_home, n_away)
                if ne_p is None:
                    continue
                ne_p.home_team, ne_p.away_team = home, away
                if b.probs is not None and b.probs.matrix is not None:
                    b.probs = xg_model.blend(b.probs, ne_p.matrix)
                    blended += 1
                elif b.probs is None:
                    b.probs = ne_p
                    b.rejection_reason = None
                    b.on_deploy_shortlist = (is_deploy_eligible(league)
                                             and b.verification.tier not in (Tier.CONFLICT, Tier.NO_DATA))
                    elo_only += 1
            flags.append(f"{league}: national Elo blended into {blended} fixture(s)"
                         + (f", rated {elo_only} the goals model could not" if elo_only else ""))
        except Exception as e:  # noqa: BLE001 — an enhancement, never a blocker
            flags.append(f"{league}: national Elo unavailable ({str(e)[:60]})")

    # NOTHING DROPPED (Architect 2026-10-02): a fixture the model can't rate is
    # priced MARKET-IMPLIED from SportyBet instead of sitting as NO DATA.
    unrated = [i for i, b in enumerate(board) if b.probs is None]
    if unrated:
        odds, _of = _odds_by_pair(league)
        from engine.market_implied import implied_probs
        filled = 0
        for i in unrated:
            b = board[i]
            home, away = b.fixture.rsplit(" (", 1)[0].split(" v ", 1)
            probs = implied_probs(odds.get((home, away)))
            if probs is None:
                continue
            b.probs, b.prob_source, b.rejection_reason = probs, "market", None
            b.on_deploy_shortlist = (is_deploy_eligible(league)
                                     and b.verification.tier not in (Tier.CONFLICT, Tier.NO_DATA))
            b.mes_trigger_price = b.engine_divergence = b.elo_probs = None
            filled += 1
        if filled:
            flags.append(f"{league}: {filled} unrated fixture(s) priced MARKET-IMPLIED "
                         f"from SportyBet (no model history — no edge claimed)")

    # Surface unmapped names ONCE per league, with the model's actual roster
    # beside them. A naming mismatch and a genuinely new club are
    # indistinguishable from inside the model, but obvious to a human the
    # moment the two lists sit next to each other.
    unmapped = sorted({t for h, a in upcoming_fixtures for t in (h, a)
                       if rename.get(t, t) not in model.teams
                       and rename.get(t, t) not in model.thin_teams})
    if unmapped:
        flags.append(
            f"{league}: {len(unmapped)} team name(s) in the fixtures feed not found "
            f"in the fitted data — {', '.join(unmapped)}. Model knows: "
            f"{', '.join(sorted(model.teams))}. If a name above is the same club "
            f"under a different spelling, add it to TEAM_ALIASES in "
            f"data/thesportsdb_fixtures.py; if it is newly promoted, it correctly "
            f"has no rating yet.")

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
