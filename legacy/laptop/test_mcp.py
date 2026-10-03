#!/usr/bin/env python3
"""
Test MCP tools directly
"""

import json
import sys

def test_perplexity():
    """Test Perplexity search via MCP"""
    try:
        # This is how we call MCP tools - they're available in the environment
        result = mcp__perplexity__perplexity_search({
            "query": "Barcelona vs Rayo Vallecano La Liga 2026-08-31 full time score",
            "max_results": 5
        })
        print("Perplexity result:")
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        print(f"Perplexity test failed: {e}")
        return None

def test_firecrawl():
    """Test Firecrawl scrape via MCP"""
    try:
        result = mcp__firecrawl__firecrawl_scrape({
            "url": "https://www.espn.com/soccer/match/_/gameId/401882903/rayo-vallecano-barcelona",
            "formats": ["markdown"]
        })
        print("\nFirecrawl result (first 500 chars):")
        if result and 'markdown' in result:
            print(result['markdown'][:500] + "..." if len(result['markdown']) > 500 else result['markdown'])
        else:
            print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        print(f"Firecrawl test failed: {e}")
        return None

if __name__ == "__main__":
    print("Testing MCP tools...")
    test_perplexity()
    test_firecrawl()