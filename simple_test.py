#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from outcome_tracker import OutcomeTracker
from datetime import datetime
import json

# Test the normalization
tracker = OutcomeTracker()

print("Testing team name normalization:")
test_names = [
    "Arsenal FC",
    "Arsenal",
    "Manchester United FC",
    "Man United",
    "Newcastle United FC",
    "Newcastle",
    "Coventry City FC",
    "Coventry City"
]
for name in test_names:
    norm = tracker.normalize_team_name(name)
    print(f"  '{name}' -> '{norm}'")

print("\nTesting prediction to match:")
prediction = {
    'home_team': 'Arsenal',
    'away_team': 'Coventry City',
    'league': 'Premier League',
    'kickoff': '2026-08-21T19:00:00Z'
}

print(f"  Prediction: {prediction['home_team']} v {prediction['away_team']} ({prediction['league']})")
print(f"  Date: {prediction['kickoff']}")

# Test loading results with correct season
results = tracker.load_league_results(prediction['league'], "2026")
if results is None:
    print("  Could not load results")
    sys.exit(1)
else:
    print(f"  Loaded results: {len(results)} matches")

# Look at first few matches
print("\nFirst 3 matches from data:")
for i in range(min(3, len(results))):
    match = results[i]
    home = match.get('homeTeam', {}).get('name', '')
    away = match.get('awayTeam', {}).get('name', '')
    date = match.get('utcDate', '')
    status = match.get('status', '')
    print(f"  {i+1}. {home} v {away} ({date}) - {status}")

# Test our specific match
print("\nTesting specific match matching:")
norm_home = tracker.normalize_team_name(prediction['home_team'])
norm_away = tracker.normalize_team_name(prediction['away_team'])
print(f"  Normalized prediction: '{norm_home}' v '{norm_away}'")

# Parse date
try:
    target_date = datetime.strptime(prediction['kickoff'].split('T')[0], "%Y-%m-%d")
    print(f"  Target date: {target_date.date()}")
except Exception as e:
    print(f"  Date parse error: {e}")
    target_date = None

# Search manually
found = False
for match in results:
    if match.get('status', '').upper() not in ['FINISHED', 'FT']:
        continue
    fixture_home = match.get('homeTeam', {}).get('name', '')
    fixture_away = match.get('awayTeam', {}).get('name', '')
    if not fixture_home or not fixture_away:
        continue
    norm_fixture_home = tracker.normalize_team_name(fixture_home)
    norm_fixture_away = tracker.normalize_team_name(fixture_away)

    home_match = (norm_home == norm_fixture_home and norm_away == norm_fixture_away)
    away_match = (norm_home == norm_fixture_away and norm_away == norm_fixture_home)

    if home_match or away_match:
        # Check date
        fixture_date_str = match.get('utcDate', '')
        try:
            fixture_date = datetime.strptime(fixture_date_str.split('T')[0], "%Y-%m-%d")
            date_diff = abs((fixture_date - target_date).days) if target_date else 999
            if date_diff <= 1:
                print(f"  MATCH FOUND: {fixture_home} v {fixture_away} on {fixture_date_str}")
                print(f"    Score: {match.get('score', {}).get('fullTime', {})}")
                found = True
                break
            else:
                print(f"  Date mismatch: {fixture_home} v {fixture_away} on {fixture_date_str} (diff {date_diff} days)")
        except Exception as e:
            print(f"  Date parse error for fixture: {e}")

if not found:
    print("  NO MATCH FOUND")
    # Show what we have for Arsenal v Coventry
    print("\nChecking for Arsenal matches on or near 2026-08-21:")
    for match in results:
        if match.get('status', '').upper() not in ['FINISHED', 'FT']:
            continue
        home = match.get('homeTeam', {}).get('name', '')
        away = match.get('awayTeam', {}).get('name', '')
        if 'Arsenal' in home or 'Arsenal' in away:
            date_str = match.get('utcDate', '')
            try:
                match_date = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
                diff = (match_date - target_date).days if target_date else 0
                print(f"  {home} v {away} on {date_str} (diff {diff} days)")
            except:
                print(f"  {home} v {away} on {date_str} (date parse error)")

print("\nDone.")