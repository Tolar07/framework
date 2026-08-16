#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PredictZ Fixtures Scraper — produces structured JSONL feed for verification gate.

PredictZ provides free football predictions and fixtures. We scrape fixture lists
(home/away/date) and emit match_1x2 JSONL with traceable provenance.
Odds/predictions are NOT consumed — only fixture identity for F2 quorum.

Architecture: same pattern as FlashScore scraper (scrape_live_odds_v3.py)
- Produces to data/live_odds/predictz_fixtures_*.jsonl
- Each entry: type, league, home_team, away_team, match_datetime, source, timestamp
- Source registered as "predictz_fixtures" in SOURCE_TRUST = T2 (after verification)
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.predictz_leagues import PREDICTZ_LEAGUES, BASE_URL


class PredictZFixturesScraper:
    """Scrapes fixtures from PredictZ for mapped leagues."""

    OUTPUT_DIR = Path(__file__).parent.parent / "data" / "live_odds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(
        self,
        headless: bool = True,
        leagues: Optional[List[str]] = None,
        max_matches_per_league: int = 50,
    ):
        self.headless = headless
        self.leagues = leagues or list(PREDICTZ_LEAGUES.keys())
        self.max_matches = max_matches_per_league
        self.browser = None
        self.page = None
        self.playwright = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        self.page = await context.new_page()
        return self

    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def _parse_fixture_row(self, text: str, league: str) -> Optional[tuple[str, str, str]]:
        """
        Parse a PredictZ fixture row.
        PredictZ format varies; typically "Team A vs Team B  21/08/2026 20:00"
        Returns (home, away, match_datetime) or None.
        """
        if not text or len(text) < 5:
            return None

        # Try multiple patterns
        # Pattern 1: "Team A vs Team B  21/08/2026 20:00"
        m = re.match(r'^(.+?)\s+(?:vs|v)\s+(.+?)\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})', text.strip())
        if m:
            home, away, dt = m.groups()
            return home.strip(), away.strip(), dt.strip()

        # Pattern 2: "Team A - Team B  21/08/2026"
        m = re.match(r'^(.+?)\s+-\s+(.+?)\s+(\d{1,2}/\d{1,2}/\d{4})', text.strip())
        if m:
            home, away, dt = m.groups()
            return home.strip(), away.strip(), dt.strip() + " 00:00"

        # Pattern 3: Table row with separate cells - try to extract from structured HTML
        return None

    async def scrape_league_fixtures(self, league_name: str) -> List[dict[str, Any]]:
        """Scrape fixtures for a single league from PredictZ."""
        slug = PREDICTZ_LEAGUES.get(league_name)
        if not slug:
            print(f"  [{datetime.now().isoformat()}] {league_name}: NOT MAPPED in PREDICTZ_LEAGUES")
            return []

        url = BASE_URL.format(slug=slug)
        print(f"  [{datetime.now().isoformat()}] {league_name}: fetching {url}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  [{datetime.now().isoformat()}] {league_name}: navigation failed: {e}")
            return []

        # PredictZ uses tables with class like "pttd" or similar
        # Try to find fixture rows
        match_elements = await self.page.query_selector_all("table tr, .pttd tr, .fixtures tr")
        print(f"  [{datetime.now().isoformat()}] {league_name}: found {len(match_elements)} potential rows")

        results = []
        for idx, el in enumerate(match_elements[:self.max_matches]):
            try:
                text = await el.text_content()
                if not text or len(text.strip()) < 10:
                    continue

                parsed = self._parse_fixture_row(text, league_name)
                if not parsed:
                    continue

                home_team, away_team, match_datetime = parsed

                results.append({
                    "type": "match_1x2",
                    "league": league_name,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_datetime": match_datetime,
                    "market": "match_winner",
                    "source": "predictz_fixtures",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"    match {idx} parse error: {e}")
                continue

        print(f"  [{datetime.now().isoformat()}] {league_name}: parsed {len(results)} fixtures")
        return results

    async def scrape_all(self) -> List[dict[str, Any]]:
        all_results: List[dict[str, Any]] = []
        for league in self.leagues:
            try:
                fixtures = await self.scrape_league_fixtures(league)
                all_results.extend(fixtures)
            except Exception as e:
                print(f"  [{datetime.now().isoformat()}] {league}: ERROR {e}")
                continue
        return all_results

    def save_results(self, results: List[dict[str, Any]]) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = self.OUTPUT_DIR / f"predictz_fixtures_{ts}.jsonl"

        with outfile.open("w", encoding="utf-8") as f:
            for entry in results:
                f.write(json.dumps(entry) + "\n")

        print(f"[{datetime.now().isoformat()}] Saved {len(results)} entries to {outfile}")
        return outfile


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="PredictZ fixtures scraper")
    parser.add_argument("--leagues", nargs="*", help="Specific league names to scrape (default: all mapped)")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--max-matches", type=int, default=50, help="Max matches per league")
    args = parser.parse_args()

    async with PredictZFixturesScraper(
        headless=args.headless,
        leagues=args.leagues,
        max_matches_per_league=args.max_matches,
    ) as scraper:
        results = await scraper.scrape_all()
        scraper.save_results(results)

        print("\n" + "="*60)
        print("📊 PREDICTZ SCRAPING SUMMARY")
        print("="*60)

        by_league: dict[str, int] = {}
        for r in results:
            by_league[r["league"]] = by_league.get(r["league"], 0) + 1

        for lg, cnt in sorted(by_league.items()):
            print(f"  {lg}: {cnt} fixtures")
        print(f"\nTOTAL: {len(results)} fixtures across {len(by_league)} leagues")


if __name__ == "__main__":
    asyncio.run(main())