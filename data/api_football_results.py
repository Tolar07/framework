"""
Historical results via API-Football — the fallback history source for leagues
football-data.co.uk does not carry.

WHY
  football-data.co.uk covers domestic leagues in 17 countries and no
  continental competitions. Croatia is absent entirely (verified: /new/CRO.csv
  404s, and /new/CRA.csv is Brazil, not Croatia — the code in the framework's
  own source table does not exist). That left HNL with no history at all.
  HR52 obliges Node 1 to go and source it rather than stop at "no ratified
  source", which is what this module does.

RATIFIED under the Section 12 grant as a T1 structured source, 2026-08-03.

THE STALENESS PROBLEM — READ THIS
  The free API-Football plan serves seasons 2022-2024 only. A model fitted
  here is therefore roughly two years behind: squads have turned over,
  managers have changed, promoted clubs are missing. Every MatchResult this
  module returns is stamped with its season and its age in `source`, and
  callers surface that on the board. A stale model is usable for reference
  scanning; it is NOT calibration-grade, and the framework's own calibration
  doctrine (13.2) forbids treating it as such.

WHAT THIS DELIBERATELY DOES NOT DO
  It carries no odds. API-Football's free tier has no historical prices, so a
  league sourced here can be MODELLED but never CLV-backtested — entry and
  closing prices simply do not exist for it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from data.football_data_source import MatchResult
from data.multi_source import SourceNoData
from data.retry import get_protected
from data import api_football_plan

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / "cache" / "api_football"

# Verified live against API-Football's own directory (name + country, exactly
# one match each). See data/fixtures_source.py for the resolver that found them.
LEAGUE_IDS = {
    "HNL": 210,                 # Croatia — the gap football-data.co.uk leaves
    "Champions League": 2,
    "Europa League": 3,
    # NOT on the ID401 whitelist and NOT a betting surface. Included solely as
    # a source of cross-league BRIDGE matches for engine/cross_league.py — 108
    # league-phase matches linking 36 more clubs across Europe, which sharpens
    # the shared scale every continental prediction rests on. Ratifying it as
    # a competition to bet would be an HR34 whitelist change: Architect-only.
    "Conference League": 848,
}

# Continental competitions whose LEAGUE PHASE supplies cross-league bridges.
BRIDGE_COMPETITIONS = ("Champions League", "Europa League", "Conference League")

# Newest season the free plan will serve. Anything later returns a plan error.
FREE_TIER_LAST_SEASON = 2024


def _key() -> str:
    k = os.environ.get("API_FOOTBALL_KEY")
    if not k:
        raise RuntimeError("API_FOOTBALL_KEY not set — cannot fetch history")
    return k


def season_age_years(season: int) -> int:
    """How stale is this data, in seasons? Reported, never hidden."""
    return max(0, date.today().year - season - 1)


LEAGUE_PHASE_PREFIX = "League Stage"


def load_results(league: str, season: int = FREE_TIER_LAST_SEASON,
                  use_cache: bool = True,
                  round_prefix: Optional[str] = None
                  ) -> tuple[list[MatchResult], list[str]]:
    """Completed matches for a league/season. Returns (results, flags).

    Only FT (full-time) fixtures are returned — HR15's 90-minute basis. A
    fixture that is abandoned, postponed, or decided on penalties is skipped
    and counted, never coerced into a result."""
    flags: list[str] = []
    if requests is None:
        raise RuntimeError("requests not installed")
    if league not in LEAGUE_IDS:
        raise SourceNoData(f"'{league}' has no verified API-Football league ID here.")
    # PLAN-GATED (Architect 2026-08-12): the free plan stops at 2024; a PAID
    # key lifts the guard so the current-season (2025-26) history loads and
    # promoted clubs become rateable through the existing DC/elo machinery.
    # is_paid_plan() fails closed (a probe failure keeps the free gate), so a
    # transient probe error can never silently open the current-season path.
    if season > FREE_TIER_LAST_SEASON and not api_football_plan.is_paid_plan():
        raise SourceNoData(
            f"season {season} is beyond the free plan (ends {FREE_TIER_LAST_SEASON}). "
            f"Fetching it would return a plan error, not data.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{league.replace(' ', '_')}_{season}.json"
    payload = None
    if use_cache and cache.exists():
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            flags.append(f"{league}: history served from cache")
        except (json.JSONDecodeError, OSError):
            payload = None
    if payload is None:
        r = get_protected(
            f"{API_BASE}/fixtures", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"league": LEAGUE_IDS[league], "season": season},
            timeout=30)
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Football: {payload['errors']}")
        cache.write_text(json.dumps(payload), encoding="utf-8")

    results: list[MatchResult] = []
    skipped = 0
    filtered_out = 0
    for item in payload.get("response", []):
        fx, teams, goals = item.get("fixture", {}), item.get("teams", {}), item.get("goals", {})
        # Round filter, for continental competitions. Qualifying rounds are
        # played by a largely different and weaker population (a club knocked
        # out in Q1 appears twice and never again), and knockouts are
        # two-legged ties whose second leg is distorted by the first. Neither
        # belongs in a fit that assumes a single comparable pool.
        if round_prefix and not (item.get("league", {}).get("round") or "").startswith(round_prefix):
            filtered_out += 1
            continue
        if fx.get("status", {}).get("short") != "FT":
            skipped += 1
            continue   # HR15: only 90-minute full-time results
        h, a = teams.get("home", {}).get("name"), teams.get("away", {}).get("name")
        gh, ga = goals.get("home"), goals.get("away")
        if not h or not a or gh is None or ga is None:
            skipped += 1
            continue   # HR35: incomplete record, dropped not guessed
        results.append(MatchResult(
            league=league, date=(fx.get("date") or "")[:10],
            home_team=h.strip(), away_team=a.strip(),
            fthg=int(gh), ftag=int(ga),
            ftr="H" if gh > ga else ("A" if ga > gh else "D"),
            source=f"api-football.com (season {season})", source_tier="T1",
        ))

    age = season_age_years(season)
    if age >= 1:
        flags.append(
            f"{league}: STALE HISTORY — fitted on the {season} season, roughly "
            f"{age} year(s) old. The free API-Football plan stops at "
            f"{FREE_TIER_LAST_SEASON}, so squads, managers and promoted clubs "
            f"have since changed. Usable for reference scanning; NOT "
            f"calibration-grade (master doc 13.2).")
    if filtered_out:
        flags.append(f"{league}: {filtered_out} fixture(s) outside '{round_prefix}' "
                     f"excluded (qualifiers and knockouts are a different population)")
    if skipped:
        flags.append(f"{league}: {skipped} fixture(s) skipped (not full-time or incomplete)")
    flags.append(f"{league}: NO ODDS available from this source — it can be "
                 f"modelled but never CLV-backtested.")
    return results, flags


def is_cross_league(league: str) -> bool:
    """True for competitions where clubs from different domestic leagues meet.

    Dixon-Coles fits attack/defence WITHIN a pool where everyone plays everyone,
    which is what puts the ratings on a common scale. A continental competition
    breaks that: the 2024 Champions League had 79 clubs from ~20 leagues at a
    MEDIAN of 5 matches each (minimum 1), against an engine floor of 4-6. Those
    ratings would be noise on incomparable scales, so a standalone fit here is
    refused rather than published."""
    return league in ("Champions League", "Europa League", "Conference League")
