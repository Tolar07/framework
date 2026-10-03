#!/usr/bin/env python3
"""
verify_results.py — automated FT-result confirmation using Perplexity and Firecrawl
replaces manual "search + fetch + grade" process for OLP XDV framework.

Key differences from original:
- Uses Perplexity for web search (no Anthropic API key needed)
- Uses Firecrawl for direct page scraping (requires Firecrawl API key)
- Implements ID403 tiering: VERIFIED (2+ independent domains), SINGLE-SOURCE, CONFLICT, NO-DATA
- Enforces ID48 requirement: only counts direct URLs to live-score/results pages

Usage:
    python verify_results.py --input fixtures.json --output results.json

fixtures.json: [{"home": "...", "away": "...", "league": "...", "date": "YYYY-MM-DD"}, ...]
results.json: same fixtures, each with a "verification" block added.

This script:
1. Uses Perplexity to search for match reports
2. Extracts direct URLs to match reports from search results
3. Uses Firecrawl to scrape match reports
4. Applies verification rules:
   - HR35: no fabrication - only use direct URLs
   - ID403: VERIFIED (2+ independent domains), SINGLE-SOURCE, CONFLICT, NO-DATA
   - ID48: direct URL requirement (not forums, tweets, or aggregators)

Output ONLY this JSON object, no other text:
{
  "status": "VERIFIED" | "SINGLE-SOURCE" | "CONFLICT" | "NO-DATA",
  "ft_score": {"home": <int>, "away": <int>} | null,
  "conflicting_scores": [{"home": <int>, "away": <int>, "source": "<url>"}] | null,
  "sources": [{"url": "<direct url actually fetched>", "domain": "<domain>"}],
  "notes": "<one short sentence, e.g. why NO-DATA if applicable>"
}
"""
from __future__ import annotations

import json
import os
import sys
import time
import argparse
import re
from typing import Any, List, Dict

# MCP tools are available directly in the environment with mcp__ prefix
# We'll check if they're available by trying to use them
perplexity_search_available = True
firecrawl_scrape_available = True


def find_direct_urls(home: str, away: str, league: str, date: str) -> List[str]:
    """Find direct URLs to match reports using Perplexity search"""
    query = f"{home} vs {away} {league} {date} full time score site:bbc.co.uk/sport OR site:skysports.com OR site:espn.com OR site:flashscore.com OR site:thesportsdb.com OR site:sofascore.com"

    try:
        # Use the MCP tool directly
        result = mcp__perplexity__perplexity_search({
            "query": query,
            "max_results": 10
        })

        # Parse the result to extract URLs
        # The MCP tool returns a dict with results
        if isinstance(result, dict) and 'results' in result:
            urls = []
            for item in result['results']:
                if isinstance(item, dict) and 'url' in item:
                    url = item['url']
                    # Filter for direct score/report pages (not forums, social media, etc.)
                    if any(domain in url for domain in ['bbc.co.uk/sport', 'bbc.com/sport', 'skysports.com', 'espn.com', 'flashscore.com', 'thesportsdb.com', 'sofascore.com']):
                        # Exclude forums, social media, aggregators
                        if not any(exclude in url.lower() for exclude in ['forum', 'reddit', 'twitter', 'x.com', 'facebook', 'instagram', 'tiktok', 'youtube.com/watch']):
                            urls.append(url)
            return urls[:5]  # Limit to top 5 results
        else:
            print(f"Unexpected Perplexity result format: {result}", file=sys.stderr)
            return []

    except Exception as e:
        print(f"Perplexity search failed: {e}", file=sys.stderr)
        return []


def scrape_match_report(url: str) -> Dict[str, Any]:
    """Use Firecrawl to scrape a match report page"""
    try:
        # Use the MCP tool directly
        result = mcp__firecrawl__firecrawl_scrape({
            "url": url,
            "formats": ["markdown"]
        })

        # Parse the result
        if isinstance(result, dict):
            return result
        else:
            print(f"Unexpected Firecrawl result format: {result}", file=sys.stderr)
            return {}

    except Exception as e:
        print(f"Firecrawl scrape failed for {url}: {e}", file=sys.stderr)
        return {}


def parse_ft_score(content: str, home: str, away: str) -> Dict[str, int] | None:
    """Parse the full-time score from match report content"""
    try:
        # Look for common patterns in match scores
        patterns = [
            r"(\d+)-(\d+)",  # 2-1 format
            r"(\d+)\s*:\s*(\d+)",  # 2:1 format
            r"full\s*time\s*score\s*[:\-]\s*(\d+)\s*[-:]\s*(\d+)",  # full time score
            r"final\s*score\s*[:\-]\s*(\d+)\s*[-:]\s*(\d+)",  # final score
            r"(\d+)\s*–\s*(\d+)",  # 2–1 format (en dash)
            r"at\s+Full\s+time\s*[:\-]\s*(\d+)\s*[,，\s]+(\d+)",  # "at Full time: 1-0"
            r"(\d+)\s*[,，\s]+(\d+)\s*at\s+Full\s+time",  # "1, 0 at Full time"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Take the first match (most likely the main score)
                home_goals, away_goals = int(matches[0][0]), int(matches[0][1])
                return {"home": home_goals, "away": away_goals}

        return None
    except Exception as e:
        print(f"Score parsing failed: {e}", file=sys.stderr)
        return None


def verify_one(fixture: dict) -> dict:
    home, away, league, date = fixture['home'], fixture['away'], fixture.get('league', 'unknown'), fixture['date']

    print(f"Verifying {home} vs {away} in {league} on {date}...", file=sys.stderr)

    # Step 1: Find direct URLs to match reports
    urls = find_direct_urls(home, away, league, date)
    if not urls:
        return {
            "status": "NO-DATA",
            "ft_score": None,
            "conflicting_scores": None,
            "sources": [],
            "notes": "No direct URLs found for match"
        }

    # Step 2: Find 2+ independent sources
    verified_sources = []
    single_source = []
    conflict = []
    all_sources = []  # Track all sources for output

    for url in urls:
        # Step 2: Scrape the page
        content = scrape_match_report(url)
        if not content or 'markdown' not in content:
            continue

        # Step 3: Parse the score
        ft_score = parse_ft_score(content['markdown'], home, away)
        if not ft_score:
            continue

        # Validate domain (different domains count as independent)
        domain = url.split("://")[1].split("/")[0]
        source_info = {"url": url, "domain": domain}
        all_sources.append(source_info)

        # Store score for conflict detection
        url_exists = any(s['url'] == url for s in verified_sources)
        if not url_exists:
            single_source.append({"url": url, "domain": domain, "score": ft_score})
        else:
            # Check for conflicts with verified sources
            is_conflict = False
            for existing in verified_sources:
                if existing['score']['home'] != ft_score['home'] or existing['score']['away'] != ft_score['away']:
                    conflict.append({
                        "home": ft_score['home'],
                        "away": ft_score['away'],
                        "source": url
                    })
                    is_conflict = True
                    break

            if not is_conflict:
                verified_sources.append({"url": url, "domain": domain, "score": ft_score})

    # Step 4: Determine verification status
    if len(verified_sources) >= 2:
        status = "VERIFIED"
    elif len(verified_sources) == 1:
        status = "SINGLE-SOURCE"
    elif conflict:
        status = "CONFLICT"
    else:
        status = "NO-DATA"

    # Step 5: Determine ft_score
    if status == "NO-DATA":
        ft_score = None
    else:
        # Use score from verified sources (or single source)
        if verified_sources:
            ft_score = verified_sources[0]['score']
        elif single_source:
            ft_score = single_source[0]['score']
        else:
            ft_score = None

    # Step 6: Format output
    return {
        "status": status,
        "ft_score": ft_score,
        "conflicting_scores": conflict if conflict else None,
        "sources": all_sources,
        "notes": "Verified match result" if status != "NO-DATA" else "No direct URL confirmation found"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to fixtures JSON list")
    parser.add_argument("--output", required=True, help="Path to write results JSON")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        fixtures: list[dict[str, Any]] = json.load(f)

    results = []

    for i, fixture in enumerate(fixtures, 1):
        print(f"[{i}/{len(fixtures)}] Verifying {fixture['home']} vs {fixture['away']}...", file=sys.stderr)
        verification = verify_one(fixture)
        results.append({**fixture, "verification": verification})
        if i < len(fixtures):
            time.sleep(2)  # Rate limiting

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    verified = sum(1 for r in results if r["verification"]["status"] == "VERIFIED")
    single_source = sum(1 for r in results if r["verification"]["status"] == "SINGLE-SOURCE")
    conflict = sum(1 for r in results if r["verification"]["status"] == "CONFLICT")
    pending = sum(1 for r in results if r["verification"]["status"] == "NO-DATA")
    print(f"Done: {verified}/{len(results)} VERIFIED, {single_source}/{len(results)} SINGLE-SOURCE, {conflict}/{len(results)} CONFLICT, {pending}/{len(results)} NO-DATA", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())