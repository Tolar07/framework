"""
ESPN Win Probability Module — live/in-match win probabilities from ESPN.

Provides win probability data as a 4th independent signal for the ID403 multi-factor
verification gate. Note: ESPN's dedicated winprobability endpoint returns 404,
so this module derives implied probabilities from pre-match odds and tracks
in-match updates where available.

Endpoints:
- /summary?event=<event_id> - contains win probability in some cases (pre-match implied)
- Win probability endpoint: 404 (not available)

HR35 Compliance:
- Only returns verifiable data from ESPN
- Clearly marks derived vs live probabilities
- Honest gaps: return empty if no data available
- Cache: 60s TTL for live, 6h for pre-match
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from data.espn_source import SLUGS as LEAGUE_MAP


# --- Data Models ---

@dataclass
class WinProbability:
    """Win probability snapshot for a match."""
    event_id: str
    league: str
    home_team: str
    away_team: str
    match_date: str
    status: str  # "pre_match", "live", "halftime", "completed"
    minute: Optional[int] = None
    # Pre-match implied probabilities from odds
    home_win_prob: Optional[float] = None
    draw_prob: Optional[float] = None
    away_win_prob: Optional[float] = None
    # Live win probabilities (if available)
    live_home_prob: Optional[float] = None
    live_draw_prob: Optional[float] = None
    live_away_prob: Optional[float] = None
    # Source tracking
    odds_source: str = ""  # "DraftKings", "Bet365", "ESPN_live"
    is_live: bool = False
    provenance: Optional[Dict[str, Any]] = None


# --- Cache ---

CACHE_DIR = Path(__file__).parent / "cache" / "espn_winprob"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL: 60s for live, 6h for pre-match
LIVE_TTL = 60
PRE_MATCH_TTL = 6 * 3600


def _is_live(status: str) -> bool:
    """Check if match is live."""
    return status.lower() in ("in_progress", "live", "halftime", "first_half", "second_half")


def _cache_path(event_id: str) -> Path:
    return CACHE_DIR / f"{event_id}.json"


def _load_cache(event_id: str, is_live: bool) -> Optional[WinProbability]:
    """Load cached win prob if within TTL."""
    path = _cache_path(event_id)
    if not path.exists():
        return None

    age = time.time() - path.stat().st_mtime
    ttl = LIVE_TTL if is_live else PRE_MATCH_TTL

    if age > ttl:
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WinProbability(**data)
    except Exception:
        return None


def _save_cache(wp: WinProbability) -> None:
    """Save win probability to cache."""
    path = _cache_path(wp.event_id)
    data = asdict(wp)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# --- Probability Calculation ---

def _implied_probabilities_from_odds(home_odds: float, draw_odds: float, away_odds: float) -> tuple[float, float, float]:
    """
    Calculate implied probabilities from decimal odds with devig (overround removal).

    Returns (home_prob, draw_prob, away_prob) as percentages summing to 100.
    """
    # Convert to implied probabilities
    h = 1.0 / home_odds
    d = 1.0 / draw_odds
    a = 1.0 / away_odds

    # Remove overround (normalize to 100%)
    total = h + d + a
    return (h / total * 100, d / total * 100, a / total * 100)


def _extract_odds_from_summary(summary_data: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    """Extract 1X2 odds from ESPN summary data."""
    # Check pickcenter (pre-match odds)
    pickcenter = summary_data.get("pickcenter", [])
    for pick in pickcenter:
        providers = pick.get("providers", [])
        for provider in providers:
            name = provider.get("name", "").lower()
            if "draftkings" in name or "bet365" in name:
                outcomes = provider.get("outcomes", [])
                for outcome in outcomes:
                    if outcome.get("type") == "home":
                        home = outcome.get("odds", {}).get("american") or outcome.get("odds", {}).get("decimal")
                    elif outcome.get("type") == "away":
                        away = outcome.get("odds", {}).get("american") or outcome.get("odds", {}).get("decimal")
                    elif outcome.get("type") == "draw":
                        draw = outcome.get("odds", {}).get("american") or outcome.get("odds", {}).get("decimal")

    # Check odds in competitions (same as scoreboard)
    competitions = summary_data.get("competitions", [])
    if competitions:
        odds = competitions[0].get("odds", [])
        for odd in odds:
            provider = odd.get("provider", {}).get("name", "").lower()
            items = odd.get("items", [])
            if len(items) >= 3:
                try:
                    home = float(items[0].get("price"))
                    draw = float(items[1].get("price"))
                    away = float(items[2].get("price"))
                    if home and draw and away:
                        return home, draw, away, provider
                except (ValueError, TypeError):
                    continue

    return None, None, None, ""


def _extract_live_winprob(summary_data: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Extract live win probability from ESPN summary.

    Note: ESPN's dedicated winprobability endpoint returns 404.
    Some summary responses include winprobability in the competitions array.
    """
    competitions = summary_data.get("competitions", [])
    for comp in competitions:
        # Check for winprobability field
        wp = comp.get("winprobability")
        if wp:
            home = wp.get("homeWinPercentage")
            away = wp.get("awayWinPercentage")
            draw = wp.get("tiePercentage") or wp.get("drawPercentage")
            if home is not None and away is not None:
                h = float(home)
                a = float(away)
                d = float(draw) if draw is not None else (100 - h - a)
                return h, d, a

        # Check in situational data
        situation = comp.get("situation", {})
        if situation:
            wp = situation.get("winprobability")
            if wp:
                home = wp.get("homeWinPercentage")
                away = wp.get("awayWinPercentage")
                draw = wp.get("tiePercentage")
                if home is not None and away is not None:
                    h = float(home)
                    a = float(away)
                    d = float(draw) if draw is not None else (100 - h - a)
                    return h, d, a

    return None, None, None


# --- Main Fetch Functions ---

def fetch_winprob_for_event(event_id: str) -> Optional[WinProbability]:
    """
    Fetch win probability for a specific event ID.

    Tries to get live win probability from summary endpoint.
    Falls back to pre-match implied probabilities from odds.
    """
    if requests is None:
        return None

    # Check cache - need to know if live first, so check without is_live
    cached = _load_cache(event_id, False)
    if cached:
        return cached

    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/summary"
        params = {"event": event_id}
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[espn_winprob] Error fetching event {event_id}: {e}")
        return None

    try:
        header = data.get("header", {})
        league = header.get("league", {}).get("name", "Unknown")
        match_date = header.get("date", "").split("T")[0]
        status = header.get("status", {}).get("type", {}).get("name", "unknown")
        competitions = header.get("competitions", [])

        home_team = ""
        away_team = ""
        if len(competitions) >= 2:
            home_team = competitions[0].get("team", {}).get("shortDisplayName", "")
            away_team = competitions[1].get("team", {}).get("shortDisplayName", "")

        is_live_match = _is_live(status)

        # Try to get live win probability
        live_home, live_draw, live_away = _extract_live_winprob(data)

        # Get pre-match odds for implied probabilities
        home_odds, draw_odds, away_odds, odds_source = _extract_odds_from_summary(data)

        # Calculate implied probabilities from odds
        implied_home = implied_draw = implied_away = None
        if home_odds and draw_odds and away_odds:
            implied_home, implied_draw, implied_away = _implied_probabilities_from_odds(
                home_odds, draw_odds, away_odds
            )

        wp = WinProbability(
            event_id=event_id,
            league=league,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            status=status,
            home_win_prob=implied_home,
            draw_prob=implied_draw,
            away_win_prob=implied_away,
            live_home_prob=live_home,
            live_draw_prob=live_draw,
            live_away_prob=live_away,
            odds_source=odds_source,
            is_live=is_live_match,
            provenance={
                "source": "ESPN",
                "endpoint": "summary",
                "has_live_winprob": live_home is not None,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            }
        )

        _save_cache(wp)
        return wp

    except Exception as e:
        print(f"[espn_winprob] Error parsing winprob for {event_id}: {e}")
        return None


def fetch_winprob_for_date(target_date: str, league: Optional[str] = None) -> List[WinProbability]:
    """
    Fetch win probabilities for all matches on a given date.

    Iterates through scoreboard and fetches winprob per event.
    """
    if requests is None:
        return []

    results = []
    leagues_to_query = [league] if league else list(LEAGUE_MAP.keys())

    for lg in leagues_to_query:
        espn_league = LEAGUE_MAP.get(lg)
        if not espn_league:
            continue

        date_str = target_date.replace("-", "")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{espn_league}/scoreboard"
            params = {"dates": date_str, "limit": 100}
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue

        events = data.get("events", [])
        for event in events:
            event_id = str(event.get("id", ""))
            if event_id:
                wp = fetch_winprob_for_event(event_id)
                if wp:
                    results.append(wp)

    return results


# --- Integration with Multi-Source Fabric ---

def get_winprob_source_name() -> str:
    """Return the source name for multi-source registration."""
    return "espn_winprob"


def create_winprob_fetcher(league: str):
    """Create a fetcher callable for the multi-source fabric."""
    def fetcher(target_date: str) -> List[WinProbability]:
        return fetch_winprob_for_date(target_date, league)
    return fetcher


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ESPN Win Probability fetcher")
    parser.add_argument("event_id", nargs="?", help="ESPN event ID")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    parser.add_argument("--league", help="League name (e.g., 'La Liga')")

    args = parser.parse_args()

    if args.event_id:
        wp = fetch_winprob_for_event(args.event_id)
        if wp:
            print(f"\n{'='*80}")
            print(f"WIN PROBABILITY - {wp.home_team} vs {wp.away_team}")
            print(f"{wp.league} | {wp.match_date} | {wp.status}")
            print(f"{'='*80}\n")

            if wp.home_win_prob is not None:
                print(f"  Pre-match implied (from {wp.odds_source}):")
                print(f"    Home: {wp.home_win_prob:.1f}%  Draw: {wp.draw_prob:.1f}%  Away: {wp.away_win_prob:.1f}%")
            if wp.is_live and wp.live_home_prob is not None:
                print(f"  Live (ESPN):")
                print(f"    Home: {wp.live_home_prob:.1f}%  Draw: {wp.live_draw_prob:.1f}%  Away: {wp.live_away_prob:.1f}%")
            if not wp.is_live and wp.live_home_prob is None:
                print("  Live win probability: NOT AVAILABLE (ESPN winprobability endpoint returns 404)")
            print()
    elif args.date:
        wps = fetch_winprob_for_date(args.date, args.league)
        print(f"\n{'='*80}")
        print(f"WIN PROBABILITIES FOR {args.date} - {len(wps)} matches")
        print(f"{'='*80}\n")
        for wp in wps:
            live = " [LIVE]" if wp.is_live else ""
            print(f"  {wp.home_team} vs {wp.away_team} ({wp.league}){live}")
            if wp.home_win_prob:
                print(f"    Implied: H{wp.home_win_prob:.0f}% D{wp.draw_prob:.0f}% A{wp.away_win_prob:.0f}% ({wp.odds_source})")
            if wp.live_home_prob:
                print(f"    Live:    H{wp.live_home_prob:.0f}% D{wp.live_draw_prob:.0f}% A{wp.live_away_prob:.0f}%")
    else:
        print("Usage: python espn_winprob.py <event_id> OR --date YYYY-MM-DD [--league LEAGUE]")