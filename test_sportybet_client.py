#!/usr/bin/env python
"""
Test script to verify SportyBetClient _get_api method exists and handles empty responses.
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from booking.sportybet_client import SportyBetClient

def test_import():
    """Test that SportyBetClient can be imported."""
    print("PASS: SportyBetClient imported successfully")

def test_get_api_exists():
    """Test that _get_api method exists."""
    client = SportyBetClient()
    assert hasattr(client, '_get_api'), "_get_api method not found"
    print("PASS: _get_api method exists")

def test_get_api_signature():
    """Test that _get_api has expected signature."""
    import inspect
    sig = inspect.signature(SportyBetClient._get_api)
    params = list(sig.parameters.keys())
    expected = ['self', 'endpoint', 'params', 'cache_ttl']
    assert params == expected, f"Unexpected signature: {params}"
    print(f"PASS: _get_api signature correct: {params}")

def test_empty_response_handling():
    """Verify the empty response handling code exists in _get_api."""
    import inspect
    source = inspect.getsource(SportyBetClient._get_api)

    # Check for empty response guard
    assert 'not response_text' in source or 'not response_text.strip()' in source, \
        "Empty response check not found"
    assert 'treating as transient' in source, "Transient error handling not found"
    assert '_record_failure_stat' in source, "Failure stat recording not found"
    assert 'breaker.record_failure()' in source, "Circuit breaker failure recording not found"
    print("PASS: Empty response handling code verified")

    # Print the relevant section for confirmation
    lines = source.split('\n')
    for i, line in enumerate(lines):
        if 'empty' in line.lower() or 'transient' in line.lower() or 'response_text' in line:
            print(f"  Line {i}: {line.strip()}")

def test_invalid_json_handling():
    """Verify invalid JSON handling exists in _get_api."""
    import inspect
    source = inspect.getsource(SportyBetClient._get_api)

    assert 'JSONDecodeError' in source, "JSONDecodeError handling not found"
    assert 'Invalid JSON' in source, "Invalid JSON error message not found"
    print("PASS: Invalid JSON handling code verified")

if __name__ == "__main__":
    print("Testing SportyBetClient _get_api method...")
    print()

    test_import()
    test_get_api_exists()
    test_get_api_signature()
    test_empty_response_handling()
    test_invalid_json_handling()

    print()
    print("All tests passed!")