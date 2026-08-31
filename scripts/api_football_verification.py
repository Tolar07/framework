#!/usr/bin/env python3
"""
api_football_verification.py — Direct API-Football integration for automated fixture verification
Replaces generic web browsing with direct API execution for result verification and matrix calculations.

Integrated into the framework pipeline:
[Trigger / Daily Result Loop]
         │
         ▼
[api_football_verification.py] ──(x-apisports-key)──► API-Football (v3.football.api-sports.io)
         │
         ▼
[Normalized JSON Output] ──► Result Verification / CLV / Matrix Engine
"""

import os
import sys
import json
import requests
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

API_KEY = os.getenv("API_FOOTBALL_KEY")
if not API_KEY:
    print("ERROR: API_FOOTBALL_KEY environment variable not set")
    print("Get your free key at https://www.api-football.com/")
    sys.exit(1)

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
}

# Rate limiting - free plan: 100 requests/day, 10 requests/minute burst
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 6.0  # seconds between requests to stay within burst limit
DAILY_QUOTA_FLOOR = 20  # Reserve requests to avoid exhausting quota

def _rate_limit():
    """Enforce burst rate limiting (10 requests/minute)"""
    global LAST_REQUEST_TIME
    elapsed = time.time() - LAST_REQUEST_TIME
    if LAST_REQUEST_TIME and elapsed < MIN_REQUEST_INTERVAL:
        sleep_time = MIN_REQUEST_INTERVAL - elapsed
        print(f"Rate limiting: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    LAST_REQUEST_TIME = time.time()

def _check_quota() -> Tuple[int, int]:
    """Check daily quota usage"""
    try:
        _rate_limit()
        response = requests.get(f"{BASE_URL}/status", headers=HEADERS, timeout=10)
        data = response.json()
        requests_info = data.get("response", {}).get("requests", {})
        used = int(requests_info.get("current", 0))
        limit = int(requests_info.get("limit_day", 100))
        return used, max(0, limit - used)
    except Exception as e:
        print(f"Warning: Could not check quota: {e}")
        return 0, 100  # Assume available if check fails

def get_fixture_result(date_str: str, league_id: Optional[int] = None,
                      team_id: Optional[int] = None) -> List[Dict]:
    """
    Get fixture results for a specific date from API-Football

    Args:
        date_str: 'YYYY-MM-DD' format
        league_id: Optional league ID filter
        team_id: Optional team ID filter

    Returns:
        List of fixture dictionaries with normalized structure
    """
    used, remaining = _check_quota()
    if remaining < DAILY_QUOTA_FLOOR:
        print(f"Warning: Daily quota low ({remaining} remaining). Skipping API call.")
        return []

    params = {"date": date_str}
    if league_id:
        params["league"] = league_id
    if team_id:
        params["team"] = team_id

    try:
        _rate_limit()
        response = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("response", []):
            fixture = item["fixture"]
            teams = item["teams"]
            goals = item["goals"]
            score = item["score"]["fulltime"]

            # Only return finished matches (FT) for verification
            if fixture["status"]["short"] != "FT":
                continue

            results.append({
                "fixture_id": fixture["id"],
                "date": fixture["date"][:10],  # YYYY-MM-DD
                "timestamp": fixture["timestamp"],
                "status": fixture["status"]["short"],  # FT, AET, PEN
                "elapsed": fixture["status"]["elapsed"],
                "home_team": teams["home"]["name"],
                "away_team": teams["away"]["name"],
                "goals_home": goals["home"],
                "goals_away": goals["away"],
                "halftime_score": item["score"]["halftime"],
                "fulltime_score": score,
                "venue": fixture["venue"]["name"] if fixture["venue"] else None,
                "referee": fixture["referee"],
                "league_id": fixture["league"]["id"],
                "league_name": fixture["league"]["name"],
                "country": fixture["league"]["country"],
                "season": fixture["league"]["season"],
                "round": fixture["league"]["round"]
            })

        print(f"Retrieved {len(results)} finished fixtures for {date_str}")
        return results

    except requests.exceptions.RequestException as e:
        print(f"Error fetching fixtures: {e}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error parsing response: {e}")
        return []

def get_fixture_statistics(fixture_id: int) -> Optional[Dict]:
    """
    Get detailed statistics for a specific fixture (xG, shots, possession, etc.)

    Args:
        fixture_id: API-Football fixture ID

    Returns:
        Dictionary with statistics or None if failed
    """
    used, remaining = _check_quota()
    if remaining < 5:  # Reserve quota for stats calls
        print(f"Warning: Quota too low for statistics call ({remaining} remaining)")
        return None

    try:
        _rate_limit()
        response = requests.get(
            f"{BASE_URL}/fixtures/statistics",
            headers=HEADERS,
            params={"fixture": fixture_id},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("response"):
            return None

        # Extract statistics for both teams
        stats = {}
        for team_data in data["response"]:
            team_name = team_data["team"]["name"]
            team_stats = {}

            for stat in team_data["statistics"]:
                stat_type = stat["type"]
                stat_value = stat["value"]
                team_stats[stat_type] = stat_value

            stats[team_name] = team_stats

        return stats

    except Exception as e:
        print(f"Error fetching statistics for fixture {fixture_id}: {e}")
        return None

def get_fixture_events(fixture_id: int) -> List[Dict]:
    """
    Get events (goals, cards, substitutions) for a fixture

    Args:
        fixture_id: API-Football fixture ID

    Returns:
        List of event dictionaries
    """
    used, remaining = _check_quota()
    if remaining < 5:
        print(f"Warning: Quota too low for events call ({remaining} remaining)")
        return []

    try:
        _rate_limit()
        response = requests.get(
            f"{BASE_URL}/fixtures/events",
            headers=HEADERS,
            params={"fixture": fixture_id},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        events = []
        for item in data.get("response", []):
            events.append({
                "time": item["time"]["elapsed"],
                "team": item["team"]["name"],
                "player": item["player"]["name"],
                "type": item["type"],  # Goal, Card, Subst, etc.
                "detail": item["detail"]  # Scored by, Yellow Card, etc.
            })

        return events

    except Exception as e:
        print(f"Error fetching events for fixture {fixture_id}: {e}")
        return []

def verify_daily_results(target_date: Optional[str] = None) -> Dict:
    """
    Main verification function for the daily result loop

    Args:
        target_date: YYYY-MM-DD format, defaults to yesterday

    Returns:
        Verification results dictionary
    """
    if not target_date:
        # Default to yesterday for verification
        target_date = (date.today() - timedelta(days=1)).isoformat()

    print(f"Starting API-Football verification for {target_date}")

    # Get finished fixtures for the date
    fixtures = get_fixture_result(target_date)

    if not fixtures:
        return {
            "date": target_date,
            "fixtures_found": 0,
            "verification_complete": False,
            "error": "No finished fixtures found or API error"
        }

    # Enhance fixtures with statistics and events (quota permitting)
    enhanced_fixtures = []
    for fixture in fixtures[:5]:  # Limit to 5 fixtures to conserve quota
        print(f"Processing fixture {fixture['fixture_id']}: {fixture['home_team']} vs {fixture['away_team']}")

        # Get statistics (if quota allows)
        stats = get_fixture_statistics(fixture["fixture_id"])
        if stats:
            fixture["statistics"] = stats

        # Get events (if quota allows)
        events = get_fixture_events(fixture["fixture_id"])
        if events:
            fixture["events"] = events

        enhanced_fixtures.append(fixture)

    # Add remaining fixtures without enhancement
    if len(fixtures) > 5:
        enhanced_fixtures.extend(fixtures[5:])

    return {
        "date": target_date,
        "fixtures_found": len(enhanced_fixtures),
        "fixtures": enhanced_fixtures,
        "verification_complete": True,
        "timestamp": datetime.now().isoformat()
    }

def format_for_pipeline(verification_result: Dict) -> str:
    """
    Format verification results for consumption by the pipeline

    Args:
        verification_result: Output from verify_daily_results()

    Returns:
        Formatted string for pipeline consumption
    """
    if not verification_result["verification_complete"]:
        return f"VERIFICATION FAILED: {verification_result.get('error', 'Unknown error')}"

    lines = [
        f"API-FOOTBALL VERIFICATION RESULTS",
        f"Date: {verification_result['date']}",
        f"Fixtures Found: {verification_result['fixtures_found']}",
        f"Timestamp: {verification_result['timestamp']}",
        "",
        "FIXTURES:"
    ]

    for fixture in verification_result["fixtures"]:
        lines.extend([
            f"  Fixture ID: {fixture['fixture_id']}",
            f"  {fixture['home_team']} {fixture['goals_home']} - {fixture['goals_away']} {fixture['away_team']}",
            f"  Status: {fixture['status']} (Elapsed: {fixture['elapsed']}')",
            f"  League: {fixture['league_name']} ({fixture['country']})",
            f"  Season: {fixture['season']}",
            f"  Round: {fixture['round']}"
        ])

        if "statistics" in fixture:
            lines.append("  Statistics:")
            for team_name, stats in fixture["statistics"].items():
                lines.append(f"    {team_name}:")
                for stat_type, stat_value in stats.items():
                    if stat_value is not None:
                        lines.append(f"      {stat_type}: {stat_value}")

        if "events" in fixture and fixture["events"]:
            lines.append("  Key Events:")
            for event in fixture["events"][:3]:  # Limit to first 3 events
                lines.append(f"    {event['time']}' - {event['team']} {event['type']}: {event['detail']}")

        lines.append("")  # Blank line between fixtures

    return "\n".join(lines)

if __name__ == "__main__":
    import time  # Import here to avoid circular issues

    # Command line interface
    import argparse
    parser = argparse.ArgumentParser(description="API-Football verification for OLP XDV framework")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), defaults to yesterday")
    parser.add_argument("--fixture-id", type=int, help="Get details for specific fixture ID")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    args = parser.parse_args()

    if args.fixture_id:
        # Get specific fixture details
        result = get_fixture_result(args.date or date.today().isoformat())
        fixture = next((f for f in result if f["fixture_id"] == args.fixture_id), None)
        if fixture:
            stats = get_fixture_statistics(args.fixture_id)
            events = get_fixture_events(args.fixture_id)
            fixture["statistics"] = stats
            fixture["events"] = events

            if args.format == "json":
                print(json.dumps(fixture, indent=2))
            else:
                print(json.dumps(fixture, indent=2))  # Fallback to json for detailed view
        else:
            print(f"Fixture {args.fixture_id} not found for date {args.date or 'yesterday'}")
            sys.exit(1)
    else:
        # Daily verification
        verification_result = verify_daily_results(args.date)

        if args.format == "json":
            print(json.dumps(verification_result, indent=2))
        else:
            if not args.quiet:
                print(format_for_pipeline(verification_result))
            else:
                # Machine-readable summary
                print(f"DATE:{verification_result['date']}")
                print(f"COUNT:{verification_result['fixtures_found']}")
                print(f"COMPLETE:{verification_result['verification_complete']}")