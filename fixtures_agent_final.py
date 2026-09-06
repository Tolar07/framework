"""
Final integrated fixtures agent with live SportyBet odds.

This agent:
1. Fetches fixtures from FlashScore (PRIMARY), BBC Sport, LiveScore, Sporting Life
2. Adds live fixtures from SportyBet API
3. Enhances fixtures with live odds from SportyBet when available
4. Applies the same verification logic (>=2 sources) as the original
5. Filters by deploy-eligible whitelist and league calendar
6. Stamps provenance on all fixtures
7. Displays clean output with odds when available

Based on the proven fixtures_agent.py with verified date filtering and verification.
"""
from __future__ import annotations

import sys
import json
import re
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Add project root

# Import ALL existing fixtures agent functions - we reuse the proven logic
from fixtures_agent import (
    LEAGUE_SEASON_START,
    load_whitelist,
    _parse_date,
    check_league_calendar,
    verify_league_fixture,
    _flashscore_line_to_date,
    _find_flashscore_feed,
    fetch_flashscore,
    fetch_livescore,
    fetch_sportinglife,
    fetch_bbc,
    fetch_sportybet_cache,
    _apply_verification,
    print_fixtures,
    main as original_main
)

# Import new components for enhanced verification and data sources
try:
    from verification.fixture_matcher import match_fixtures, SourceFixture, unmatched_report
    FIXTURE_MATCHER_AVAILABLE = True
except Exception as e:
    print(f"[INFO] Fixture matcher not available: {e}")
    FIXTURE_MATCHER_AVAILABLE = False

try:
    from data.apifootball_client import APIFootballClient
    API_FOOTBALL_AVAILABLE = True
except Exception as e:
    print(f"[INFO] API-Football client not available: {e}")
    API_FOOTBALL_AVAILABLE = False

# Import SportyBet live components with error handling
try:
    from booking.sportybet_client import SportyBetClient
    from booking.league_map import SPORTYBET_LEAGUES
    SPORTYBET_AVAILABLE = True
except Exception as e:
    print(f"[INFO] SportyBet live integration not available: {e}")
    SPORTYBET_AVAILABLE = False
    SportyBetClient = None
    SPORTYBET_LEAGUES = {}

# Import API-Football client for structured data
try:
    from data.apifootball_client import APIFootballClient, LEAGUE_ID_MAP
    API_FOOTBALL_AVAILABLE = True
except Exception as e:
    print(f"[INFO] API-Football client not available: {e}")
    API_FOOTBALL_AVAILABLE = False
    APIFootballClient = None
    LEAGUE_ID_MAP = {}


def fetch_sportybet_live_fixtures(today: str) -> List[Dict]:
    """
    Fetch live fixtures from SportyBet API for today.

    Returns fixtures in the same format as other sources.
    """
    if not SPORTYBET_AVAILABLE:
        return []

    rows: List[Dict] = []
    client = None

    try:
        # Conservative settings to prevent hanging
        client = SportyBetClient(timeout=8, delay=0.5)

        # Focus on priority leagues to limit API calls
        priority_leagues = [
            "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
            "Eredivisie", "Primeira Liga", "Belgian Pro League",
            "Scottish Premiership", "Swiss Super League", "Turkish Super Lig"
        ]

        for league_name in priority_leagues:
            if league_name not in SPORTYBET_LEAGUES:
                continue

            try:
                mapping = SPORTYBET_LEAGUES[league_name]
                country = mapping.country
                sb_league = mapping.league

                # Get fixtures for today/tomorrow
                fixtures = client.get_fixtures(country, sb_league, days_ahead=2)

                for fixture in fixtures:
                    if not fixture.kickoff_utc:
                        continue

                    # Check if fixture is for today
                    fixture_date = fixture.kickoff_utc[:10]  # YYYY-MM-DD
                    if fixture_date != today:
                        continue

                    # Format kickoff time
                    kickoff_time = "TBD"
                    if len(fixture.kickoff_utc) >= 16:
                        kickoff_time = fixture.kickoff_utc[11:16]  # HH:MM

                    fixture_data = {
                        "league": league_name,
                        "home": fixture.home_team,
                        "away": fixture.away_team,
                        "kickoff": kickoff_time,
                        "odds_1": None,
                        "odds_x": None,
                        "odds_2": None,
                        "source": "SportyBet live",
                        "kickoff_date": fixture.kickoff_utc,
                        "fixture_id": fixture.fixture_id,
                        "home_team_normalized": fixture.home_team.lower().strip(),
                        "away_team_normalized": fixture.away_team.lower().strip(),
                        "fetched_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                    }

                    # Try to get odds (non-blocking)
                    try:
                        odds_list = client.get_odds(fixture.fixture_id)
                        if odds_list:
                            # Look for 1X2 market
                            for market in odds_list:
                                if market.market in ["1X2", "match_winner", "full_time_result"]:
                                    outcomes = market.outcomes
                                    home_odds = draw_odds = away_odds = None

                                    for outcome_name, odds_value in outcomes.items():
                                        outcome_lower = outcome_name.lower()
                                        if 'home' in outcome_lower or outcome_name == '1':
                                            home_odds = float(odds_value)
                                        elif 'draw' in outcome_lower or outcome_name == 'x':
                                            draw_odds = float(odds_value)
                                        elif 'away' in outcome_lower or outcome_name == '2':
                                            away_odds = float(odds_value)

                                    # Set if we have complete 1X2 odds
                                    if home_odds is not None and draw_odds is not None and away_odds is not None:
                                        fixture_data["odds_1"] = home_odds
                                        fixture_data["odds_x"] = draw_odds
                                        fixture_data["odds_2"] = away_odds
                                        fixture_data["odds_source"] = "SportyBet live"
                                    break  # Found 1X2 market
                    except Exception:
                        pass  # Continue without odds if slow/fails

                    rows.append(fixture_data)

            except Exception as e:
                print(f"[DEBUG] SportyBet live skipped {league_name}: {type(e).__name__}")
                continue

    except Exception as e:
        print(f"[INFO] SportyBet live unavailable: {e}")
    finally:
        if client:
            client.close()

    return rows


def enhance_with_sportybet_odds(today: str, fixtures: List[Dict]) -> List[Dict]:
    """
    Enhance existing fixtures with live SportyBet odds.

    Preserves existing fixtures while adding odds data where possible.
    """
    if not SPORTYBET_AVAILABLE:
        return fixtures

    client = None
    try:
        client = SportyBetClient(timeout=8, delay=0.5)

        # Create lookup: (norm_home, norm_away, date) -> index
        lookup = {}
        for i, fixture in enumerate(fixtures):
            home_key = fixture.get("home_team_normalized", fixture.get("home", "").lower().strip())
            away_key = fixture.get("away_team_normalized", fixture.get("away", "").lower().strip())
            date_key = fixture.get("kickoff_date", today)

            # Store both directions for team order flexibility
            lookup[(home_key, away_key, date_key)] = i
            lookup[(away_key, home_key, date_key)] = i

        # Check each league for odds enhancement
        for league_name in SPORTYBET_LEAGUES.keys():
            try:
                mapping = SPORTYBET_LEAGUES[league_name]
                country = mapping.country
                sb_league = mapping.league

                fixtures_list = client.get_fixtures(country, sb_league, days_ahead=2)

                for sb_fixture in fixtures_list:
                    if not sb_fixture.kickoff_utc:
                        continue

                    # Check if for today
                    sb_date = sb_fixture.kickoff_utc[:10]
                    if sb_date != today:
                        continue

                    sb_home = sb_fixture.home_team.lower().strip()
                    sb_away = sb_fixture.away_team.lower().strip()

                    # Find matching fixture
                    match_index = None
                    key1 = (sb_home, sb_away, today)
                    key2 = (sb_away, sb_home, today)

                    if key1 in lookup:
                        match_index = lookup[key1]
                    elif key2 in lookup:
                        match_index = lookup[key2]

                    # Enhance if match found and no existing odds
                    if match_index is not None and sb_fixture.fixture_id:
                        existing = fixtures[match_index]
                        if existing.get("odds_1") is None:
                            try:
                                odds_list = client.get_odds(sb_fixture.fixture_id)
                                if odds_list:
                                    # Process for 1X2 odds
                                    for market in odds_list:
                                        if market.market in ["1X2", "match_winner", "full_time_result"]:
                                            outcomes = market.outcomes
                                            home_odds = draw_odds = away_odds = None

                                            for outcome_name, odds_value in outcomes.items():
                                                outcome_lower = outcome_name.lower()
                                                if 'home' in outcome_lower or outcome_name == '1':
                                                    home_odds = float(odds_value)
                                                elif 'draw' in outcome_lower or outcome_name == 'x':
                                                    draw_odds = float(odds_value)
                                                elif 'away' in outcome_lower or outcome_name == '2':
                                                    away_odds = float(odds_value)

                                            if home_odds is not None and draw_odds is not None and away_odds is not None:
                                                existing["odds_1"] = home_odds
                                                existing["odds_x"] = draw_odds
                                                existing["odds_2"] = away_odds
                                                existing["odds_source"] = "SportyBet live"
                                            break  # Found 1X2 market
                            except Exception:
                                pass  # Continue without odds if slow/fails
            except Exception as e:
                print(f"[DEBUG] Odds enhancement skipped {league_name}: {type(e).__name__}")
                continue

    except Exception as e:
        print(f"[INFO] Odds enhancement unavailable: {e}")
    finally:
        if client:
            client.close()

    return fixtures


def print_fixtures_with_odds(today: str, all_rows: List[Dict]) -> None:
    """
    Print fixtures with clean formatting, odds, and provenance.

    Maintains all existing filtering and verification logic.
    """
    # Deduplicate by (home, away) - prefer rows with odds
    seen: Dict[str, Dict] = {}
    for r in all_rows:
        key = f"{r.get('home','')}|{r.get('away','')}"
        if key not in seen:
            seen[key] = r
        elif not seen[key].get("odds_1") and r.get("odds_1"):
            seen[key] = r  # Prefer fixture with odds

    # Apply all existing filters
    whitelist = load_whitelist()
    active_leagues, not_started = check_league_calendar(today)

    filtered_rows = []
    for r in seen.values():
        league = r.get("league", "")

        # Whitelist filter
        if league not in whitelist:
            continue

        # League calendar filter (anti-hallucination)
        if league in not_started:
            continue

        # Extra plausibility check
        plausible, reason = verify_league_fixture(league, today)
        if not plausible:
            continue

        filtered_rows.append(r)

    # Sort by kickoff time, then league
    sorted_rows = sorted(filtered_rows, key=lambda r: (
        r.get("kickoff", "99:99") if r.get("kickoff") != "TBD" else "99:99",
        r.get("league", ""),
    ))

    # Print header
    print(f"\n{'='*80}")
    print(f"  FOOTBALL FIXTURES - {today}  (verified with live odds)")
    print(f"{'='*80}\n")

    # Group by league
    by_league: Dict[str, List[Dict]] = {}
    for r in sorted_rows:
        lg = r.get("league", "Unknown")
        by_league.setdefault(lg, []).append(r)

    total = 0
    total_verified = 0
    total_with_odds = 0

    for league in sorted(by_league.keys()):
        fixtures = by_league[league]
        verified_count = sum(1 for r in fixtures if r.get("verified", False))
        odds_count = sum(1 for r in fixtures if r.get("odds_1") is not None)

        print(f"  {league} ({verified_count} verified, {odds_count} with odds)")

        for r in fixtures:
            kickoff = r.get("kickoff", "TBD")
            home = r.get("home", "?")
            away = r.get("away", "?")

            # Odds display
            odds = ""
            if r.get("odds_1"):
                odds = f"  | 1X2: {r['odds_1']:.2f}/{r['odds_x']:.2f}/{r['odds_2']:.2f}"
                if r.get("odds_source"):
                    odds += f" ({r['odds_source']})"
                total_with_odds += 1

            # Provenance stamp
            src = r.get("source", "?")
            fetch_time = r.get("fetched_at", datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
            verified_status = "verified" if r.get("verified", False) else "UNVERIFIED"
            prov = f"  [{src} | {fetch_time[:19]} | {verified_status}]"

            print(f"    {kickoff}  {home} vs {away}{odds}{prov}")
            total += 1
            if r.get("verified", False):
                total_verified += 1

        print()  # Blank line between leagues

    # Show leagues not yet started
    if not_started:
        whitelist_not_started = not_started & whitelist
        if whitelist_not_started:
            print(f"  !!!  Leagues NOT YET STARTED (excluded): {', '.join(sorted(whitelist_not_started))}")

    # Final summary
    print(f"  Total: {total} fixtures across {len(by_league)} deploy-eligible competitions")
    print(f"  Verified: {total_verified} fixtures (confirmed by >=2 sources)")
    print(f"  With live odds: {total_with_odds} fixtures")
    print(f"{'='*80}\n")


def main_final(target_date: Optional[str] = None, verify_only: bool = False):
    """
    Main function for final integrated fixtures agent.

    Follows the same pattern as original but adds:
    1. SportyBet live fixture fetching
    2. Live odds enhancement from SportyBet
    3. Enhanced output with odds display
    """
    today = target_date or date.today().isoformat()

    if verify_only:
        original_main(target_date=target_date, verify_only=True)
        return

    print(f"[final-fixtures] Fetching fixtures for {today}...")
    print(f"[final-fixtures] PRIMARY SOURCE: FlashScore (Architect directive 2026-08-14)")
    print()

    all_rows: List[Dict] = []

    # === STEP 1: Fetch from all traditional sources ===
    print("  [1/6] FlashScore (PRIMARY)...")
    fs_rows = fetch_flashscore(today)
    for r in fs_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(fs_rows)} fixtures found")
    all_rows.extend(fs_rows)

    print("  [2/6] LiveScore...")
    ls_rows = fetch_livescore(today)
    for r in ls_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(ls_rows)} fixtures found")
    all_rows.extend(ls_rows)

    print("  [3/6] BBC Sport...")
    bbc_rows = fetch_bbc(today)
    for r in bbc_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(bbc_rows)} fixtures found")
    all_rows.extend(bbc_rows)

    print("  [4/6] Sporting Life...")
    sl_rows = fetch_sportinglife(today)
    for r in sl_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(sl_rows)} fixtures found")
    all_rows.extend(sl_rows)

    print("  [5/6] SportyBet cache (with cached odds)...")
    sb_rows = fetch_sportybet_cache(today)
    for r in sb_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(sb_rows)} fixtures with cached odds")
    all_rows.extend(sb_rows)

    # === STEP 6: API-Football (structured data) ===
    print("  [6/6] API-Football...")
    api_rows = []
    if API_FOOTBALL_AVAILABLE:
        try:
            api_client = APIFootballClient()
            # Fetch fixtures for all known leagues
            for league_name, league_id in LEAGUE_ID_MAP.items():
                if league_id is not None:
                    league_fixtures = api_client.get_fixtures(today, league_id=league_id, season=2026)
                    for fixture in league_fixtures:
                        # Convert Fixture dataclass to dict with additional fields
                        fixture_dict = {
                            "league": fixture.league,
                            "home": fixture.home,
                            "away": fixture.away,
                            "kickoff": fixture.kickoff_utc[11:16] if len(fixture.kickoff_utc) >= 16 else "TBD",
                            "kickoff_date": fixture.kickoff_utc[:10] if fixture.kickoff_utc else today,
                            "fixture_id": fixture.fixture_id,
                            "source": "API-Football",
                            "fetched_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                            "status": fixture.status,
                            "raw": fixture.raw
                        }
                        api_rows.append(fixture_dict)
            # APIFootballClient doesn't have close() - the session is managed internally
            print(f"       {len(api_rows)} fixtures found")
            all_rows.extend(api_rows)
        except Exception as e:
            print(f"[INFO] API-Football unavailable: {e}")
    else:
        print("       [SKIPPED] API-Football client not available")

    # === STEP 2: Add live SportyBet fixtures ===
    print("  [7/7] SportyBet live API...")
    sb_live_rows = fetch_sportybet_live_fixtures(today)
    for r in sb_live_rows:
        r["fetched_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    print(f"       {len(sb_live_rows)} live fixtures found")
    all_rows.extend(sb_live_rows)

    # === STEP 3: Enhance existing fixtures with live SportyBet odds ===
    print("  [Enhancement] Adding live odds from SportyBet...")
    all_rows = enhance_with_sportybet_odds(today, all_rows)
    odds_enhanced = sum(1 for r in all_rows if r.get("odds_1") is not None and r.get("odds_source") == "SportyBet live")
    print(f"       {odds_enhanced} fixtures enhanced with live odds")

    # === STEP 4: Apply fixture matching for improved verification ===
    print("  [Matching] Applying team name normalization and cross-source matching...")
    if FIXTURE_MATCHER_AVAILABLE:
        try:
            # Convert all_rows to format expected by matcher (group by source)
            # We need to convert our dict rows to SourceFixture objects
            from verification.fixture_matcher import SourceFixture
            source_lists = {}
            for row in all_rows:
                source = row.get("source", "unknown")
                if source not in source_lists:
                    source_lists[source] = []

                # Convert dict row to SourceFixture
                source_fixture = SourceFixture(
                    home=row.get("home", ""),
                    away=row.get("away", ""),
                    league=row.get("league", ""),
                    kickoff_utc=row.get("kickoff_utc", ""),
                    raw=row
                )
                source_lists[source].append(source_fixture)

            # Apply matching
            matched_fixtures = match_fixtures(source_lists)

            # Diagnostic logging
            report = unmatched_report(matched_fixtures)
            print(f"       Matched: {report['total_fixtures']} fixtures")
            print(f"       Verified: {report['verified_2plus']} fixtures (>=2 sources)")
            print(f"       Single-source: {report['single_source']} fixtures")
            print(f"       Conflict: {report['conflict']} fixtures")
            verification_rate = report['verified_2plus'] / report['total_fixtures'] if report['total_fixtures'] > 0 else 0
            print(f"       Verification rate: {verification_rate:.1%}")

            # Convert back to flat list format for existing pipeline
            # We'll enhance each row with verification info from matcher
            enhanced_rows = []
            for fixture in matched_fixtures:
                # Create a base row from the first source's data
                if fixture.sources:
                    # Get the first source's raw data
                    first_source_key = next(iter(fixture.sources))
                    first_source_fixture = fixture.sources[first_source_key]
                    base_row = first_source_fixture.raw.copy()
                else:
                    # Fallback if no sources
                    base_row = {}

                # Add verification and source information
                base_row["verified"] = fixture.is_verified
                base_row["source_count"] = fixture.source_count
                base_row["all_sources"] = list(fixture.sources.keys())

                # Ensure we have the basic fixture fields
                if "home" not in base_row:
                    base_row["home"] = fixture.home
                if "away" not in base_row:
                    base_row["away"] = fixture.away
                if "league" not in base_row:
                    base_row["league"] = fixture.league
                if "kickoff_utc" not in base_row:
                    base_row["kickoff_utc"] = ""
                if "kickoff_date" not in base_row:
                    base_row["kickoff_date"] = fixture.kickoff_utc.strftime('%Y-%m-%d') if fixture.kickoff_utc else ""

                enhanced_rows.append(base_row)

            all_rows = enhanced_rows

        except Exception as e:
            print(f"[INFO] Fixture matching failed, continuing with original verification: {e}")
            # Fallback to original verification logic
            _apply_verification(all_rows)
    else:
        print("       [SKIPPED] Fixture matcher not available")
        # Apply original verification
        _apply_verification(all_rows)

    # === STEP 5: Print results with live odds ===
    print_fixtures_with_odds(today, all_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Final integrated fixtures agent with live SportyBet odds"
    )
    parser.add_argument("date", nargs="?", help="Target date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--verify", action="store_true", help="Pre-flight league calendar check only")
    args = parser.parse_args()

    main_final(target_date=args.date, verify_only=args.verify)