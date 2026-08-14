#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Odds Scraper v2 — FlashScore Premier League
Extracts both outright winner odds and 1X2 match odds from multiple bookmakers.
Solves ID397/FIX4: Automated price feed from JS-locked sources.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright


class FlashScoreOddsScraper:
    """Scrapes live odds from FlashScore Premier League page."""

    BASE_URL = "https://www.flashscore.com/football/england/premier-league/"
    OUTPUT_DIR = Path("data/live_odds")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(self, headless: bool = True, max_matches: int = 5):
        self.headless = headless
        self.max_matches = max_matches
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

    def _extract_team_codes(self, text: str) -> list[tuple[str, float]]:
        """Extract team code + odds pairs from text."""
        # Pattern: 3 uppercase letters followed by decimal odds
        pattern = re.compile(r'([A-Z]{3})(\d\.\d{2})')
        return [(m.group(1), float(m.group(2))) for m in pattern.finditer(text)]

    def _extract_1x2_odds(self, text: str) -> list[dict[str, float]]:
        """Extract 1X2 triplets from text (1, X, 2 odds)."""
        # Pattern: three consecutive decimal odds
        # Look for sequences like "1.177.5013.00" or "1.17 7.50 13.00"
        pattern = re.compile(r'(\d\.\d{2})(\d\.\d{2})(\d\.\d{2})')
        results = []
        for m in pattern.finditer(text):
            try:
                home, draw, away = float(m.group(1)), float(m.group(2)), float(m.group(3))
                # Basic sanity check: odds should be reasonable
                if 1.01 <= home <= 50 and 1.01 <= draw <= 50 and 1.01 <= away <= 50:
                    results.append({"1": home, "X": draw, "2": away})
            except ValueError:
                pass
        return results

    async def scrape_outright_winner(self) -> list[dict[str, Any]]:
        """Scrape outright winner odds from league page."""
        print(f"[{datetime.now().isoformat()}] Scraping outright winner odds...")
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(8000)

        # Get odds elements
        odds_elements = await self.page.query_selector_all("[class*='odd']")
        odds_text = ""
        for el in odds_elements[:10]:
            text = await el.text_content()
            if text:
                odds_text += text + " "

        results = []
        for team_code, odds in self._extract_team_codes(odds_text):
            results.append({
                "type": "outright_winner",
                "team_code": team_code,
                "odds": odds,
                "market": "league_winner",
                "source": "flashscore_league_page",
                "timestamp": datetime.now().isoformat()
            })

        print(f"[{datetime.now().isoformat()}] Found {len(results)} outright winner odds")
        return results

    async def scrape_match_odds(self, match_index: int) -> list[dict[str, Any]]:
        """Click on a match and scrape 1X2 odds."""
        print(f"[{datetime.now().isoformat()}] Scraping match {match_index} odds...")

        # Re-navigate to league page
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(5000)

        match_elements = await self.page.query_selector_all("[class*='event__match']")
        if match_index >= len(match_elements):
            print(f"  Match index {match_index} out of range ({len(match_elements)} matches)")
            return []

        # Get match info first
        match_text = await match_elements[match_index].text_content()
        match_info = self._parse_match_info(match_text)

        # Click the match
        try:
            await match_elements[match_index].click()
            await self.page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  Failed to click match: {e}")
            return []

        # Get odds from match detail page
        odds_elements = await self.page.query_selector_all("[class*='odd'], [class*='Odd']")
        all_odds_text = ""
        for el in odds_elements:
            text = await el.text_content()
            if text:
                all_odds_text += text + " "

        results = []
        for triplet in self._extract_1x2_odds(all_odds_text):
            results.append({
                "type": "match_1x2",
                "match_index": match_index,
                "home_team": match_info.get("home", ""),
                "away_team": match_info.get("away", ""),
                "match_datetime": match_info.get("datetime", ""),
                "odds_1": triplet["1"],
                "odds_X": triplet["X"],
                "odds_2": triplet["2"],
                "market": "match_winner",
                "source": "flashscore_match_detail",
                "timestamp": datetime.now().isoformat()
            })

        print(f"[{datetime.now().isoformat()}] Found {len(results)} bookmaker odds for match {match_index}")
        return results

    def _parse_match_info(self, text: str) -> dict[str, str]:
        """Parse fixture info from match element text."""
        # Format: "21.08. 20:00ArsenalCoventry--"
        pattern = re.compile(r'(\d{2}\.\d{2}\.\s*\d{2}:\d{2})([A-Za-z\s]+?)([A-Z][a-z]+)--')
        m = pattern.search(text.strip())
        if m:
            return {
                "datetime": m.group(1).strip(),
                "home": m.group(2).strip(),
                "away": m.group(3).strip()
            }
        return {"datetime": "", "home": "", "away": ""}

    async def scrape_all(self) -> dict[str, list[dict[str, Any]]]:
        """Scrape both outright and match odds."""
        outright = await self.scrape_outright_winner()

        # Scrape first few matches for 1X2 odds
        match_odds = []
        for i in range(min(self.max_matches, 10)):
            try:
                odds = await self.scrape_match_odds(i)
                match_odds.extend(odds)
            except Exception as e:
                print(f"  Error scraping match {i}: {e}")

        return {
            "outright_winner": outright,
            "match_1x2": match_odds
        }

    def save_results(self, results: dict[str, list[dict[str, Any]]]) -> Path:
        """Save results to JSONL files."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = self.OUTPUT_DIR / f"flashscore_odds_{ts}.jsonl"

        with outfile.open("w", encoding="utf-8") as f:
            for category, entries in results.items():
                for entry in entries:
                    entry["category"] = category
                    f.write(json.dumps(entry) + "\n")

        print(f"[{datetime.now().isoformat()}] Saved {sum(len(v) for v in results.values())} entries to {outfile}")
        return outfile


async def main():
    async with FlashScoreOddsScraper(headless=True, max_matches=3) as scraper:
        results = await scraper.scrape_all()
        scraper.save_results(results)

        # Print summary
        print("\n" + "="*60)
        print("📊 SCRAPING SUMMARY")
        print("="*60)

        print(f"\n🏆 OUTRIGHT WINNER ({len(results['outright_winner'])} entries):")
        for o in results['outright_winner']:
            print(f"  {o['team_code']}: {o['odds']}")

        print(f"\n⚽ MATCH 1X2 ODDS ({len(results['match_1x2'])} bookmaker entries):")
        current_match = None
        for m in results['match_1x2']:
            match_key = f"{m['home_team']} vs {m['away_team']}"
            if match_key != current_match:
                current_match = match_key
                print(f"\n  {m['match_datetime']} {match_key}")
            print(f"    1: {m['odds_1']}  X: {m['odds_X']}  2: {m['odds_2']}")


if __name__ == "__main__":
    asyncio.run(main())