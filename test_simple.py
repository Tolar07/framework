#!/usr/bin/env python3
import os
import sys

# Add current directory to path
sys.path.insert(0, '.')

# Set environment variables
os.environ['ODDS_REGIONS'] = 'uk,eu'
os.environ['ODDS_MARKETS'] = 'h2h,totals'

print("Testing line shopping...")
print(f"ODDS_REGIONS: {os.environ.get('ODDS_REGIONS')}")
print(f"ODDS_MARKETS: {os.environ.get('ODDS_MARKETS')}")

try:
    from pipeline.odds import fetch_odds
    print("Import successful")

    # Test with Premier League
    fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)
    print(f"Successfully fetched {len(fixtures)} fixtures")
    print(f"Flags: {flags}")

    if fixtures:
        f = fixtures[0]
        print(f"First fixture: {f.home_team} vs {f.away_team}")
        print(f"Home odds: {f.home.price}")
        print(f"Draw odds: {f.draw.price}")
        print(f"Away odds: {f.away.price}")
        print(f"Over 2.5: {f.over25.price}")
        print(f"Under 2.5: {f.under25.price}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()