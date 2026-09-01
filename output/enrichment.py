"""
ENRICHMENT GATE — Fixture enrichment with hard gates for league/kickoff.

ROOT CAUSE FIX: The season string used to key kickoff/league cache lookups was
stale ("2526" for 2025-26 season) while live fixtures were already "2627"
(2026-27). Every lookup missed, falling through to "Unknown League"/"??:??"
placeholders.

Two things get fixed here:
  1. current_season_string() computes the season dynamically from the real
     date, so it can never go stale again without a code change.
  2. enrich_fixture() is a HARD GATE — if kickoff or league genuinely can't
     be resolved (season bug fixed or not, this cache-miss or a future
     different one), the fixture is DROPPED from all output instead of
     shipping with placeholders. This enforces Hard Gates 1 & 2 from
     OFFICIAL_PIPELINE_OUTPUT_SPEC.md in code.

Wire enrich_fixture() into wherever produce_bet.py and heartbeat.py currently
build a fixture record before it's handed to any renderer — nothing
downstream should ever see a fixture this function didn't approve.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

logger = logging.getLogger("enrichment")

# European domestic season convention: rolls over mid-year. If your
# leagues' actual rollover month differs, adjust ROLLOVER_MONTH — but
# this being a single named constant, computed from the real date, is
# the whole point: it can never silently drift the way a hardcoded
# "2526" string sitting in code can.
ROLLOVER_MONTH = 7  # July — adjust if your deploy leagues differ


def current_season_string(reference_date: date | None = None) -> str:
    """
    Returns e.g. "2627" for any date from July 2026 through June 2027.
    No hardcoding, no manual annual update — it's derived from the date
    every time it's called, so it can't go stale the way a literal
    "2526" string sitting in code can.
    """
    d = reference_date or date.today()
    if d.month >= ROLLOVER_MONTH:
        start_year = d.year
    else:
        start_year = d.year - 1
    end_year = start_year + 1
    return f"{str(start_year)[-2:]}{str(end_year)[-2:]}"


def cache_kickoff(
    fixture_key: str,
    cache_lookup_fn: Callable[[str, str], Optional[str]],
    season: str | None = None
) -> Optional[str]:
    """
    Replacement for _cache_kickoff(). cache_lookup_fn is whatever your
    actual cache-read function is (e.g. a dict/DB lookup keyed by
    season+fixture) -- pass it in so this stays a thin, testable wrapper
    rather than needing to know your cache's storage details.

    Returns the real kickoff time string, or None if genuinely not
    found -- NEVER "??:??". None is the honest signal; the caller (see
    enrich_fixture below) decides what to do with a miss.
    """
    season = season or current_season_string()
    result = cache_lookup_fn(season=season, fixture_key=fixture_key)
    if result is None:
        logger.warning(
            "kickoff cache miss for %s (season=%s) — check whether this "
            "season string actually matches what's in the cache, and "
            "whether the fixture is even in this season's data.",
            fixture_key, season,
        )
    return result


def extract_league(
    fixture_key: str,
    cache_lookup_fn: Callable[[str, str], Optional[str]],
    season: str | None = None
) -> Optional[str]:
    """Same pattern as cache_kickoff, for league name resolution."""
    season = season or current_season_string()
    result = cache_lookup_fn(season=season, fixture_key=fixture_key)
    if result is None:
        logger.warning(
            "league lookup miss for %s (season=%s)", fixture_key, season
        )
    return result


@dataclass
class EnrichedFixture:
    fixture_key: str
    home: str
    away: str
    league: str
    kickoff: str


def enrich_fixture(
    fixture_key: str,
    home: str,
    away: str,
    kickoff_lookup_fn: Callable[[str, str], Optional[str]],
    league_lookup_fn: Callable[[str, str], Optional[str]],
) -> EnrichedFixture | None:
    """
    THE GATE. Call this for every fixture before it reaches ANY renderer
    (board, heartbeat, acca legs). Returns None if kickoff or league
    can't be resolved -- the fixture is held back from every output,
    full stop, regardless of which underlying cause produced the miss.

    This is what makes Hard Gates 1 & 2 real instead of aspirational:
    it's no longer possible for a downstream renderer to receive a
    fixture with missing league/kickoff and print a placeholder,
    because it never receives that fixture at all.
    """
    season = current_season_string()
    kickoff = cache_kickoff(fixture_key, kickoff_lookup_fn, season)
    league = extract_league(fixture_key, league_lookup_fn, season)

    if kickoff is None or league is None:
        logger.warning(
            "DROPPED fixture %s v %s — missing %s. Held back from all "
            "output rather than shipped with a placeholder.",
            home, away,
            "kickoff and league" if kickoff is None and league is None
            else "kickoff" if kickoff is None else "league",
        )
        return None

    return EnrichedFixture(fixture_key, home, away, league, kickoff)


def log_current_season_on_startup() -> None:
    """
    Call this once when the pipeline starts each run, so the season
    string being used is visible in the log every single day -- if it
    ever silently drifts wrong again, it's a one-line log diff to spot
    instead of a mystery investigated after the fact.
    """
    season = current_season_string()
    logger.info("Pipeline run using season string: %s (computed from today's date)", season)
    print(f"[enrichment] Using season: {season}")