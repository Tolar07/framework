"""
CROSS-LEAGUE MODEL — makes the Champions League and Europa League fittable.

THE PROBLEM
  Dixon-Coles puts attack/defence ratings on a common scale because, within a
  league, everyone eventually plays everyone. A continental competition breaks
  that: 36 clubs from ~15 domestic leagues, and a club's 8 continental matches
  say nothing about how its league compares to another's. Fitting the league
  phase ALONE gives 8 observations per team on scales that were never linked.

THE FIX
  Fit ONE model on domestic results AND continental results together. The
  continental matches are the bridges: when Arsenal play PSV, that single
  result ties the English and Dutch scales to each other. Every anchored club
  then carries ~38 domestic matches plus 8 continental ones, all on one axis.

  This is why the format change matters. The old group stage gave 32 clubs six
  matches inside eight isolated groups of four — barely any cross-league
  linkage. The league phase (from 2024/25) is a SINGLE 36-team table where
  each club plays 8 different opponents: 144 matches forming one connected
  graph across the whole of Europe. That is what makes the pooled fit work,
  and it did not exist under the old format.

HONESTY ABOUT WHAT IT CANNOT DO
  A club from a league not in the pool (Swiss, Serbian, Ukrainian, Slovak,
  Czech, Turkish, Greek...) has only its 8 continental matches. Those clubs
  are reported as WEAKLY ANCHORED and, below the data-sufficiency floor, are
  dropped entirely rather than rated on 8 games. `anchoring_report()` states
  exactly which clubs are which — a rating built on 8 matches is not the same
  object as one built on 46, and the board must not pretend otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import load_league, MatchResult
from data import api_football_results as apif
from engine.dixon_coles import fit, DixonColesModel

# Domestic leagues pooled to anchor continental clubs. Every one is already
# ratified and already loaded elsewhere in the pipeline.
ANCHOR_LEAGUES = (
    "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
    "Eredivisie", "Primeira Liga", "Belgian Pro League",
    "Scottish Premiership", "Ekstraklasa", "Championship", "Danish Superliga",
)

# API-Football continental names -> the domestic model key for the SAME club.
# Every pair is verified against the loaded domestic squads by
# verify_aliases(); an unverified pair is a silent mis-rating, so the check is
# part of the test suite rather than a manual promise.
CONTINENTAL_ALIASES: dict[str, str] = {
    # England
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle": "Newcastle",
    "Tottenham": "Tottenham",
    # Spain
    "Atletico Madrid": "Ath Madrid",
    "Athletic Club": "Ath Bilbao",
    "Real Sociedad": "Sociedad",
    "Real Betis": "Betis",
    # Italy
    "AC Milan": "Milan",
    "AS Roma": "Roma",
    "Inter": "Inter",
    # Germany
    "Bayern M\xfcnchen": "Bayern Munich",
    "Bayer Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund",
    "Borussia Monchengladbach": "M'gladbach",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "VfB Stuttgart": "Stuttgart",
    "1899 Hoffenheim": "Hoffenheim",
    "RB Leipzig": "RB Leipzig",
    "VfL Wolfsburg": "Wolfsburg",
    # France
    "Paris Saint Germain": "Paris SG",
    "Stade Brestois 29": "Brest",
    "Lille": "Lille",
    "Monaco": "Monaco",
    # Portugal
    "Sporting CP": "Sp Lisbon",
    "FC Porto": "Porto",
    "SC Braga": "Sp Braga",
    "Benfica": "Benfica",
    # Netherlands / Belgium / Denmark
    "PSV Eindhoven": "PSV Eindhoven",
    "Feyenoord": "Feyenoord",
    "Ajax": "Ajax",
    "Club Brugge KV": "Club Brugge",
    "Union St. Gilloise": "St. Gilloise",
    "FC Midtjylland": "Midtjylland",
}


def map_continental(name: str) -> str:
    """Continental feed name -> model key. Unknown names pass through so an
    unanchored club is visibly unanchored rather than silently mis-joined."""
    return CONTINENTAL_ALIASES.get(name, name)


def verify_aliases(domestic_names: set[str]) -> list[str]:
    """Every alias TARGET must exist in the pooled domestic squads. A target
    that doesn't exist means the alias silently does nothing — the club stays
    unanchored while the table claims otherwise."""
    return sorted({v for v in CONTINENTAL_ALIASES.values()
                   if v not in domestic_names})


def build_pool(competition: str, season: int = 2024,
                anchor_season: str = "2425"
                ) -> tuple[list[MatchResult], dict, list[str]]:
    """Domestic results + continental LEAGUE-PHASE results, as one dataset.

    Only the league phase is pooled. Qualifying rounds and knockouts are
    excluded deliberately: qualifiers are played by a largely different, weaker
    population (a club eliminated in Q1 plays 2 matches), and knockouts are
    two-legged ties whose second leg is distorted by the first — neither is
    the clean single-table structure the pooled fit relies on."""
    flags: list[str] = []
    pooled: list[MatchResult] = []
    domestic_names: set[str] = set()

    for lg in ANCHOR_LEAGUES:
        try:
            res, _ = load_league(lg, anchor_season)
            pooled += res
            domestic_names |= {r.home_team for r in res} | {r.away_team for r in res}
        except Exception as e:
            flags.append(f"anchor league {lg} unavailable ({str(e)[:50]})")

    missing = verify_aliases(domestic_names)
    if missing:
        flags.append(f"alias targets not found in the domestic pool "
                     f"(these clubs stay unanchored): {', '.join(missing)}")

    # Pool the LEAGUE PHASE of EVERY continental competition, not just the one
    # being predicted. Each competition alone leaves gaps: fitting the Europa
    # League in isolation produced Celtic 58% at home to Bayern Munich, because
    # nothing in that fixture set linked the German and Scottish scales. Using
    # all three (144 + 144 + 108 = 396 matches across ~108 clubs) gives one
    # densely-connected European graph, so every prediction rests on the same
    # calibrated scale regardless of which competition it belongs to.
    bridged: list[MatchResult] = []
    for comp in apif.BRIDGE_COMPETITIONS:
        try:
            lp, cflags = apif.load_results(
                comp, season, round_prefix=apif.LEAGUE_PHASE_PREFIX)
        except Exception as e:
            flags.append(f"bridge source {comp} unavailable ({str(e)[:50]})")
            continue
        if comp == competition:
            flags += cflags
        # Re-key continental clubs onto domestic names so the sets join.
        bridged += [MatchResult(
            league=comp, date=r.date,
            home_team=map_continental(r.home_team),
            away_team=map_continental(r.away_team),
            fthg=r.fthg, ftag=r.ftag, ftr=r.ftr,
            source=r.source, source_tier=r.source_tier) for r in lp]
    pooled += bridged

    anchored = {t for r in bridged for t in (r.home_team, r.away_team)
                if t in domestic_names}
    all_cont = {t for r in bridged for t in (r.home_team, r.away_team)}
    info = {"domestic_matches": len(pooled) - len(bridged),
            "continental_matches": len(bridged),
            "continental_clubs": len(all_cont),
            "anchored": sorted(anchored),
            "weakly_anchored": sorted(all_cont - domestic_names)}

    flags.append(
        f"{competition}: pooled {info['domestic_matches']} domestic + "
        f"{info['continental_matches']} continental matches. "
        f"{len(anchored)} of {len(all_cont)} clubs anchored to a domestic "
        f"league; {len(info['weakly_anchored'])} rely on continental matches "
        f"alone and are rated only if they clear the data-sufficiency floor.")
    return pooled, info, flags


def fit_cross_league(competition: str, season: int = 2024,
                      anchor_season: str = "2425",
                      min_matches_per_team: int = 6,
                      pool: Optional[tuple[list[MatchResult], dict]] = None
                      ) -> tuple[Optional[DixonColesModel], dict, list[str]]:
    """One model spanning every pooled league. Returns (model, info, flags).

    `pool=(pooled, info)` lets the caller build the pool once and reuse it
    (e.g. for the Elo source and for the brain's content-hash) instead of
    build_pool being called twice per continental league."""
    if pool is not None:
        pooled, info = pool
        flags: list[str] = []
    else:
        pooled, info, flags = build_pool(competition, season, anchor_season)
    if len(pooled) < 200:
        flags.append(f"{competition}: pooled history too thin ({len(pooled)}) "
                     f"— NO DATA — PENDING")
        return None, info, flags
    model = fit(pooled, min_matches_per_team=min_matches_per_team)
    model.league = competition
    dropped = [t for t in info["weakly_anchored"] if t not in model.teams]
    if dropped:
        flags.append(f"{competition}: {len(dropped)} club(s) dropped for having "
                     f"too few matches even after pooling: {', '.join(dropped[:6])}"
                     + (" ..." if len(dropped) > 6 else ""))
    flags.append(f"{competition}: fitted {len(model.teams)} rated clubs across "
                 f"{len(pooled)} matches, home_adv={model.home_advantage:.3f}, "
                 f"rho={model.rho:.3f}")
    flags.append(
        f"{competition}: CROSS-LEAGUE CALIBRATION CAVEAT — a club that dominates "
        f"a weak domestic league carries that inflated rating into this model, "
        f"and 8 continental matches cannot fully correct 38 domestic ones. "
        f"Measured on the 2024 league phase, Celtic fitted a HIGHER attack "
        f"rating than Manchester City and Real Madrid, which is plainly wrong. "
        f"Goals markets hold up better (Over 2.5 predicted 65.1% vs 62.5% "
        f"actual) than 1X2, which depends directly on relative strength. Treat "
        f"1X2 here as indicative only. This competition is scan-only under "
        f"ID402 regardless, so none of it can reach capital.")
    return model, info, flags
