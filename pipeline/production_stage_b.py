"""
HR58 Stage B — Production Logic Reading Stage A Output.

Reads the immutable fixture list from Stage A, processes ALL fixtures (including
NO DATA — PENDING rows, never silently dropped), and generates the 4-layer output:

Layer 2 (Full Grid) → Layer 1 (Compact) → Acca Route (Capital-Eligible) → THE PICK (Last)

Vehicle: 2 accas + 1 SLV per session (rejected 4-5 accas).
Production runs before 08:00 kickoff pipeline.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from engine.acca import (
    Acca,
    AccaLeg,
    ProductionBets,
    _make_acca,
    build_production_bets,
    render_production_block,
)
from engine.dixon_coles import FixtureProbabilities
from engine.leagues import is_deploy_eligible
from engine.mes import edge_diff, mes_numeric_ev, trigger_price
from engine import markets as mkt
from output.produce_bet import BoardFixture, render_part2_compact, render_part2_the_scan, render_part5_signoff
from pipeline.fixture_extraction import StageAOutput, VerifiedFixture
from verification.id403 import VerificationResult, Tier, stamp

log = logging.getLogger("pipeline.production_stage_b")


# Output path for Stage B production artifact
STAGE_B_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "stage_b_output"
STAGE_B_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Vehicle structure: 2 accas + 1 SLV (single) per session
VEHICLE_ACCA_MAX = 2      # Headline accas: Acca A + Acca B (was 4-5, reduced per Architect)
VEHICLE_SLV_COUNT = 1     # Single SLV (was singles per fixture, now 1 best single)
ACCA_A_MAX = 4            # Acca A holds top 4 legs (was 5)
SPLIT_GROUP_TARGET = 4    # Remainder splits into ~4 leg groups


@dataclass
class ProductionLayer2:
    """Layer 2 — Full Grid: the complete scan table with all fixtures."""
    fixtures: list[BoardFixture]
    compact: str  # render_part2_compact output
    full_scan: str  # render_part2_the_scan output


@dataclass
class ProductionLayer1:
    """Layer 1 — Compact: today's deploy-eligible fixtures with pick + booking code."""
    today_fixtures: list[BoardFixture]
    table: str  # Full detail table (render_part1_the_call)


@dataclass
class ProductionAccaRoute:
    """Acca Route — Capital-eligible bets only (2 accas + 1 SLV)."""
    acca_a: Optional[Acca] = None
    acca_b: Optional[Acca] = None
    slv: Optional[AccaLeg] = None  # Single best standalone leg
    watchlist: list[AccaLeg] = field(default_factory=list)  # ID420 watchlist (odds > 2.00)


@dataclass
class ProductionThePick:
    """THE PICK — Final sign-off: the single best capital leg."""
    leg: Optional[AccaLeg] = None
    rationale: str = ""


@dataclass
class StageBOutput:
    """Complete Stage B output — the day's production for Telegram/board."""
    run_date: str                    # YYYY-MM-DD
    fixtures_season: str             # season code fixtures pulled for
    stage_a_run_date: str            # run_date from Stage A input
    layer2: ProductionLayer2
    layer1: ProductionLayer1
    acca_route: ProductionAccaRoute
    the_pick: ProductionThePick
    data_flags: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "run_date": self.run_date,
            "fixtures_season": self.fixtures_season,
            "stage_a_run_date": self.stage_a_run_date,
            "layer2": {
                "compact": self.layer2.compact,
                "full_scan": self.layer2.full_scan,
                "fixtures_count": len(self.layer2.fixtures),
            },
            "layer1": {
                "table": self.layer1.table,
                "today_fixtures_count": len(self.layer1.today_fixtures),
            },
            "acca_route": {
                "acca_a": self.acca_route.acca_a.label if self.acca_route.acca_a else None,
                "acca_a_legs": len(self.acca_route.acca_a.legs) if self.acca_route.acca_a else 0,
                "acca_b": self.acca_route.acca_b.label if self.acca_route.acca_b else None,
                "acca_b_legs": len(self.acca_route.acca_b.legs) if self.acca_route.acca_b else 0,
                "slv": self.acca_route.slv.fixture if self.acca_route.slv else None,
                "watchlist_count": len(self.acca_route.watchlist),
            },
            "the_pick": {
                "fixture": self.the_pick.leg.fixture if self.the_pick.leg else None,
                "market": self.the_pick.leg.market_name if self.the_pick.leg else None,
                "price": self.the_pick.leg.price if self.the_pick.leg else None,
                "edge": self.the_pick.leg.edge if self.the_pick.leg else None,
                "rationale": self.the_pick.rationale,
            },
            "data_flags": self.data_flags,
            "stats": self.stats,
        }, indent=2)

    @classmethod
    def from_json(cls, data: str) -> "StageBOutput":
        obj = json.loads(data)
        # Note: full objects not restored from JSON - this is for inspection
        return cls(**{k: v for k, v in obj.items() if k not in ["layer2", "layer1", "acca_route", "the_pick"]})

    def save(self, path: Path | None = None) -> Path:
        if path is None:
            path = STAGE_B_OUTPUT_DIR / f"production_{self.run_date}_{self.fixtures_season}.json"
        path.write_text(self.to_json(), encoding="utf-8")
        return path


def _verified_fixture_to_board_fixture(vf: VerifiedFixture, today: str) -> BoardFixture:
    """Convert a VerifiedFixture from Stage A to a BoardFixture for production."""
    # Build verification result - VerificationResult requires a value argument
    tier = Tier(vf.verification_tier) if vf.verification_tier in [t.value for t in Tier] else Tier.NO_DATA
    verification = VerificationResult(
        tier=tier,
        value=f"{vf.home_team} v {vf.away_team}",
        note=vf.verification_note,
        factors=vf.verification_factors,
    )

    # Determine if fixture kicks off today
    kickoff_today = vf.kickoff_date == today

    # Determine deploy eligibility
    on_shortlist = (
        is_deploy_eligible(vf.league)
        and vf.verification_tier not in ("CONFLICT", "NO-DATA")
        and kickoff_today
    )

    # No model probs in Stage A - will be enriched in production
    probs = None
    mes_trigger = None
    rating_source = None

    # Status maps to rejection reason
    rejection_reason = None
    if vf.status == "no_data":
        rejection_reason = f"NO DATA — PENDING: {vf.verification_note}"
    elif vf.status == "pending":
        rejection_reason = f"CONFLICT — Architect must adjudicate: {vf.verification_note}"

    return BoardFixture(
        fixture=f"{vf.home_team} v {vf.away_team} ({vf.league})",
        probs=probs,
        verification=verification,
        on_deploy_shortlist=on_shortlist,
        mes_trigger_price=mes_trigger,
        kickoff_date=vf.kickoff_date,
        rejection_reason=rejection_reason,
        rating_source=rating_source,
        model_engine=vf.source_tier or "unknown",
    )


def _load_stage_a_output(stage_a_path: Path) -> StageAOutput:
    """Load Stage A output from JSON file."""
    return StageAOutput.load(stage_a_path)


def _enrich_fixtures_with_models(
    board: list[BoardFixture],
    today: str,
    season: str,
    fixtures_season: str,
    days_ahead: int = 14,
) -> tuple[list[BoardFixture], list[str]]:
    """
    Enrich board fixtures with model probabilities (DC, Elo, xG, bookmaker).
    This mirrors the logic from orchestrator_DEPRECATED.scan_one_league but
    operates on the Stage A fixture universe.

    Returns (enriched_board, flags).
    """
    from data.football_data_source import load_league, load_second_division
    from data import api_football_results as apif
    from data import xg_source
    from data import clubelo_source
    from engine import cross_league as xleague
    from engine import elo as elo_engine
    from engine.consensus import compute_consensus
    from engine.dixon_coles import fit, predict, predict_adjusted, FixtureProbabilities
    from brain.store import Brain, content_hash, elo_to_payload, elo_from_payload, dc_to_payload, dc_from_payload
    from data.football_data_source import UNCOVERED_LEAGUES
    from booking.bridge import get_sportybet_odds_for_leg
    from data.thesportsdb_fixtures import map_team
    from verification.id403 import verify, SourcedDatum, Tier

    flags: list[str] = []
    brain = Brain()
    as_of_str = today

    # Group fixtures by league
    by_league: dict[str, list[BoardFixture]] = {}
    for bf in board:
        by_league.setdefault(bf.fixture.split(" (")[-1].rstrip(")"), []).append(bf)

    PROMOTION_SCALE = 0.90
    PROMOTION_OPPONENT_SCALE = 1.08

    for league, league_fixtures in by_league.items():
        log.info(f"Stage B: enriching {league} ({len(league_fixtures)} fixtures)")

        # --- History loading (same as orchestrator) ---
        cross_model = None
        pooled = None
        fallback_history = None

        if league in UNCOVERED_LEAGUES:
            if apif.is_cross_league(league):
                try:
                    pooled, pool_info, xflags = xleague.build_pool(league)
                    flags += xflags
                    pool_hash = content_hash(pooled, salt=f"cross:{league}:{season}")
                    row = brain.load_model_state(f"cross:{league}")
                    if row is not None and row["content_hash"] == pool_hash:
                        cross_model = dc_from_payload(row["payload"])
                        cross_model.league = league
                    else:
                        cross_model, _info, fit_flags = xleague.fit_cross_league(
                            league, pool=(pooled, pool_info))
                        flags += fit_flags
                        if cross_model is None:
                            continue
                        if brain:
                            brain.save_model_state(
                                f"cross:{league}", "cross", 1, pool_hash,
                                cross_model.n_matches_fit,
                                min(r.date for r in pooled),
                                max(r.date for r in pooled),
                                dc_to_payload(cross_model))
                except Exception as e:
                    flags.append(f"{league}: cross-league fit failed ({str(e)[:70]})")
                    continue
            else:
                try:
                    fallback_history, hflags = apif.load_results(league)
                    flags += hflags
                    if len(fallback_history) < 20:
                        flags.append(f"{league}: fallback history too thin")
                        fallback_history = None
                except Exception:
                    fallback_history = None

        if cross_model is None and fallback_history is None:
            try:
                fallback_history, _ = load_league(league, season)
            except Exception:
                try:
                    from data.multi_source_concrete import get_historical_results
                    fallback_history = get_historical_results(league, season)
                    flags.append(f"{league}: history via multi-source")
                except Exception:
                    flags.append(f"{league}: NO DATA — PENDING (no history source)")
                    continue

        # Merge current-season results from football-data.org (promoted clubs)
        try:
            from data.multi_source_concrete import FootballDataOrgResultsSource
            fdo = FootballDataOrgResultsSource()
            fdo_result = fdo.fetch(league=league, season=season, fixtures_season=fixtures_season)
            fdo_results = fdo_result.get("results", [])
            if fdo_results and fallback_history:
                existing = {(r.date, r.home_team, r.away_team) for r in fallback_history}
                added = 0
                for r in fdo_results:
                    key = (r.date, r.home_team, r.away_team)
                    if key not in existing:
                        fallback_history.append(r)
                        existing.add(key)
                        added += 1
                if added:
                    flags.append(f"{league}: +{added} current-season results from football-data.org")
        except Exception:
            pass

        # --- Fit or reuse DC model ---
        if cross_model is not None:
            model = cross_model
        else:
            dc_hash = content_hash(fallback_history, salt=f"dc:{league}:{season}")
            row = brain.load_model_state(f"dc:{league}")
            if row is not None and row["content_hash"] == dc_hash:
                model = dc_from_payload(row["payload"])
            else:
                model = fit(fallback_history)
                if brain:
                    brain.save_model_state(
                        f"dc:{league}", "dc", 1, dc_hash,
                        model.n_matches_fit,
                        min(r.date for r in fallback_history),
                        max(r.date for r in fallback_history),
                        dc_to_payload(model))

        # --- Carry-over model for promoted clubs ---
        carry_model = None
        carry_promoted: set[str] = set()
        carry_flags: list[str] = []
        if cross_model is None:
            try:
                carry_season = f"{int(season[:2]) - 1:02d}{int(season[2:]) - 1:02d}"
                carry_results, _ = load_league(league, carry_season)
                sec_results, _ = load_second_division(league, carry_season)
                if sec_results:
                    top_flight = ({r.home_team for r in carry_results} | {r.away_team for r in carry_results})
                    sec_teams = ({r.home_team for r in sec_results} | {r.away_team for r in sec_results})
                    carry_promoted = sec_teams - top_flight
                    carry_results = carry_results + sec_results
                carry_hash = content_hash(carry_results, salt=f"dc:{league}:carry:{carry_season}")
                row = brain.load_model_state(f"dc:{league}:carry")
                if row is not None and row["content_hash"] == carry_hash:
                    carry_model = dc_from_payload(row["payload"])
                else:
                    carry_model = fit(carry_results)
                    if brain:
                        brain.save_model_state(
                            f"dc:{league}:carry", "dc", 1, carry_hash,
                            carry_model.n_matches_fit,
                            min(r.date for r in carry_results),
                            max(r.date for r in carry_results),
                            dc_to_payload(carry_model))
            except Exception:
                carry_model = None

        # --- Elo model ---
        elo_model = None
        elo_source = fallback_history if cross_model is None else pooled
        try:
            elo_row = brain.load_model_state(f"elo:{league}")
            seed = elo_from_payload(elo_row["payload"]) if elo_row else None
            elo_model = elo_engine.rate_through(elo_source, seed_from=seed)
            if elo_model is not None and brain:
                brain.save_model_state(
                    f"elo:{league}", "elo", elo_engine.STATE_VERSION,
                    content_hash(elo_source, salt=f"elo:{league}:{season}"),
                    elo_model.n_matches, elo_model.last_date, None,
                    elo_to_payload(elo_model))
        except Exception as e:
            flags.append(f"{league}: Elo unavailable ({str(e)[:60]})")

        # --- xG model ---
        xg_ratings = None
        if xg_source.is_covered(league):
            try:
                xg_ratings = xg_source.fit_xg(league, season)
            except Exception:
                pass

        # --- Enrich each fixture ---
        for bf in league_fixtures:
            # Apply team alias mapping so fixture feed names match fitted model roster
            home = map_team(league, bf.fixture.split(" (")[0].split(" v ")[0].strip())
            away = map_team(league, bf.fixture.split(" (")[0].split(" v ")[1].strip())

            probs = predict(model, home, away)
            carry_rated = False
            rating_source = None

            # Promoted-club fallback
            if probs is None and carry_model is not None:
                if home in carry_promoted or away in carry_promoted:
                    carry_p = predict_adjusted(
                        carry_model, home, away,
                        scale_home=(PROMOTION_SCALE if home in carry_promoted else PROMOTION_OPPONENT_SCALE),
                        scale_away=(PROMOTION_SCALE if away in carry_promoted else PROMOTION_OPPONENT_SCALE))
                else:
                    carry_p = predict(carry_model, home, away)
                if carry_p is not None:
                    probs = carry_p
                    carry_rated = True
                    carry_flags.append(f"{home} v {away}")
            rating_source = "carry" if carry_rated else None

            # ClubElo stretch
            if probs is None:
                cl_h = clubelo_source.elo_for(home)
                cl_a = clubelo_source.elo_for(away)
                if cl_h is not None and cl_a is not None:
                    cl_p = elo_engine.EloModel(ratings={home: cl_h, away: cl_a}).probabilities(home, away)
                    if cl_p is not None:
                        ph, pd, pa = cl_p
                        probs = FixtureProbabilities(
                            home_team=home, away_team=away,
                            lambda_home=0.0, lambda_away=0.0,
                            p_home=ph, p_draw=pd, p_away=pa,
                            modal_scoreline=(0, 0))
                        rating_source = "clubelo"

            # Tactical engine (ID417)
            tactical_prov = None
            if probs is not None:
                try:
                    home_snap = brain.get_team_state(team=home, league=league, as_of=as_of_str, limit=1)
                    away_snap = brain.get_team_state(team=away, league=league, as_of=as_of_str, limit=1)
                    h_form = home_snap[0].get("derived_formation") if home_snap else None
                    a_form = away_snap[0].get("derived_formation") if away_snap else None
                    h_hash = home_snap[0].get("squad_hash") if home_snap else None
                    a_hash = away_snap[0].get("squad_hash") if away_snap else None
                    h_prior, a_prior = None, None  # Simplified - tactical_engine.load_prior_hashes
                    from engine import tactical as tactical_engine
                    adj = tactical_engine.tactical_for_fixture(
                        home_formation=h_form, away_formation=a_form,
                        home_squad_hash=h_hash, away_squad_hash=a_hash,
                        home_prior_hash=h_prior, away_prior_hash=a_prior)
                    if adj.applied:
                        base_model = carry_model if carry_rated else model
                        probs = predict_adjusted(
                            base_model, home, away,
                            scale_home=adj.scale_home,
                            scale_away=adj.scale_away)
                        tactical_prov = adj.provenance
                except Exception:
                    pass

            # Verification (already done in Stage A, but refresh for board)
            v = verify([SourcedDatum(
                domain="thesportsdb.com",
                value=f"{home} v {away}",
                url="https://www.thesportsdb.com",
                structured=True)])

            # Second/third/fourth opinions
            elo_p = elo_model.probabilities(home, away) if elo_model else None
            xg_p = xg_source.predict_xg(home, away, xg_ratings, league=league) if xg_ratings else None
            xg_t = (xg_p.home, xg_p.draw, xg_p.away) if xg_p else None
            xg_goals = (xg_p.over15, xg_p.over25, xg_p.over35, xg_p.btts) if xg_p else None

            # Market probs (bookmaker devigged) - from odds if available
            market_probs = None
            blend_probs = None

            # SportyBet odds for MES/CLV
            sb_odds = {"home": None, "draw": None, "away": None}
            sb_mes = None
            best_price = None
            best_market = None
            best_model_prob = None
            best_mes_ev = None
            best_bookmaker = "SportyBet"
            best_n_books = 1
            mes_trigger = None

            for market_key, prob_attr in [("1X2_HOME", "p_home"), ("1X2_DRAW", "p_draw"), ("1X2_AWAY", "p_away")]:
                sb_price = get_sportybet_odds_for_leg(home, away, league, market_key)
                if sb_price:
                    if probs is not None:
                        market_prob = getattr(probs, prob_attr)
                        if market_prob:
                            sb_mes_val = mes_numeric_ev(market_prob, sb_price)
                            if sb_mes is None or (sb_mes_val is not None and sb_mes_val > sb_mes):
                                sb_mes = sb_mes_val
                    if market_key == "1X2_HOME":
                        sb_odds["home"] = sb_price
                    elif market_key == "1X2_DRAW":
                        sb_odds["draw"] = sb_price
                    elif market_key == "1X2_AWAY":
                        sb_odds["away"] = sb_price

            # Determine best market for this fixture
            if probs is not None:
                candidates = []
                for mk in mkt.EDGE_MARKETS:
                    prob = mkt.model_prob(mk, probs)
                    if prob is None:
                        continue
                    price = None
                    if mk in mkt.MARKETS_1X2:
                        price = sb_odds.get(mkt.MARKETS_1X2[mk])
                    # Could also check odds_index here for other markets
                    if price and price > 1.0:
                        edge = edge_diff(prob, price)
                        ev = mes_numeric_ev(prob, price)
                        candidates.append((edge, prob, price, mk, ev))
                if candidates:
                    candidates.sort(key=lambda x: (x[0] if x[0] is not None else -1, x[1]), reverse=True)
                    best_edge, best_prob, best_price, best_mk, best_ev = candidates[0]
                    best_market = mkt.display(best_mk, home, away)
                    best_model_prob = best_prob
                    best_mes_ev = best_ev
                    mes_trigger = trigger_price(best_prob)

            # Consensus
            consensus = compute_consensus(probs, elo_p, xg_t) if probs else None

            # Update the board fixture
            bf.probs = probs
            bf.verification = v
            bf.model_engine = "cross" if cross_model else "dc"
            bf.rating_source = rating_source
            bf.elo_probs = elo_p
            bf.xg_probs = xg_t
            bf.xg_goals = xg_goals
            bf.goals_divergence = xg_source.goals_divergence(probs, xg_p) if probs and xg_p else None
            bf.consensus = consensus
            bf.engine_divergence = elo_engine.divergence(elo_p, probs) if elo_p and probs else None
            bf.best_market = best_market
            bf.best_price = best_price
            bf.best_model_prob = best_model_prob
            bf.best_mes_ev = best_mes_ev
            bf.best_bookmaker = best_bookmaker
            bf.best_n_books = best_n_books
            bf.mes_trigger_price = mes_trigger
            bf.sb_home_odds = sb_odds["home"]
            bf.sb_draw_odds = sb_odds["draw"]
            bf.sb_away_odds = sb_odds["away"]
            bf.sb_mes_ev = sb_mes
            bf.tactical_provenance = tactical_prov

    if carry_flags:
        flags.append(f"Carry-over rated: {', '.join(carry_flags)}")

    return board, flags


def _build_acca_route(production_bets: ProductionBets) -> ProductionAccaRoute:
    """
    Build the Acca Route from ProductionBets with vehicle constraint:
    2 accas (Acca A + Acca B) + 1 SLV.
    """
    accas = ([production_bets.acca_a] if production_bets.acca_a else []) + production_bets.split_accas

    acca_a = accas[0] if len(accas) > 0 else None
    acca_b = accas[1] if len(accas) > 1 else None

    # SLV = single best leg from remaining singles (highest edge)
    slv = None
    if production_bets.singles:
        singles_sorted = sorted(
            production_bets.singles,
            key=lambda l: (l.edge if l.edge is not None else -1.0, l.prob),
            reverse=True
        )
        slv = singles_sorted[0]

    return ProductionAccaRoute(
        acca_a=acca_a,
        acca_b=acca_b,
        slv=slv,
        watchlist=production_bets.watchlist,
    )


def _select_the_pick(acca_route: ProductionAccaRoute) -> ProductionThePick:
    """
    THE PICK — single best capital-eligible leg.
    Priority: Acca A first leg > Acca B first leg > SLV.
    """
    if acca_route.acca_a and acca_route.acca_a.legs:
        leg = acca_route.acca_a.legs[0]
        rationale = "Top leg of headline Acca A (highest canonical edge)"
    elif acca_route.acca_b and acca_route.acca_b.legs:
        leg = acca_route.acca_b.legs[0]
        rationale = "Top leg of Acca B (next highest canonical edge)"
    elif acca_route.slv:
        leg = acca_route.slv
        rationale = "Best standalone single (SLV)"
    else:
        return ProductionThePick(leg=None, rationale="No capital-eligible legs today")

    return ProductionThePick(
        leg=leg,
        rationale=rationale
    )


def run_stage_b(
    stage_a_path: Path,
    season: str = "2526",
    fixtures_season: str | None = None,
    days_ahead: int = 14,
    max_odds_cap: float = 2.00,
    min_odds_floor: float = 1.20,
    preferred_ceiling: float = 1.50,
) -> StageBOutput:
    """
    HR58 Stage B — Production reads Stage A output, NO DATA — PENDING rows preserved.

    Args:
        stage_a_path: Path to Stage A JSON output
        season: Season the model is FIT on
        fixtures_season: Season fixtures are from (default: next_season_code)
        days_ahead: Fixture window
        max_odds_cap: ID420 hard cap (default 2.00)
        min_odds_floor: Hard floor (default 1.20)
        preferred_ceiling: Preferred zone ceiling (default 1.50)

    Returns:
        StageBOutput with 4-layer production output.
    """
    from orchestrator_DEPRECATED import next_season_code

    # Load Stage A output
    stage_a = _load_stage_a_output(stage_a_path)
    run_date = date.today().isoformat()
    fixtures_season = fixtures_season or next_season_code(season)
    today = date.today().isoformat()

    log.info(f"Stage B: reading Stage A from {stage_a_path}")
    log.info(f"  Stage A run_date: {stage_a.run_date}, fixtures: {len(stage_a.fixtures)}")

    # Convert ALL Stage A fixtures to BoardFixtures (NO silent drops - HR35)
    board: list[BoardFixture] = []
    for vf in stage_a.fixtures:
        bf = _verified_fixture_to_board_fixture(vf, today)
        board.append(bf)

    # Enrich with model probabilities
    board, enrich_flags = _enrich_fixtures_with_models(
        board, today, season, fixtures_season, days_ahead
    )

    # Separate today's fixtures for Layer 1
    today_fixtures = [bf for bf in board if bf.kickoff_date == today]

    # Build production bets
    production_bets = build_production_bets(
        board,
        today=today,
        odds_index=None,  # Could be passed if available
        acca_a_max=ACCA_A_MAX,
        agreement_band=None,  # Opt-in experiment, default off
        max_odds_cap=max_odds_cap,
        min_odds_floor=min_odds_floor,
        preferred_ceiling=preferred_ceiling,
    )

    # Build 4 layers
    layer2 = ProductionLayer2(
        fixtures=board,
        compact=render_part2_compact(board),
        full_scan=render_part2_the_scan(board),
    )

    layer1 = ProductionLayer1(
        today_fixtures=today_fixtures,
        table="",  # Will be filled below
    )

    # Render Layer 1 table (full detail THE CALL)
    from output.produce_bet import render_part1_the_call
    layer1.table = render_part1_the_call(today_fixtures)

    acca_route = _build_acca_route(production_bets)
    the_pick = _select_the_pick(acca_route)

    # Stats
    stats = {
        "total_fixtures_stage_a": len(stage_a.fixtures),
        "total_fixtures_enriched": len(board),
        "today_fixtures": len(today_fixtures),
        "deploy_eligible_today": len([bf for bf in today_fixtures if bf.on_deploy_shortlist]),
        "no_data_fixtures": len([bf for bf in board if bf.rejection_reason and "NO DATA" in bf.rejection_reason]),
        "conflict_fixtures": len([bf for bf in board if bf.rejection_reason and "CONFLICT" in bf.rejection_reason]),
        "verified_fixtures": len([bf for bf in board if bf.verification.tier == Tier.VERIFIED]),
        "single_source_fixtures": len([bf for bf in board if bf.verification.tier == Tier.SINGLE_SOURCE]),
        "acca_a_legs": len(acca_route.acca_a.legs) if acca_route.acca_a else 0,
        "acca_b_legs": len(acca_route.acca_b.legs) if acca_route.acca_b else 0,
        "slv": acca_route.slv.fixture if acca_route.slv else None,
        "watchlist_count": len(acca_route.watchlist),
    }

    output = StageBOutput(
        run_date=run_date,
        fixtures_season=fixtures_season,
        stage_a_run_date=stage_a.run_date,
        layer2=layer2,
        layer1=layer1,
        acca_route=acca_route,
        the_pick=the_pick,
        data_flags=stage_a.flags + enrich_flags,
        stats=stats,
    )

    # Save immutable artifact
    saved_path = output.save()
    log.info(f"Stage B complete: saved to {saved_path}")

    return output


def render_stage_b_output(output: StageBOutput, codes: Optional[dict] = None) -> str:
    """
    Render the complete 4-layer production output in the mandated order:
    Layer 2 → Layer 1 → Acca Route → THE PICK
    """
    today = date.today().isoformat()
    s = output.stats or {}
    lines = [
        f"OLP XDV — PRODUCTION OUTPUT — {today}",
        f"Stage A: {output.stage_a_run_date} | Fixtures Season: {output.fixtures_season}",
        f"Total Fixtures: {s.get('total_fixtures_enriched', 'N/A')} "
        f"(Today: {s.get('today_fixtures', 'N/A')}, "
        f"Deploy-Eligible: {s.get('deploy_eligible_today', 'N/A')}, "
        f"NO DATA: {s.get('no_data_fixtures', 'N/A')})",
        "",
        "=" * 60,
        "LAYER 2 — FULL GRID (Complete Scan Table)",
        "=" * 60,
        output.layer2.compact,
        "",
        output.layer2.full_scan,
        "",
        "=" * 60,
        "LAYER 1 — COMPACT (Today's Deploy-Eligible + Pick + Booking Code)",
        "=" * 60,
        output.layer1.table,
        "",
        "=" * 60,
        "ACCA ROUTE — Capital-Eligible (2 Accas + 1 SLV)",
        "=" * 60,
    ]

    # Acca A
    if output.acca_route.acca_a:
        acca = output.acca_route.acca_a
        code = _code_for(codes, acca.label)
        lines.append(f"★ {acca.label} — HEADLINE ({acca.n_legs} legs)")
        for leg in acca.legs:
            lines.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} @ {leg.price:.2f}")
        lines.append(f"    Combined odds: {acca.combined_odds:.2f} | "
                     f"Combined prob: {acca.combined_prob:.1%} | "
                     f"Booking code: {code or 'NO DATA — PENDING'}")
    else:
        lines.append("Acca A: No capital-eligible legs for headline acca")

    # Acca B
    if output.acca_route.acca_b:
        acca = output.acca_route.acca_b
        code = _code_for(codes, acca.label)
        lines.append(f"")
        lines.append(f"★ {acca.label} ({acca.n_legs} legs)")
        for leg in acca.legs:
            lines.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} @ {leg.price:.2f}")
        lines.append(f"    Combined odds: {acca.combined_odds:.2f} | "
                     f"Combined prob: {acca.combined_prob:.1%} | "
                     f"Booking code: {code or 'NO DATA — PENDING'}")
    else:
        lines.append("Acca B: No second acca formed (insufficient remainder legs)")

    # SLV
    if output.acca_route.slv:
        leg = output.acca_route.slv
        code = _code_for(codes, f"SINGLE — {leg.fixture}")
        lines.append(f"")
        lines.append(f"★ SLV — Single Best Value")
        lines.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} @ {leg.price:.2f}")
        lines.append(f"    Edge: {leg.edge:+.2%} | EV: {leg.ev:+.2%} | "
                     f"Booking code: {code or 'NO DATA — PENDING'}")
    else:
        lines.append("SLV: No standalone single available")

    # Watchlist
    if output.acca_route.watchlist:
        lines.append("")
        lines.append("  ⚠ WATCHLIST (ID420 — odds > 2.00) — NOT CAPITAL, review only")
        for leg in output.acca_route.watchlist:
            lines.append(f"    {leg.fixture} ({leg.league}) — {leg.market_name} "
                         f"@ {leg.price:.2f}  edge {leg.edge:+.2%}")

    lines += [
        "",
        "=" * 60,
        "THE PICK — Final Sign-Off",
        "=" * 60,
    ]

    if output.the_pick.leg:
        leg = output.the_pick.leg
        lines.append(f"Fixture: {leg.fixture} ({leg.league})")
        lines.append(f"Market: {leg.market_name}")
        lines.append(f"Price: {leg.price:.2f}")
        lines.append(f"Model Prob: {leg.prob:.1%}")
        lines.append(f"Canonical Edge: {leg.edge:+.2%}")
        lines.append(f"EV (Kelly): {leg.ev:+.2%}")
        lines.append(f"Rationale: {output.the_pick.rationale}")
    else:
        lines.append("No capital-eligible pick today — valid, honest result (HR35)")

    lines += [
        "",
        render_part5_signoff(),
    ]

    return "\n".join(lines)


def _code_for(codes: Optional[dict], label: str) -> Optional[str]:
    """Extract booking code for label."""
    if not codes:
        return None
    for r in codes.get("results") or []:
        if r.get("label") == label:
            return r.get("code")
    return None


if __name__ == "__main__":
    import argparse
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="HR58 Stage B — Production from Stage A")
    ap.add_argument("--stage-a", required=True, help="Path to Stage A JSON output")
    ap.add_argument("--season", default="2526", help="Season the model is FIT on")
    ap.add_argument("--fixtures-season", default=None, help="Season fixtures are from")
    ap.add_argument("--days-ahead", type=int, default=14, help="Fixture window")
    ap.add_argument("--max-odds-cap", type=float, default=2.00, help="ID420 hard cap")
    ap.add_argument("--min-odds-floor", type=float, default=1.20, help="Hard floor")
    ap.add_argument("--preferred-ceiling", type=float, default=1.50, help="Preferred zone ceiling")
    ap.add_argument("--output", default=None, help="Output JSON path")

    args = ap.parse_args()

    output = run_stage_b(
        stage_a_path=Path(args.stage_a),
        season=args.season,
        fixtures_season=args.fixtures_season,
        days_ahead=args.days_ahead,
        max_odds_cap=args.max_odds_cap,
        min_odds_floor=args.min_odds_floor,
        preferred_ceiling=args.preferred_ceiling,
    )

    if args.output:
        output.save(Path(args.output))
    else:
        output.save()

    print(render_stage_b_output(output))
    print(f"\n✓ Stage B complete: {output.stats['deploy_eligible_today']} deploy-eligible today, "
          f"{output.stats['acca_a_legs']}+{output.stats['acca_b_legs']} acca legs, "
          f"SLV: {output.stats['slv'] or 'none'}, "
          f"Watchlist: {output.stats['watchlist_count']}")