"""
DOMESTIC CUP MODEL — makes the EFL Cup and its siblings fittable without a key.

THE PROBLEM
  A domestic cup is not a league. Everton, Fleetwood Town and Sheffield United
  meet in the EFL Cup but play their league football in three different
  divisions, so there is no single table that rates all of them. Fitting the
  cup alone gives a club two or three matches against opponents whose scales
  were never linked -- which is no rating at all.

  The framework already solves the continental version of this in
  engine/cross_league.py by pooling domestic leagues with the continental
  matches that bridge them. The domestic-cup case looked unsolvable the same
  way, because football-data.co.uk publishes NO cup results, so there are no
  cup matches to act as bridges. EFL Cup was therefore routed to API-Football,
  which needs API_FOOTBALL_KEY, which is not set -- so in practice every EFL
  Cup fixture came back NO DATA — PENDING.

THE FIX
  The bridges do not have to be cup matches. Promotion and relegation move
  clubs between tiers, so a club relegated from the Premier League appears in
  E0 one season and E1 the next. Pool two seasons of every English tier and
  those movers tie the divisions into one connected graph:

      E0 --6-- E1 --6-- E2 --8-- E3 --4-- EC        (counts as of 2026-09-16)

  2,936 matches across five tiers, and every club in a given cup tie is rated
  on one scale. No API key, no new data source -- football-data.co.uk already
  publishes all five, and four of the five European cups here need no new
  league registrations at all.

HONESTY ABOUT WHAT IT CANNOT DO
  These bridges are WEAKER than the continental ones, and the difference is
  not cosmetic:

  - They are TEMPORAL, not simultaneous. A continental tie links two clubs on
    one night; a promotion bridge links one club to ITSELF a season apart, so
    it carries the assumption that the club's strength is roughly continuous
    across the summer. For a club that was relegated and then rebuilt, that
    assumption is wrong.
  - They are SELECTED, not random. The clubs that cross tiers are exactly the
    best of the lower division and the worst of the upper one, so they sit at
    the extremes of both scales rather than sampling them evenly.
  - Some are THIN. Four movers is enough to connect E3 to EC arithmetically
    and not enough to pin the offset precisely.

  So a cross-tier rating is a real rating, but it is a weaker object than a
  within-league one, and `anchoring_report()` says which is which rather than
  letting the board present them as equivalent. `MIN_TIER_BRIDGES` refuses the
  fit outright when a tier is not connected at all -- an unlinked tier gives
  an arbitrary scale offset, which would read as a huge spurious edge.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult, load_league
from engine.dixon_coles import DixonColesModel, fit

# Which league tiers feed each cup. Every league named here is already in
# config/leagues.json with a football_data id, so no cup needs a source the
# pipeline does not already load.
CUP_FEEDER_LEAGUES: dict[str, tuple[str, ...]] = {
    "EFL Cup":         ("Premier League", "Championship", "League One", "League Two"),
    "FA Cup":          ("Premier League", "Championship", "League One", "League Two",
                        "National League"),
    "Copa del Rey":    ("La Liga", "La Liga 2"),
    "Coppa Italia":    ("Serie A", "Serie B"),
    "DFB-Pokal":       ("Bundesliga", "2. Bundesliga"),
    "Coupe de France": ("Ligue 1", "Ligue 2"),
}

# Seasons pooled. Two is the minimum that can produce a promotion bridge at
# all -- within one season no club appears in two tiers.
DEFAULT_SEASONS: tuple[str, ...] = ("2526", "2627")

# Below this many shared clubs, two adjacent tiers are treated as unconnected
# and the fit is refused. Three is not a statistical claim; it is the point
# below which a single atypical club sets the whole offset between divisions.
MIN_TIER_BRIDGES = 3

# A club needs this many pooled matches to be rated. Higher than the
# dixon_coles default of 4 because a cup pool mixes divisions: a club with a
# handful of matches gets its rating almost entirely from the tier offset
# rather than from its own results.
MIN_MATCHES_FOR_CUP_RATING = 10


def is_domestic_cup(competition: str) -> bool:
    """True when this competition is fittable from pooled league tiers."""
    return competition in CUP_FEEDER_LEAGUES


def _teams(results: list[MatchResult]) -> set[str]:
    return {r.home_team for r in results} | {r.away_team for r in results}


def build_cup_pool(
    cup: str,
    seasons: tuple[str, ...] = DEFAULT_SEASONS,
) -> tuple[list[MatchResult], dict, list[str]]:
    """Pool every feeder tier for `cup`. Returns (results, info, flags).

    Loads each tier for each season and reports which tiers actually arrived.
    A tier that fails to load is flagged rather than silently skipped -- losing
    a division from the pool silently is how a club ends up unrated for no
    visible reason.
    """
    if cup not in CUP_FEEDER_LEAGUES:
        raise ValueError(
            f"'{cup}' is not a domestic cup this module knows. Known: "
            f"{', '.join(sorted(CUP_FEEDER_LEAGUES))}"
        )

    flags: list[str] = []
    pooled: list[MatchResult] = []
    by_tier: dict[str, set[str]] = {}
    per_tier_counts: dict[str, int] = {}

    for tier in CUP_FEEDER_LEAGUES[cup]:
        tier_results: list[MatchResult] = []
        for season in seasons:
            try:
                res, rflags = load_league(tier, season)
            except Exception as e:
                flags.append(f"{cup}: {tier} {season} failed to load "
                             f"({type(e).__name__}: {str(e)[:60]})")
                continue
            flags += rflags or []
            tier_results.extend(res or [])
        if not tier_results:
            flags.append(f"{cup}: {tier} contributed 0 matches — pool is "
                         f"missing a division")
            continue
        pooled.extend(tier_results)
        by_tier[tier] = _teams(tier_results)
        per_tier_counts[tier] = len(tier_results)

    bridges = _tier_bridges(CUP_FEEDER_LEAGUES[cup], by_tier)
    info = {
        "cup": cup,
        "seasons": list(seasons),
        "tiers": list(by_tier),
        "matches_per_tier": per_tier_counts,
        "n_matches": len(pooled),
        "n_teams": len(_teams(pooled)),
        "bridges": bridges,
    }
    return pooled, info, flags


def _tier_bridges(order: tuple[str, ...], by_tier: dict[str, set[str]]) -> dict:
    """Shared clubs between each ADJACENT pair of tiers.

    Only adjacent pairs matter: promotion and relegation move a club one
    division at a time, so E0 and E2 share clubs only by way of E1. Checking
    adjacency is what verifies the chain is connected end to end.
    """
    out: dict[str, dict] = {}
    present = [t for t in order if t in by_tier]
    for upper, lower in zip(present, present[1:]):
        shared = sorted(by_tier[upper] & by_tier[lower])
        out[f"{upper} <-> {lower}"] = {"count": len(shared), "clubs": shared}
    return out


def check_connected(info: dict) -> tuple[bool, list[str]]:
    """Is every adjacent tier pair linked by enough movers to fit as one pool?

    Refusing here is the point. Dixon-Coles will happily fit a disconnected
    graph and return numbers; the scale offset between two unlinked components
    is then arbitrary, and an arbitrary offset reads downstream as an enormous
    edge on every fixture that crosses it.
    """
    problems = []
    for pair, data in (info.get("bridges") or {}).items():
        if data["count"] < MIN_TIER_BRIDGES:
            problems.append(
                f"{pair}: only {data['count']} shared club(s), need "
                f"{MIN_TIER_BRIDGES} — these tiers are not linked, so their "
                f"relative scale would be arbitrary"
            )
    if len(info.get("tiers") or []) < 2:
        problems.append("fewer than two tiers loaded — nothing to bridge")
    return (not problems), problems


def fit_domestic_cup(
    cup: str,
    pool: tuple[list[MatchResult], dict] | None = None,
    seasons: tuple[str, ...] = DEFAULT_SEASONS,
    half_life_days: float | None = 365.0,
) -> tuple[DixonColesModel | None, dict, list[str]]:
    """Fit one Dixon-Coles model across the cup's feeder tiers.

    Returns (model, info, flags); model is None when the pool is not fit to
    fit, which the caller must surface as NO DATA — PENDING rather than fall
    back to anything.

    Time decay is ON by default here, unlike the dixon_coles default. A cup
    pool deliberately spans two seasons, so the older season is a season out of
    date; weighting it down is what keeps a club's rating tracking its current
    division rather than the one it was in last year.
    """
    flags: list[str] = []
    if pool is not None:
        pooled, info = pool
    else:
        pooled, info, pflags = build_cup_pool(cup, seasons=seasons)
        flags += pflags

    if not pooled:
        flags.append(f"{cup}: pool is empty — NO DATA — PENDING")
        return None, info, flags

    ok, problems = check_connected(info)
    if not ok:
        for p in problems:
            flags.append(f"{cup}: {p}")
        flags.append(f"{cup}: refusing to fit a disconnected pool — "
                     f"NO DATA — PENDING")
        return None, info, flags

    ref_date = max(r.date for r in pooled)
    model = fit(
        pooled,
        min_matches_per_team=MIN_MATCHES_FOR_CUP_RATING,
        half_life_days=half_life_days,
        ref_date=ref_date,
    )
    model.league = cup

    info = dict(info)
    info["n_rated"] = len(model.teams)
    info["ref_date"] = ref_date
    info["half_life_days"] = half_life_days
    return model, info, flags


def anchoring_report(model: DixonColesModel, info: dict) -> dict:
    """Which clubs are solidly rated and which are riding the tier offset.

    A club rated on 12 pooled matches is not the same object as one rated on
    80, and a board that prints both without distinction is overstating what
    it knows. Mirrors cross_league.anchoring_report.
    """
    thin = dict(getattr(model, "thin_teams", {}) or {})
    rated = sorted(getattr(model, "teams", []) or [])
    return {
        "cup": info.get("cup"),
        "n_rated": len(rated),
        "n_dropped_below_floor": len(thin),
        "floor": MIN_MATCHES_FOR_CUP_RATING,
        "dropped": thin,
        "bridges": info.get("bridges"),
        "caveat": (
            "Tiers are linked by clubs that changed division between seasons, "
            "not by matches played between the tiers. The link is real but "
            "temporal and selected — see engine/domestic_cup.py."
        ),
    }
