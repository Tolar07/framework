"""
Full-slate daily results via API-Football — FT/HT scores + kickoff times for
every whitelisted league (ID416).

WHY
  The daily run needs a complete slate of settled results across ALL 65 leagues
  for retrospective calibration. football-data.co.uk covers ~11 leagues; api-
  football is the workhorse for the rest. This module pulls FT/HT scores and
  kickoff times for a date (or date range), plan-aware: the free key serves
  seasons ≤2024; the current season requires a paid key (gated by
  api_football_plan.is_paid_plan()).

FREE ALTERNATIVE: football-data.org (free tier: 100 req/day, keyless-ish with
  free registration). Provides current-season results for mapped leagues.
  Used as a fallback when api-football free plan blocks current season.

PLAN-AWARE
  Free plan:  only seasons ≤ FREE_TIER_LAST_SEASON (2024) — historical backfill.
  Paid plan:  current season unlocks — the daily scrape becomes live.

  is_paid_plan() fails CLOSED (a probe failure keeps the free gate), so a
  transient error can never silently open the current-season path.

WHAT THIS DELIBERATELY DOES NOT DO
  - No odds (api-football free tier has no historical prices).
  - No fabrication (HR35): a fixture not returned by the API is NO DATA —
    PENDING, never guessed.
  - No cross-source blending here — that happens in the verification gate
    (ID403). This module is the FETCH layer only.

ID404 TIER: T1 (api-football.com, structured/official, ratified 2026-08-03).
           T1 (football-data.org, structured/official, ratified 2026-08-13).

ID416: full_slate_results table in brain/store.py stores these rows.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None

from data.multi_source import SourceNoData
from data.retry import get_protected
from data import api_football_plan
from data import football_data_org_source as fdo
from engine.league_registry import registry, get_api_football_id

API_BASE = "https://v3.football.api-sports.io"
CACHE_DIR = Path(__file__).parent / "cache" / "api_football"
FREE_TIER_LAST_SEASON = 2024


@dataclass(frozen=True)
class SlateResult:
    """One completed fixture from the full-slate pull."""
    league: str
    fixture_date: str       # YYYY-MM-DD
    home_team: str
    away_team: str
    fthg: int
    ftag: int
    ftr: str               # H/D/A
    hthg: int | None = None
    htag: int | None = None
    htr: str | None = None  # H/D/A or None if no HT data
    kickoff_time: str | None = None  # ISO datetime or None
    source: str = "api-football.com"
    source_tier: str = "T1"


def _key() -> str:
    k = os.environ.get("API_FOOTBALL_KEY")
    if not k:
        raise RuntimeError("API_FOOTBALL_KEY not set — cannot fetch full-slate results")
    return k


def _season_for_date(d: date) -> int:
    """Which api-football season year does a date fall in?

    api-football treats a season as the year it STARTS. A match on 2025-08-15
    belongs to season 2025 (the 2025-26 campaign). A match on 2025-01-15
    belongs to season 2024 (the 2024-25 campaign)."""
    return d.year if d.month >= 7 else d.year - 1


def _is_season_accessible(season: int) -> bool:
    """Plan-aware gate: free plan serves ≤2024, paid serves current."""
    if season <= FREE_TIER_LAST_SEASON:
        return True
    return api_football_plan.is_paid_plan()


def _cache_path(league: str, fixture_date: str) -> Path:
    safe = league.replace(" ", "_")
    return CACHE_DIR / f"slate_{safe}_{fixture_date}.json"


def _fetch_date(league: str, fixture_date: str,
                use_cache: bool = True) -> list[SlateResult]:
    """Fetch all completed fixtures for `league` on `fixture_date`.

    Returns a list of SlateResult. Raises SourceNoData if the league has no
    api-football ID or the season is beyond the plan gate. Network/payload
    errors bubble up so callers can flag them."""
    if requests is None:
        raise RuntimeError("requests not installed")

    league_id = get_api_football_id(league)
    if league_id is None:
        raise SourceNoData(f"'{league}' has no api-football league ID")

    d = date.fromisoformat(fixture_date)
    season = _season_for_date(d)
    if not _is_season_accessible(season):
        raise SourceNoData(
            f"season {season} for '{league}' is beyond the free plan "
            f"(ends {FREE_TIER_LAST_SEASON}). Fetching it would return a "
            f"plan error, not data.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(league, fixture_date)
    payload = None
    if use_cache and cache.exists():
        try:
            blob = json.loads(cache.read_text(encoding="utf-8"))
            # 6-hour TTL for live-season, no expiry for completed seasons
            age = time.time() - blob.get("cached_at", 0)
            if season <= FREE_TIER_LAST_SEASON or age < 6 * 3600:
                payload = blob.get("data")
        except (json.JSONDecodeError, OSError):
            payload = None

    if payload is None:
        r = get_protected(
            f"{API_BASE}/fixtures", breaker_name="api_football",
            headers={"x-apisports-key": _key()},
            params={"league": league_id, "season": season,
                    "date": fixture_date},
            timeout=30)
        payload = r.json()
        if payload.get("errors"):
            errs = payload["errors"]
            # API-Football returns plan errors here too
            if isinstance(errs, str) and "Free plan" in errs:
                raise SourceNoData(
                    f"api-football plan error for '{league}' season {season}: "
                    f"{errs}")
            raise RuntimeError(f"API-Football: {errs}")
        cache.write_text(
            json.dumps({"data": payload, "cached_at": time.time()}),
            encoding="utf-8")

    return _parse(payload, league)


def _parse(payload: dict, league: str) -> list[SlateResult]:
    """Extract SlateResult rows from an api-football /fixtures payload."""
    results: list[SlateResult] = []
    skipped = 0
    for item in payload.get("response", []):
        fx = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        htl = item.get("score", {}).get("halftime", {})

        status = fx.get("status", {}).get("short")
        if status != "FT":
            skipped += 1
            continue  # HR15: only 90-minute full-time

        h = teams.get("home", {}).get("name")
        a = teams.get("away", {}).get("name")
        gh = goals.get("home")
        ga = goals.get("away")
        if not h or not a or gh is None or ga is None:
            skipped += 1
            continue  # HR35: incomplete, dropped not guessed

        hthg = htl.get("home")
        htag = htl.get("away")
        htr = None
        if hthg is not None and htag is not None:
            htr = "H" if hthg > htag else ("A" if htag > hthg else "D")

        results.append(SlateResult(
            league=league,
            fixture_date=(fx.get("date") or "")[:10],
            home_team=h.strip(), away_team=a.strip(),
            fthg=int(gh), ftag=int(ga),
            ftr="H" if gh > ga else ("A" if ga > gh else "D"),
            hthg=int(hthg) if hthg is not None else None,
            htag=int(htag) if htag is not None else None,
            htr=htr,
            kickoff_time=fx.get("date"),
        ))
    return results


def fetch_slate(fixture_date: str | date,
                 leagues: list[str] | None = None,
                 use_cache: bool = True) -> tuple[list[SlateResult], list[str]]:
    """Fetch all completed fixtures across the full league pool for a given date.

    Args:
        fixture_date: YYYY-MM-DD string or date object.
        leagues: subset of leagues to scan (default: ALL registry leagues).
        use_cache: cache results to avoid re-fetching on re-runs.

    Returns (results, flags). Flags carry per-league status (skipped, plan
    error, no data). Never raises for an ordinary data gap — those go into flags
    (HR35)."""
    if isinstance(fixture_date, date):
        fixture_date = fixture_date.isoformat()

    league_names = leagues or registry.all_leagues()
    all_results: list[SlateResult] = []
    flags: list[str] = []

    d = date.fromisoformat(fixture_date)
    season = _season_for_date(d)

    for league in league_names:
        # Try api-football first
        try:
            rows = _fetch_date(league, fixture_date, use_cache=use_cache)
            if rows:
                all_results.extend(rows)
            # No flag for empty — only flag if skipped rows or errors.
            continue
        except SourceNoData as e:
            # If free plan blocks current season, try football-data.org fallback
            if "beyond the free plan" in str(e) and league in fdo.COMPETITION_CODES:
                try:
                    fdo_results, fdo_flags = fdo.fetch_current_season_results(
                        league, season, use_cache=use_cache)
                    for mr in fdo_results:
                        # Only include if match date matches the requested date
                        if mr.date == fixture_date:
                            all_results.append(SlateResult(
                                league=league,
                                fixture_date=mr.date,
                                home_team=mr.home_team,
                                away_team=mr.away_team,
                                fthg=mr.fthg,
                                ftag=mr.ftag,
                                ftr=mr.ftr,
                                hthg=None, htag=None, htr=None,  # FDO doesn't provide HT
                                kickoff_time=None,
                                source="football-data.org",
                                source_tier="T1",
                            ))
                    flags.extend(fdo_flags)
                    continue
                except Exception as fe:
                    flags.append(f"{league}: FDO fallback failed ({str(fe)[:60]})")
            flags.append(f"{league}: {e}")
        except Exception as e:
            flags.append(f"{league}: full-slate fetch failed ({str(e)[:80]})")

    return all_results, flags


def fetch_slate_range(start_date: str | date, end_date: str | date,
                      leagues: list[str] | None = None,
                      use_cache: bool = True) -> tuple[list[SlateResult], list[str]]:
    """Fetch all completed fixtures across the full pool for a date range.

    Iterates day-by-day, reusing fetch_slate for each date. Returns
    (deduplicated results, combined flags)."""
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    all_results: list[SlateResult] = []
    all_flags: list[str] = []
    seen: set[tuple[str, str, str, str]] = set()  # (league, date, home, away)

    cur = start_date
    while cur <= end_date:
        rows, flags = fetch_slate(cur, leagues=leagues, use_cache=use_cache)
        for r in rows:
            key = (r.league, r.fixture_date, r.home_team, r.away_team)
            if key not in seen:
                seen.add(key)
                all_results.append(r)
        all_flags.extend(flags)
        cur += timedelta(days=1)

    return all_results, all_flags
