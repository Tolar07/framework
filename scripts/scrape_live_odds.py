#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Odds Scraper - FlashScore Premier League
Solves ID397/FIX4: Automated price feed from JS-locked sources
Uses Playwright to render JS and extract structured odds data.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright


class FlashScoreOddsScraper:
    """Scrapes live odds from FlashScore Premier League page."""

    BASE_URL = "https://www.flashscore.com/football/england/premier-league/"
    OUTPUT_DIR = Path("data/live_odds")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.page = None

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
        await self.playwright.stop()

    async def fetch_odds(self) -> list[dict[str, Any]]:
        """Navigate to FlashScore and extract structured odds."""
        print(f"[{datetime.now().isoformat()}] Navigating to {self.BASE_URL}")
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(8000)  # Allow JS to render odds

        # Wait for odds elements to appear
        try:
            await self.page.wait_for_selector("[class*='odd']", timeout=15000)
            print(f"[{datetime.now().isoformat()}] Odds elements found in DOM")
        except Exception:
            print(f"[{datetime.now().isoformat()}] Warning: No odds elements found")

        # Take screenshot for debugging
        screenshot_path = self.OUTPUT_DIR / "flashscore_debug.png"
        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"[{datetime.now().isoformat()}] Screenshot saved to {screenshot_path}")

        # Get match elements (fixture data)
        match_elements = await self.page.query_selector_all(
            ".event__match, .event__match--static, [class*='event__match']"
        )
        print(f"[{datetime.now().isoformat()}] Match elements found: {len(match_elements)}")

        # Get odds elements
        odds_elements = await self.page.query_selector_all("[class*='odd']")
        print(f"[{datetime.now().isoformat()}] Odds elements found: {len(odds_elements)}")

        matches = []

        # Method 1: Extract odds from odds-specific elements
        # These contain text like "ARS2.50", "MCI3.75", "LIV6.00"
        odds_container_text = ""
        for el in odds_elements[:5]:
            text = await el.text_content()
            if text:
                odds_container_text += text + " "

        # Pattern: Team code (3 uppercase letters) immediately followed by decimal odds
        odds_pattern = re.compile(r'([A-Z]{3})(\d\.\d{2})')
        for match in odds_pattern.finditer(odds_container_text):
            team_code, odds = match.groups()
            matches.append({
                "team_code": team_code,
                "odds": float(odds),
                "market": "outright_winner",
                "source": "odds_element",
                "timestamp": datetime.now().isoformat()
            })

        # Method 2: Extract match fixtures
        fixtures = []
        for i, el in enumerate(match_elements[:20]):
            text = await el.text_content()
            if text and text.strip():
                # Parse fixture: date + time + home team + away team
                fixture_pattern = re.compile(
                    r'(\d{2}\.\d{2}\.\s*\d{2}:\d{2})([A-Za-z\s]+?)([A-Z][a-z]+)--$'
                )
                fm = fixture_pattern.search(text.strip())
                if fm:
                    fixtures.append({
                        "fixture_id": i,
                        "datetime": fm.group(1),
                        "home_team": fm.group(2).strip(),
                        "away_team": fm.group(3).strip(),
                        "raw": text.strip()[:100]
                    })

        # Method 3: Get all body text and extract all team+odds pairs
        all_text = await self.page.evaluate(
            "() => document.body.innerText || document.body.textContent"
        )
        if all_text:
            for om in odds_pattern.finditer(all_text):
                team_code, odds = om.groups()
                matches.append({
                    "team_code": team_code,
                    "odds": float(odds),
                    "market": "outright_winner",
                    "source": "body_text",
                    "timestamp": datetime.now().isoformat()
                })

        # Deduplicate by team_code + odds
        seen = set()
        unique = []
        for m in matches:
            key = (m["team_code"], m["odds"])
            if key not in seen:
                seen.add(key)
                unique.append(m)

        print(f"[{datetime.now().isoformat()}] Extracted {len(unique)} unique odds entries")
        print(f"[{datetime.now().isoformat()}] Extracted {len(fixtures)} fixtures")

        # Attach fixtures to result
        self.fixtures = fixtures
        return unique

    async def save_odds(self, odds: list[dict[str, Any]]) -> Path:
        """Save odds to timestamped JSONL file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = self.OUTPUT_DIR / f"flashscore_odds_{ts}.jsonl"
        with outfile.open("w", encoding="utf-8") as f:
            for entry in odds:
                f.write(json.dumps(entry) + "\n")
        print(f"[{datetime.now().isoformat()}] Saved to {outfile}")
        return outfile


async def main():
    async with FlashScoreOddsScraper(headless=True) as scraper:
        odds = await scraper.fetch_odds()
        if odds:
            await scraper.save_odds(odds)
            # Print summary
            print("\n📊 Live Odds Summary:")
            for o in odds[:15]:
                print(f"  {o['team_code']}: {o['odds']} (via {o['source']})")

            # Print fixtures if available
            if hasattr(scraper, 'fixtures') and scraper.fixtures:
                print("\n📅 Fixtures:")
                for f in scraper.fixtures[:10]:
                    print(f"  {f['datetime']} {f['home_team']} vs {f['away_team']}")
        else:
            print("⚠️  No odds extracted — page structure may have changed")
        return odds


if __name__ == "__main__":
    asyncio.run(main())