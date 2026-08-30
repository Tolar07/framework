#!/usr/bin/env python3
"""Test script to verify line shopping functionality"""

import os
import sys

# Add current directory to path so we can import pipeline modules
sys.path.insert(0, '.')

from pipeline.odds import fetch_odds

def test_line_shopping():
    """Test that fetch_odds works with multiple regions"""
    print("Testing line shopping functionality...")

    # Set environment variables for testing
    os.environ['ODDS_REGIONS'] = 'uk,eu'
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    try:
        # Test with a small league that should have data
        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)
        print(f"Successfully fetched {len(fixtures)} fixtures")
        print(f"Flags: {flags}")

        if fixtures:
            print(f"First fixture: {fixtures[0].home_team} vs {fixtures[0].away_team}")
            print(f"Home odds: {fixtures[0].home.price}")
            print(f"Draw odds: {fixtures[0].draw.price}")
            print(f"Away odds: {fixtures[0].away.price}")
            print(f"Over 2.5: {fixtures[0].over25.price}")
            print(f"Under 2.5: {fixtures[0].under25.price}")

        return True
    except Exception as e:
        print(f"Error testing line shopping: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """Test that existing single-region usage still works"""
    print("\nTesting backward compatibility...")

    # Set environment variables for single region (default)
    os.environ['ODDS_REGIONS'] = 'uk'
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    try:
        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)
        print(f"Successfully fetched {len(fixtures)} fixtures with single region")
        print(f"Flags: {flags}")
        return True
    except Exception as e:
        print(f"Error testing backward compatibility: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_line_shopping()
    success2 = test_backward_compatibility()

    if success1 and success2:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)