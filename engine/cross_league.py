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
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data import api_football_results as apif
from data.football_data_source import MatchResult, load_league
from engine import elo as elo_engine
from engine.dixon_coles import DixonColesModel, fit

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
    # Champions League 2026-08-18 scan flags — exact accent/case-fold match (score 1.00)
    "LASK Linz": "Lask Linz",
    # Viking FK (Norway) — continental feed name -> domestic key
    "Viking FK": "Viking",
}


def map_continental(name: str) -> str:
    """Continental feed name -> model key. Unknown names pass through so an
    unanchored club is visibly unanchored rather than silently mis-joined."""
    return CONTINENTAL_ALIASES.get(name, name)


def _fold_name(s: str) -> str:
    """Accent- and case-fold for matching ('Fenerbahçe' -> 'fenerbahce')."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def suggest_aliases(feed_name: str, pool_teams: list[str],
                    topk: int = 3, cutoff: float = 0.6) -> list[tuple[str, float]]:
    """Candidates in the fitted pool that an unknown feed name most likely IS.

    Used when a fixtures feed returns a team the model doesn't know (a new
    qualifying entrant, a renamed club, a different transliteration). An exact
    accent/case-folded match wins outright (score 1.0); otherwise difflib fuzzy
    matches against the pool. Returns [(pool_name, similarity)] best-first,
    empty when nothing clears the cutoff.

    This is a SUGGESTION for a human to verify — never applied automatically.
    An unverified alias is a silent mis-rating (the same bright line
    verify_aliases() enforces on CONTINENTAL_ALIASES)."""
    folded = _fold_name(feed_name)
    exact = [t for t in pool_teams if _fold_name(t) == folded]
    if exact:
        return [(exact[0], 1.0)]
    pool_folded = {_fold_name(t): t for t in pool_teams}
    import difflib
    candidates = difflib.get_close_matches(folded, list(pool_folded.keys()),
                                           n=topk, cutoff=cutoff)
    out = []
    for c in candidates:
        score = round(difflib.SequenceMatcher(None, folded, c).ratio(), 3)
        out.append((pool_folded[c], score))
    return out


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


# ---------------------------------------------------------------------------
# ELO BLEND WEIGHT (Phase 3.2) — how much continental matches should count.
#
# WHY A WEIGHT AT ALL
#   Elo is structurally cross-league: a Dutch club beating an English one moves
#   both ratings on one scale, so the pooled fit makes continental 1X2
#   possible. But every match moves ratings by the SAME K-FACTOR, so a club's
#   38 domestic results speak exactly as loudly as its 8 European ones. When a
#   continental fixture is being priced, the European matches are the DIRECT
#   evidence of cross-league strength — the domestic ones built the rating on a
#   scale that was never linked to the opponent's. The pool's own caveat above
#   (Celtic rated above Real Madrid) is exactly this: 38 weak-league domestic
#   matches drowning the 8 European ones that would correct them.
#
# THE BLEND
#   Weight every continental match in the pooled Elo by a constant `w` relative
#   to 1.0 for domestic ones (engine/elo.py rate_through(match_weight=...)).
#   w > 1 lets the European record speak louder exactly where it is the
#   strongest evidence. This is NOT a new rating system — it is the same Elo,
#   with the same leakage-free walk, just reading the direct evidence harder.
#
# HOW THE WEIGHT IS CHOSEN (honesty, HR35)
#   - EVIDENCE-GATED: needs >= MIN_BLEND_MATCHES continental matches in the
#     pool, or the engine is untouched.
#   - PROVEN OUT-OF-SAMPLE: every candidate w is scored by Brier on the pooled
#     continental matches, each predicted from ratings that existed BEFORE the
#     match (the leak-free scorer hook in rate_through). The w with the lowest
#     Brier wins.
#   - NO-GAIN -> IDENTITY: unless the winner beats w=1.0 by MIN_BLEND_IMPROVEMENT
#     Brier points, the weight is left at 1.0 and the model is exactly the
#     classic engine. The optimiser can never force a change the evidence
#     didn't earn.
#   - LOUD: fit_blend_weight returns a flag stating whether the weight was
#     applied, and the orchestrator surfaces it on the board.
# ---------------------------------------------------------------------------

# The candidate weights for the continental-match multiplier, 0.5..3.0 in
# half-steps. 1.0 (the classic engine) is always on the grid, so identity is
# always a candidate rather than an assumption.
BLEND_WEIGHT_GRID: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
# A pool needs at least this many continental matches before ANY weight is fit.
MIN_BLEND_MATCHES = 50
# Brier points the best weight must beat w=1.0 by (0.005 = half a point).
MIN_BLEND_IMPROVEMENT = 0.005


def continental_weight(w: float) -> Callable:
    """A match_weight callable for elo.rate_through: maps each pooled match to
    its update weight — `w` for a continental bridge match, 1.0 for a domestic
    one. w=1.0 reproduces the classic engine exactly."""
    def _weight(r) -> float:
        return w if r.league in apif.BRIDGE_COMPETITIONS else 1.0
    return _weight


def _weighted_continental_brier(pooled: list[MatchResult], w: float,
                                burn_in: int) -> tuple[float | None, int]:
    """Out-of-sample 1X2 Brier on the continental matches of a pooled graph,
    rated with continental matches weighted `w` relative to domestic ones.

    Uses the leak-free scorer hook in rate_through: every continental match is
    scored from ratings built only from matches BEFORE it, so the weight is
    judged exactly as it will be used. Returns (mean_brier, n_scored); brier is
    None when no continental match was scoreable (both clubs too thin)."""
    total = 0.0
    n = 0

    def _score(model: elo_engine.EloModel, r: MatchResult) -> None:
        nonlocal total, n
        if r.league not in apif.BRIDGE_COMPETITIONS:
            return  # only continental matches are the evidence under test
        probs = model.probabilities(r.home_team, r.away_team)
        if probs is None:
            return  # a too-thin club gets no score, exactly as on the board
        target = {"H": (1.0, 0.0, 0.0), "D": (0.0, 1.0, 0.0),
                  "A": (0.0, 0.0, 1.0)}[r.ftr]
        total += sum((p - y) ** 2 for p, y in zip(probs, target, strict=True))
        n += 1

    elo_engine.rate_through(pooled, burn_in=burn_in,
                            match_weight=continental_weight(w), scorer=_score)
    return (total / n if n else None), n


def fit_blend_weight(pooled: list[MatchResult],
                     grid: tuple[float, ...] = BLEND_WEIGHT_GRID,
                     burn_in: int | None = None,
                     min_matches: int = MIN_BLEND_MATCHES,
                     min_improvement: float = MIN_BLEND_IMPROVEMENT,
                     ) -> tuple[float, dict]:
    """Find the continental-match weight that minimises out-of-sample Brier.

    Returns (w, info). `info` always carries `applied` and a `flag` so the
    caller can report honestly: the weight is 1.0 (the classic engine, applied
    or not) unless a grid point provably beats it — never a fabricated change.
    The grid always contains 1.0, so identity is a candidate, not a fallback.
    """
    if burn_in is None:
        burn_in = elo_engine.BURN_IN_PASSES
    n_cont = sum(1 for r in pooled if r.league in apif.BRIDGE_COMPETITIONS)
    info: dict = {"n_continental": n_cont, "grid": list(grid), "applied": False}
    if n_cont < min_matches:
        info["flag"] = (f"ELO blend weight: only {n_cont} continental matches "
                        f"(< {min_matches}) — NO DATA — PENDING")
        return 1.0, info

    scored: dict[float, tuple[float | None, int]] = {
        w: _weighted_continental_brier(pooled, w, burn_in) for w in grid}
    info["evaluated"] = scored
    n = max((n for _b, n in scored.values()), default=0)
    info["n_scored"] = n
    if n < 1:
        info["flag"] = ("ELO blend weight: no continental match was scoreable "
                        "(every club too thin) — NO DATA — PENDING")
        return 1.0, info

    base = scored[1.0][0]
    best_w = min((w for w in grid if scored[w][0] is not None),
                 key=lambda w: scored[w][0])   # ties -> smallest w
    best = scored[best_w][0]
    if best_w == 1.0 or best is None or best >= base - min_improvement:
        info["flag"] = (f"ELO blend weight: no evidence a weight helps "
                        f"(Brier {base:.4f} at w=1.0; best {best_w} "
                        f"{best:.4f}) — left at 1.0")
        return 1.0, info

    info["applied"] = True
    info["w"] = best_w
    info["brier_w1"] = base
    info["brier_best"] = best
    info["improvement_pp"] = round((base - best) * 100, 2)
    info["flag"] = (f"ELO blend weight w={best_w} applied — continental "
                    f"matches count {best_w}x domestic (Brier "
                    f"{base:.4f} -> {best:.4f} on {n} out-of-sample "
                    f"continental matches, +{info['improvement_pp']}pp)")
    return best_w, info
