"""Cup training — monitor cup competitions live and TRAIN THE BRAIN.

WHY IT EXISTS
  The daily run logs paper legs only for deploy-eligible (softness A/B)
  leagues. The cups — EFL Cup, J-League, Europa League quals, Champions
  League quals — involve clubs from the 15 approved leagues but are not
  deploy leagues themselves, so they were never logged. The Architect
  authorised (2026-08-06): log a paper leg on EVERY cup fixture — O1.5 as the
  baseline plus every priced market (1X2, O2.5, U2.5) — purely to train the
  brain. The monitor settles each completed match, so the brain accumulates
  hit-rate + CLV evidence per market across the cups.

PHASE SEPARATION (the whole point)
  Cup legs are written with phase="cup_training", NOT "phase2_paper".
  - The brain's calibration_by_market(phase="cup_training") reads them, so
    the engine's CLV-gated recalibration LEARNS from the cups.
  - The Phase-3 capital gate counts ONLY "phase2_paper" legs, so a flood of
    cup legs can never graduate the framework by volume. Training the brain
    is not a back-door to capital.

HONESTY (HR35)
  - O1.5 has no price source in this framework (blocked from capital per
    ID405 anyway) -> its leg logs OUTCOME evidence (hit/miss after settle)
    and entry_odds=None, so CLV stays NO DATA — PENDING. Never estimated.
  - Priced markets get their REAL entry price from the odds feed.
  - A leg whose match is not exactly matched (home, away, kickoff DATE) is
    never settled (HR48 discipline, same as grade_open_legs).
  - A result comes from the SOURCE (/scores or TSDB), never guessed.
"""
from __future__ import annotations

import sys
import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.odds as odds  # noqa: E402
from clv.clv_logger import CLVLog  # noqa: E402
from engine import markets as mkt  # noqa: E402

# The cup competitions the Architect asked to train on (2026-08-06).
# key   = the odds-api sport key, when the feed prices it
# tsdb  = TheSportsDB league id, used as the SCORES fallback
# label = the framework's internal league name
CUP_COMPETITIONS: dict[str, dict] = {
    "EFL Cup": {"odds": "soccer_england_efl_cup", "tsdb": None},
    "J League": {"odds": "soccer_japan_j_league", "tsdb": None},
    "Europa League": {"odds": None, "tsdb": 4481},  # verified 4481 2026-08-06
    "Champions League": {"odds": "soccer_uefa_champs_league_qualification",
                         "tsdb": 4480},
}

# Markets logged on EVERY cup fixture. O1.5 is the Architect's baseline (and
# the one with no price — pure outcome evidence); the priced deployable
# markets (1X2, O2.5, U2.5) carry the real CLV when the feed quotes them.
ALWAYS_LEGS = (mkt.OVER_15,)
PRICED_LEGS = (mkt.HOME, mkt.DRAW, mkt.AWAY, mkt.OVER_25, mkt.UNDER_25)

CUP_PHASE = "cup_training"


def _league_of_label(label: str) -> str:
    """Cup labels are already framework league names."""
    return label


def _event_date(ev: dict) -> Optional[str]:
    ct = ev.get("commence_time") or ""
    return ct[:10] if len(ct) >= 10 else None


def log_cup_legs(log: CLVLog, league: str, fixtures: list,
                 odds_index: Optional[dict] = None,
                 now: Optional[datetime.datetime] = None) -> tuple[int, list[str]]:
    """Log paper legs on every fixture of one cup competition, TODAY only.

    `fixtures` are the score-feed events (dicts with home_team/away_team/
    commence_time) OR FixtureOdds. For each fixture: O1.5 always (outcome
    evidence) + each priced market where a real price exists. When no
    `odds_index` is passed and the league has an odds sport key, the prices
    are fetched (cached). Returns (logged, flags). Idempotent: a
    (fixture, market, match_date) already logged is skipped.
    """
    flags: list[str] = []
    if not fixtures:
        return 0, flags
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date().isoformat()

    # Build a (home, away) -> price map when the caller did not pass one.
    if odds_index is None:
        odds_index = {}
        comp = CUP_COMPETITIONS.get(league)
        if comp and comp.get("odds"):
            try:
                price_fxs, oflags = odds.fetch_odds(league)
                odds_index = odds.index_by_fixture(price_fxs)
                flags += oflags
            except Exception as e:
                flags.append(f"{league}: prices unavailable ({e}) — "
                             f"O1.5 outcome legs only")

    # Already-logged keys so a repeated call never duplicates legs.
    already = {(l.fixture, l.market, l.match_date) for l in log.legs
               if l.phase == CUP_PHASE and l.league == league}

    logged = 0
    for fx in fixtures:
        if isinstance(fx, dict):  # score-feed event (odds-API names)
            home = odds.map_team(league, (fx.get("home_team") or "").strip())
            away = odds.map_team(league, (fx.get("away_team") or "").strip())
            kickoff = fx.get("commence_time") or fx.get("date") or ""
            quote = odds_index.get((home, away))
        else:  # FixtureOdds
            home, away = fx.home_team, fx.away_team
            kickoff = fx.kickoff_utc
            quote = odds_index.get((home, away)) or fx
        if not home or not away or not kickoff:
            continue
        match_date = kickoff[:10]
        if match_date != today:
            continue

        def _log(market: str, entry: Optional[float]):
            nonlocal logged
            key = (f"{home} v {away}", market, match_date)
            if key in already:
                return
            already.add(key)
            # model_prob=None on purpose: the monitor does not run the DC
            # model, and a fabricated probability would poison the engine's
            # hit-vs-model residual. These legs carry hit + CLV evidence
            # only; the model-vs-reality comparison lives in the board
            # predictions (which _predictions_from_board prices properly).
            log.log_entry(league=league, fixture=key[0], market=market,
                          model_prob=None, entry_odds=entry,
                          entry_capture_path="CL-LIVE" if entry else "NONE",
                          phase=CUP_PHASE, match_date=match_date)
            logged += 1

        # O1.5 baseline — outcome evidence, no price (never estimated).
        _log(mkt.OVER_15, None)
        # Priced markets where the feed actually quotes them.
        if quote is not None:
            for market in PRICED_LEGS:
                q = mkt.quote(market, quote)
                if q is not None and q.available:
                    _log(market, q.price)

    if logged:
        flags.append(f"{league}: logged {logged} cup-training paper leg(s) "
                     f"on {len(fixtures)} fixture(s)")
    return logged, flags


def settle_cup_legs(log: CLVLog, brain, league: str, events: list,
                    ) -> tuple[int, list[str]]:
    """Settle completed cup events into the CLV log. Returns (settled, flags).

    The brain's `legs` mirror (clv/clv_log.json, full-refresh via
    sync_legs) carries the settled hit + CLV, and calibration_by_market
    reads it by phase — so the brain learns WITHOUT a fabricated model
    probability (predictions.model_prob is NOT NULL, and the monitor does
    not run the DC model; cup legs are honest hit/CLV evidence, not model
    predictions). Never settles a leg that does not exactly match (home,
    away, kickoff DATE); never overwrites a settled leg."""
    flags: list[str] = []
    pending = [l for l in log.legs if l.phase == CUP_PHASE and l.league == league
               and l.hit is None and l.match_date]
    if not pending:
        return 0, flags

    by_fixture = {}
    for leg in pending:
        home, _, away = leg.fixture.partition(" v ")
        by_fixture.setdefault((home.strip(), away.strip(), leg.match_date), []).append(leg)

    settled = 0
    for ev in events:
        if not ev.get("completed"):
            continue
        scores = sorted(ev.get("scores") or [], key=lambda s: s.get("position", 0))
        if len(scores) < 2:
            continue
        fthg, ftag = int(scores[0]["score"]), int(scores[1]["score"])
        home, away = odds.map_team(league, ev.get("home_team") or ""), \
                     odds.map_team(league, ev.get("away_team") or "")
        if not home or not away:
            continue
        match_date = _event_date(ev)
        legs = by_fixture.get((home, away, match_date))
        if not legs:
            continue
        for leg in legs:
            hit = mkt.settle(leg.market, fthg, ftag)
            if hit is None:
                continue
            log.log_result(leg.leg_id, ft_result=f"{fthg}-{ftag}", hit=hit)
            settled += 1
    if settled:
        flags.append(f"{league}: settled {settled} cup-training leg(s)")
    return settled, flags
