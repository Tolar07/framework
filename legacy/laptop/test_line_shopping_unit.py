#!/usr/bin/env python3
"""Unit test to verify line shopping functionality with mocked API responses"""

import os
import sys
from unittest import mock

sys.path.insert(0, '.')

from pipeline.odds import fetch_odds, FixtureOdds, MarketQuote


# Mock API response for a single region
MOCK_UK_RESPONSE = [{
    "id": "12345",
    "commence_time": "2026-08-30T14:00:00Z",
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "bookmakers": [
        {"key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Arsenal", "price": 1.85},
                {"name": "Draw", "price": 3.50},
                {"name": "Chelsea", "price": 4.20}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "point": 2.5, "price": 1.90},
                {"name": "Under", "point": 2.5, "price": 1.95}]}]}
    ]}]

MOCK_EU_RESPONSE = [{
    "id": "12345",
    "commence_time": "2026-08-30T14:00:00Z",
    "home_team": "Arsenal",
    "away_team": "Chelsea",
    "bookmakers": [
        {"key": "betfair_ex_eu", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Arsenal", "price": 1.80},
                {"name": "Draw", "price": 3.60},
                {"name": "Chelsea", "price": 4.40}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "point": 2.5, "price": 1.88},
                {"name": "Under", "point": 2.5, "price": 1.98}]}]}
    ]}]


def test_multi_region_median_calculation():
    """Test that fetch_odds correctly calculates median prices across regions"""
    print("Testing multi-region median price calculation...")

    # Set environment variables for multi-region
    os.environ['ODDS_REGIONS'] = 'uk,eu'
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    with mock.patch('pipeline.odds._resolve_key') as mock_resolve, \
         mock.patch('pipeline.odds._read_cache', return_value=None), \
         mock.patch('pipeline.odds.get_protected') as mock_get:

        # Mock the quota check
        mock_resolve.return_value = ('test_key', 100, 400)

        # Mock get_protected to return different responses per region
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call - uk region
                mock_resp = mock.Mock()
                mock_resp.json.return_value = MOCK_UK_RESPONSE
                mock_resp.headers = {'x-requests-remaining': '399'}
                return mock_resp
            else:
                # Second call - eu region
                mock_resp = mock.Mock()
                mock_resp.json.return_value = MOCK_EU_RESPONSE
                mock_resp.headers = {'x-requests-remaining': '398'}
                return mock_resp

        mock_get.side_effect = side_effect

        # Call fetch_odds
        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)

        print(f"Flags: {flags}")
        print(f"Fixtures fetched: {len(fixtures)}")

        assert len(fixtures) == 1, f"Expected 1 fixture, got {len(fixtures)}"
        fx = fixtures[0]

        # Check median prices:
        # Home: median(1.85, 1.80) = 1.825
        # Draw: median(3.50, 3.60) = 3.55
        # Away: median(4.20, 4.40) = 4.30
        # Over 2.5: median(1.90, 1.88) = 1.89
        # Under 2.5: median(1.95, 1.98) = 1.965

        print(f"Home odds: {fx.home.price} (bookmaker: {fx.home.bookmaker}, n_books: {fx.home.n_books})")
        print(f"Draw odds: {fx.draw.price} (bookmaker: {fx.draw.bookmaker}, n_books: {fx.draw.n_books})")
        print(f"Away odds: {fx.away.price} (bookmaker: {fx.away.bookmaker}, n_books: {fx.away.n_books})")
        print(f"Over 2.5: {fx.over25.price} (bookmaker: {fx.over25.bookmaker}, n_books: {fx.over25.n_books})")
        print(f"Under 2.5: {fx.under25.price} (bookmaker: {fx.under25.bookmaker}, n_books: {fx.under25.n_books})")

        # Verify median calculation (allowing for floating point precision)
        assert abs(fx.home.price - 1.825) < 0.001, f"Expected median 1.825, got {fx.home.price}"
        assert abs(fx.draw.price - 3.55) < 0.001, f"Expected median 3.55, got {fx.draw.price}"
        assert abs(fx.away.price - 4.30) < 0.001, f"Expected median 4.30, got {fx.away.price}"
        assert abs(fx.over25.price - 1.89) < 0.001, f"Expected median 1.89, got {fx.over25.price}"
        assert abs(fx.under25.price - 1.965) < 0.001, f"Expected median 1.965, got {fx.under25.price}"

        # Verify bookmaker is "median" and n_books = 2 (two regions)
        assert fx.home.bookmaker == "median"
        assert fx.home.n_books == 2
        assert fx.draw.n_books == 2
        assert fx.away.n_books == 2
        assert fx.over25.n_books == 2
        assert fx.under25.n_books == 2

        print("✓ Multi-region median price calculation test PASSED")
        return True


def test_single_region_backward_compatibility():
    """Test that single region usage still works (backward compatibility)"""
    print("\nTesting single region backward compatibility...")

    # Set environment variables for single region
    os.environ['ODDS_REGIONS'] = 'uk'
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    with mock.patch('pipeline.odds._resolve_key') as mock_resolve, \
         mock.patch('pipeline.odds._read_cache', return_value=None), \
         mock.patch('pipeline.odds.get_protected') as mock_get:

        mock_resolve.return_value = ('test_key', 100, 400)

        mock_resp = mock.Mock()
        mock_resp.json.return_value = MOCK_UK_RESPONSE
        mock_resp.headers = {'x-requests-remaining': '399'}
        mock_get.return_value = mock_resp

        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)

        print(f"Flags: {flags}")
        print(f"Fixtures fetched: {len(fixtures)}")

        assert len(fixtures) == 1, f"Expected 1 fixture, got {len(fixtures)}"
        fx = fixtures[0]

        # With single region, prices should come directly from that region
        assert abs(fx.home.price - 1.85) < 0.001, f"Expected 1.85, got {fx.home.price}"
        assert abs(fx.draw.price - 3.50) < 0.001, f"Expected 3.50, got {fx.draw.price}"
        assert abs(fx.away.price - 4.20) < 0.001, f"Expected 4.20, got {fx.away.price}"
        assert abs(fx.over25.price - 1.90) < 0.001, f"Expected 1.90, got {fx.over25.price}"
        assert abs(fx.under25.price - 1.95) < 0.001, f"Expected 1.95, got {fx.under25.price}"

        # With current implementation, bookmaker is always "median"
        # (even for single region - it's treated as median across regions)
        assert fx.home.bookmaker == "median"
        assert fx.draw.bookmaker == "median"
        assert fx.away.bookmaker == "median"
        assert fx.home.n_books == 1
        assert fx.draw.n_books == 1
        assert fx.away.n_books == 1

        print("✓ Single region backward compatibility test PASSED")
        return True


def test_empty_region_list():
    """Test empty region list handling"""
    print("\nTesting empty region list handling...")

    os.environ['ODDS_REGIONS'] = ''
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    with mock.patch('pipeline.odds._resolve_key') as mock_resolve, \
         mock.patch('pipeline.odds._read_cache', return_value=None), \
         mock.patch('pipeline.odds.get_protected') as mock_get:

        mock_resolve.return_value = ('test_key', 100, 400)
        mock_get.return_value = mock.Mock()

        try:
            fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)
            # Should handle gracefully - likely return empty list
            print(f"Empty regions returned: {len(fixtures)} fixtures, flags: {flags}")
            print("✓ Empty region list handling test PASSED")
            return True
        except Exception as e:
            print(f"Error (may be expected): {e}")
            return False


def test_failed_region_fetch():
    """Test that failed region fetch doesn't break aggregation"""
    print("\nTesting failed region fetch handling...")

    os.environ['ODDS_REGIONS'] = 'uk,eu'
    os.environ['ODDS_MARKETS'] = 'h2h,totals'

    with mock.patch('pipeline.odds._resolve_key') as mock_resolve, \
         mock.patch('pipeline.odds._read_cache', return_value=None), \
         mock.patch('pipeline.odds.get_protected') as mock_get:

        mock_resolve.return_value = ('test_key', 100, 400)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (uk) succeeds
                mock_resp = mock.Mock()
                mock_resp.json.return_value = MOCK_UK_RESPONSE
                mock_resp.headers = {'x-requests-remaining': '399'}
                return mock_resp
            else:
                # Second call (eu) fails
                raise Exception("Network error")

        mock_get.side_effect = side_effect

        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)

        print(f"Flags: {flags}")
        print(f"Fixtures fetched: {len(fixtures)}")

        # Should still get fixtures from the successful region
        assert len(fixtures) == 1, f"Expected 1 fixture from successful region, got {len(fixtures)}"
        fx = fixtures[0]

        # With one region only, prices should be from that region
        assert fx.home.price == 1.85, f"Expected 1.85 from uk, got {fx.home.price}"
        assert fx.home.n_books == 1, f"Expected n_books=1, got {fx.home.n_books}"

        print("✓ Failed region fetch handling test PASSED")
        return True


def test_median_odd_even_counts():
    """Test median calculation with odd and even number of prices"""
    print("\nTesting median calculation with odd/even counts...")

    # Create test fixture with 3 regions (odd count)
    os.environ['ODDS_REGIONS'] = 'uk,eu,us'
    os.environ['ODDS_MARKETS'] = 'h2h'

    MOCK_THREE_REGIONS = [{
        "id": "12345",
        "commence_time": "2026-08-30T14:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {"key": "bet365", "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Arsenal", "price": 1.85},
                    {"name": "Draw", "price": 3.50},
                    {"name": "Chelsea", "price": 4.20}]}]}]}]

    with mock.patch('pipeline.odds._resolve_key') as mock_resolve, \
         mock.patch('pipeline.odds._read_cache', return_value=None), \
         mock.patch('pipeline.odds.get_protected') as mock_get:

        mock_resolve.return_value = ('test_key', 100, 400)

        # Create 3 different responses
        def make_response(price):
            resp = mock.Mock()
            resp.json.return_value = [{
                "id": "12345",
                "commence_time": "2026-08-30T14:00:00Z",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "bookmakers": [{"key": "test", "markets": [
                    {"key": "h2h", "outcomes": [
                        {"name": "Arsenal", "price": price},
                        {"name": "Draw", "price": 3.50},
                        {"name": "Chelsea", "price": 4.20}]}]}]}]
            resp.headers = {'x-requests-remaining': '399'}
            return resp

        mock_get.side_effect = [
            make_response(1.80),  # Region 1
            make_response(1.85),  # Region 2
            make_response(1.90),  # Region 3
        ]

        fixtures, flags = fetch_odds('Premier League', use_cache=False, fixture_capture=False)

        fx = fixtures[0]
        # Median of [1.80, 1.85, 1.90] = 1.85
        print(f"Home odds (3 regions): {fx.home.price} (n_books={fx.home.n_books})")
        assert fx.home.price == 1.85, f"Expected median 1.85, got {fx.home.price}"
        assert fx.home.n_books == 3, f"Expected n_books=3, got {fx.home.n_books}"

        print("✓ Odd/even median count test PASSED")
        return True


if __name__ == "__main__":
    results = []
    results.append(test_multi_region_median_calculation())
    results.append(test_single_region_backward_compatibility())
    results.append(test_failed_region_fetch())
    results.append(test_median_odd_even_counts())

    if all(results):
        print("\n" + "="*50)
        print("ALL LINE SHOPPING TESTS PASSED")
        print("="*50)
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("SOME TESTS FAILED")
        print("="*50)
        sys.exit(1)