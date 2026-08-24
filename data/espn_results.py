"""
ESPN Results Module — historical match results + closing odds from ESPN.

Provides completed match data with closing odds (DraftKings primary, Bet365 secondary)
for completed matches. Used as a redundant source for results verification in the
multi-source fabric (data/multi_source.py).

Endpoints used:
- /sports/soccer/scoreboard?dates=YYYYMMDD - daily fixtures (existing espn_source.py)
- /sports/soccer/scoreboard?dates=YYYYMMDD - also returns completed matches with scores
- /sports/soccer/<league>/scoreboard?dates=YYYYMMDD - league-specific scoreboard
- /summary?event=<event_id>&lineups=true - match summary with stats, lineups, odds

HR35 Compliance:
- Skip malformed rows, record skipped count in provenance
- Honest gaps: return empty list if no data available (no fabrication)
- Cache: 6h TTL for live season, 30d for completed seasons
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from data.espn_source import SLUGS

# Season year fallback (current season start year)
_SEASON_YEAR = 2025


# --- Data Models ---

@dataclass
class MatchResult:
    """Completed match result with closing odds."""
    event_id: str
    league: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str  # "completed", "postponed", "cancelled"
    match_date: str  # ISO date YYYY-MM-DD
    # Closing odds (DraftKings primary, Bet365 secondary)
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    odds_source: str = ""  # "DraftKings" or "Bet365"
    # Additional metadata
    home_stats: Optional[Dict[str, Any]] = None
    away_stats: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None


# --- Cache ---

CACHE_DIR = Path(__file__).parent / "cache" / "espn_results"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL: 6h for live season, 30d for completed
LIVE_SEASON_TTL = 6 * 3600
COMPLETED_SEASON_TTL = 30 * 24 * 3600


# ESPN final-status enum values. ESPN reports finished matches as
# STATUS_FULL_TIME (not STATUS_FINAL / STATUS_COMPLETED as older code assumed),
# so the result filter must accept it — otherwise every completed match is
# silently dropped and the verification loop can never settle (HR35 gap).
FINAL_STATUS_NAMES = {
    "STATUS_FINAL", "STATUS_COMPLETED", "STATUS_FULL_TIME",
    "Final", "Completed",
}


def _is_completed(event: Dict[str, Any]) -> bool:
    """True if an ESPN event is a finished match (honest settlement signal)."""
    status_obj = (event.get("status") or {}).get("type") or {}
    # Canonical completion flag ESPN sets on final results.
    if status_obj.get("completed") is True:
        return True
    return status_obj.get("name", "") in FINAL_STATUS_NAMES


def _is_season_completed(league: str, match_date: str) -> bool:
    """Check if a league season is completed by the match date."""
    # Heuristic: if match_date is before typical season start of next year
    # For simplicity, check if match_date is in a completed year
    try:
        match_dt = datetime.fromisoformat(match_date)
        # If match is from previous season (before Aug of current year)
        now = datetime.now()
        if match_dt.year < now.year:
            return True
        if match_dt.year == now.year and match_dt.month < 8:
            # Could be previous season - check if league typically starts in Aug
            # Most European leagues start in Aug
            return True
    except Exception:
        pass
    return False


def _cache_path(league: str, match_date: str) -> Path:
    safe_league = league.replace(" ", "_").replace("/", "_")
    return CACHE_DIR / f"{safe_league}_{match_date}.json"


def _load_cache(league: str, match_date: str) -> Optional[List[MatchResult]]:
    """Load cached results if within TTL."""
    path = _cache_path(league, match_date)
    if not path.exists():
        return None

    age = time.time() - path.stat().st_mtime
    ttl = COMPLETED_SEASON_TTL if _is_season_completed(league, match_date) else LIVE_SEASON_TTL

    if age > ttl:
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [MatchResult(**r) for r in data]
    except Exception:
        return None


def _save_cache(league: str, match_date: str, results: List[MatchResult]) -> None:
    """Save results to cache."""
    path = _cache_path(league, match_date)
    data = [asdict(r) for r in results]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# --- Odds Extraction ---

def _extract_closing_odds(competition: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    """
    Extract closing 1X2 odds from ESPN competition data.

    Priority: DraftKings (primary) > Bet365 (secondary)
    Returns (home_odds, draw_odds, away_odds, source)
    """
    odds = [o for o in competition.get("odds", []) if o]
    if not odds:
        return None, None, None, ""

    # DraftKings is usually first, Bet365 second
    dk_odds = None
    bet365_odds = None

    for odd in odds:
        provider = odd.get("provider", {}).get("name", "").lower()
        items = odd.get("items", [])
        if not items:
            continue
        # 1X2 format: home, draw, away
        if len(items) >= 3:
            home = items[0].get("price") if items[0] else None
            draw = items[1].get("price") if len(items) > 1 else None
            away = items[2].get("price") if len(items) > 2 else None
            if home and draw and away:
                if "draftkings" in provider:
                    dk_odds = (float(home), float(draw), float(away))
                elif "bet365" in provider:
                    bet365_odds = (float(home), float(draw), float(away))

    if dk_odds:
        return (*dk_odds, "DraftKings")
    if bet365_odds:
        return (*bet365_odds, "Bet365")

    # Fallback: use first available
    for odd in odds:
        items = odd.get("items", [])
        if len(items) >= 3:
            try:
                home = float(items[0].get("price")) if items[0] else None
                draw = float(items[1].get("price")) if len(items) > 1 else None
                away = float(items[2].get("price")) if len(items) > 2 else None
                if home and draw and away:
                    provider = odd.get("provider", {}).get("name", "Unknown")
                    return home, draw, away, provider
            except (ValueError, TypeError):
                continue

    return None, None, None, ""


def _extract_team_stats(competitors: List[Dict[str, Any]]) -> tuple[Optional[Dict], Optional[Dict]]:
    """Extract team statistics from competitors array."""
    home_stats = None
    away_stats = None

    for comp in competitors:
        stats = comp.get("statistics", [])
        stat_dict = {}
        for s in stats:
            name = s.get("name", "").lower().replace(" ", "_")
            value = s.get("value") or s.get("displayValue")
            if name and value is not None:
                stat_dict[name] = value

        if comp.get("homeAway") == "home":
            home_stats = stat_dict
        else:
            away_stats = stat_dict

    return home_stats, away_stats


# --- Main Fetch Functions ---

def fetch_results_for_date(target_date: str, league: Optional[str] = None) -> List[MatchResult]:
    """
    Fetch completed match results for a specific date.

    Args:
        target_date: ISO date string (YYYY-MM-DD)
        league: Optional league name to filter (e.g., "La Liga", "Premier League")

    Returns:
        List of MatchResult objects for completed matches
    """
    if requests is None:
        return []

    # Check cache first
    if league:
        cached = _load_cache(league, target_date)
        if cached is not None:
            return cached

    results = []
    skipped = 0

    # Determine which leagues to query
    leagues_to_query = [league] if league else list(LEAGUE_MAP.keys())

    for lg in leagues_to_query:
        espn_league = SLUGS.get(lg)
        if not espn_league:
            continue

        # Query ESPN scoreboard for the date
        date_str = target_date.replace("-", "")
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league}/scoreboard"
        params = {"dates": date_str, "limit": 100}

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[espn_results] Error fetching {lg} for {target_date}: {e}")
            continue

        events = data.get("events", [])
        for event in events:
            try:
                completed_check = _is_completed(event)
                # Only process completed matches
                if not completed_check:
                    continue

                competitions = event.get("competitions", [])
                if not competitions:
                    skipped += 1
                    continue

                comp = competitions[0]
                competitors = comp.get("competitors", [])
                if len(competitors) < 2:
                    skipped += 1
                    continue

                # Identify home/away
                home = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away = next((c for c in competitors if c.get("homeAway") == "away"), None)
                if not home or not away:
                    skipped += 1
                    continue

                home_team = home.get("team", {}).get("shortDisplayName") or home.get("team", {}).get("displayName", "")
                away_team = away.get("team", {}).get("shortDisplayName") or away.get("team", {}).get("displayName", "")
                home_score = int(home.get("score", 0))
                away_score = int(away.get("score", 0))

                # Extract closing odds
                home_odds, draw_odds, away_odds, odds_source = _extract_closing_odds(comp)

                # Extract team stats
                home_stats, away_stats = _extract_team_stats(competitors)

                # Match date from event
                event_date = event.get("date", "").split("T")[0]

                result = MatchResult(
                    event_id=str(event.get("id", "")),
                    league=lg,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=home_score,
                    away_score=away_score,
                    status="completed",
                    match_date=event_date or target_date,
                    home_odds=home_odds,
                    draw_odds=draw_odds,
                    away_odds=away_odds,
                    odds_source=odds_source,
                    home_stats=home_stats,
                    away_stats=away_stats,
                    provenance={
                        "source": "ESPN",
                        "endpoint": "scoreboard",
                        "fetched_at": datetime.utcnow().isoformat() + "Z",
                        "skipped_malformed": skipped,
                    },
                )
                results.append(result)

            except Exception as exc:
                skipped += 1
                continue

    # Save to cache if we queried a specific league
    if league and results:
        _save_cache(league, target_date, results)

    return results


def fetch_results_range(
    start_date: str,
    end_date: str,
    league: Optional[str] = None
) -> List[MatchResult]:
    """
    Fetch completed match results for a date range.

    Args:
        start_date: ISO date string (YYYY-MM-DD)
        end_date: ISO date string (YYYY-MM-DD)
        league: Optional league name to filter

    Returns:
        List of MatchResult objects for completed matches
    """
    all_results = []
    current = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        results = fetch_results_for_date(date_str, league)
        all_results.extend(results)
        current += timedelta(days=1)

    return all_results


def fetch_results_for_league_season(league: str, season: str) -> List[MatchResult]:
    """
    Fetch all completed results for a league season.

    Args:
        league: League name (e.g., "La Liga")
        season: Season string (e.g., "2025-2026" or "2025")

    Returns:
        List of MatchResult objects
    """
    # Determine season date range
    try:
        if "-" in season:
            start_year = int(season.split("-")[0])
        else:
            start_year = int(season)
    except ValueError:
        start_year = _SEASON_YEAR

    # Typical European season: Aug to May
    start_date = f"{start_year}-08-01"
    end_date = f"{start_year + 1}-05-31"

    return fetch_results_range(start_date, end_date, league)


# --- Integration with Multi-Source Fabric ---

def get_results_source_name() -> str:
    """Return the source name for multi-source registration."""
    return "espn_results"


def create_results_fetcher(league: str):
    """Create a fetcher callable for the multi-source fabric."""
    def fetcher(target_date: str) -> List[MatchResult]:
        return fetch_results_for_date(target_date, league)
    return fetcher


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ESPN Results fetcher")
    parser.add_argument("date", nargs="?", help="Target date (YYYY-MM-DD), defaults to yesterday")
    parser.add_argument("--league", help="League name (e.g., 'La Liga')")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"), help="Date range")
    parser.add_argument("--season", help="Season (e.g., '2025-2026')")

    args = parser.parse_args()

    if args.range:
        results = fetch_results_range(args.range[0], args.range[1], args.league)
    elif args.season:
        results = fetch_results_for_league_season(args.league or "La Liga", args.season)
    else:
        target = args.date or (date.today() - timedelta(days=1)).isoformat()
        results = fetch_results_for_date(target, args.league)

    print(f"\n{'='*80}")
    print(f"ESPN RESULTS - {len(results)} matches")
    print(f"{'='*80}\n")

    for r in results:
        odds = f"  1X2: {r.home_odds}/{r.draw_odds}/{r.away_odds} ({r.odds_source})" if r.home_odds else "  No odds"
        print(f"  {r.match_date}  {r.league}")
        print(f"    {r.home_team} {r.home_score} - {r.away_score} {r.away_team}{odds}")
        print()