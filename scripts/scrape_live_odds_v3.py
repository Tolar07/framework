#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Odds Scraper v3 — FlashScore Premier League
Production-ready: extracts outright winner + 1X2 match odds with bookmaker attribution.
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
    # Anchor output to the repo's data/live_odds so readers find it regardless of CWD
    OUTPUT_DIR = Path(__file__).parent.parent / "data" / "live_odds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Known team codes for Premier League
    TEAM_CODES = {
        "ARS": "Arsenal", "MCI": "Man City", "LIV": "Liverpool",
        "CHE": "Chelsea", "TOT": "Tottenham", "MUN": "Man Utd",
        "NEW": "Newcastle", "BHA": "Brighton", "AVL": "Aston Villa",
        "WHU": "West Ham", "FUL": "Fulham", "BRE": "Brentford",
        "CRY": "Crystal Palace", "EVE": "Everton", "WOL": "Wolves",
        "BOU": "Bournemouth", "NFO": "Nott'm Forest", "LEI": "Leicester",
        "SOU": "Southampton", "IPS": "Ipswich", "LEE": "Leeds",
        "HUL": "Hull", "SUN": "Sunderland", "COV": "Coventry",
        "NOR": "Norwich", "WAT": "Watford", "BUR": "Burnley",
    }

    def __init__(self, headless: bool = True, max_matches: int = 10):
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

    def _parse_team_names(self, text: str) -> tuple[str, str]:
        """Parse home/away team names from FlashScore fixture text."""
        # Text format: "21.08. 20:00ArsenalCoventry--"
        # Remove date/time prefix
        text = re.sub(r'^\d{2}\.\d{2}\.\s*\d{2}:\d{2}', '', text.strip())
        text = text.rstrip('-')

        # Try to split known team names
        for code, name in self.TEAM_CODES.items():
            if text.startswith(name):
                # Found home team, rest is away
                rest = text[len(name):]
                for code2, name2 in self.TEAM_CODES.items():
                    if rest == name2 or rest.startswith(name2):
                        return name, name2
                # If not found, try common abbreviations
                return name, rest

        # Fallback: split on capital letters (camel case)
        # "ArsenalCoventry" -> ["Arsenal", "Coventry"]
        parts = re.findall(r'[A-Z][a-z]+', text)
        if len(parts) >= 2:
            return parts[0], parts[1]
        return text[:len(text)//2], text[len(text)//2:]

    async def scrape_outright_winner(self) -> list[dict[str, Any]]:
        """Scrape outright winner odds from league page."""
        print(f"[{datetime.now().isoformat()}] Scraping outright winner odds...")
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(8000)

        odds_elements = await self.page.query_selector_all("[class*='odd']")
        odds_parts = []
        for el in odds_elements[:10]:
            text = await el.text_content()
            if text:
                odds_parts.append(text)
        odds_text = " ".join(odds_parts)

        # Extract team_code + odds pairs
        # Pattern: 3 uppercase letters followed by decimal odds
        pattern = re.compile(r'([A-Z]{3})(\d\.\d{2})')
        raw_pairs = [(m.group(1), float(m.group(2))) for m in pattern.finditer(odds_text)]

        # Deduplicate: keep unique (team, odds) pairs
        seen = set()
        results = []
        for team_code, odds in raw_pairs:
            key = (team_code, odds)
            if key not in seen:
                seen.add(key)
                results.append({
                    "type": "outright_winner",
                    "team_code": team_code,
                    "team_name": self.TEAM_CODES.get(team_code, team_code),
                    "odds": odds,
                    "market": "league_winner",
                    "source": "flashscore_league_page",
                    "timestamp": datetime.now().isoformat()
                })

        print(f"[{datetime.now().isoformat()}] Found {len(results)} unique outright winner odds")
        return results

    def _extract_bookmaker_1x2(self, text: str) -> list[dict[str, float]]:
        """
        Extract 1X2 odds grouped by bookmaker from match detail page.
        FlashScore format: "1X2 1.177.5013.00 --- 1.146.5017.00 ..."
        Odds are often concatenated without spaces (e.g. "1.177.5013.00").
        Each bookmaker section starts with "1X2" followed by three odds: Home, Draw, Away.
        """
        bookmakers = []

        # Normalize text
        text = text.replace('\n', ' ').replace('\r', ' ')

        # Split by "1X2" - each section after this should contain 3 odds for one bookmaker
        sections = re.split(r'1X2', text)

        for section in sections[1:]:  # Skip first section (before first 1X2)
            # Remove non-odds text (like "Place a bet", "Pre-match odds", etc.)
            # Extract all decimal numbers that look like odds: X.YY where X is 1-2 digits, YY is 2 digits
            # Pattern handles concatenated odds: "1.177.5013.00" -> ["1.17", "7.50", "13.00"]
            odds = re.findall(r'(\d{1,2}\.\d{2})', section)
            if len(odds) >= 3:
                try:
                    home, draw, away = float(odds[0]), float(odds[1]), float(odds[2])
                    # Sanity check
                    if (1.01 <= home <= 50 and 1.01 <= draw <= 50 and 1.01 <= away <= 50):
                        bookmakers.append({
                            "home": home, "draw": draw, "away": away,
                            "raw_odds": [home, draw, away]
                        })
                except (ValueError, IndexError):
                    pass

        return bookmakers

    async def scrape_match_odds(self, match_index: int) -> list[dict[str, Any]]:
        """Click on a match and scrape 1X2 odds from all bookmakers."""
        print(f"[{datetime.now().isoformat()}] Scraping match {match_index} odds...")

        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(5000)

        match_elements = await self.page.query_selector_all("[class*='event__match']")
        if match_index >= len(match_elements):
            print(f"  Match index {match_index} out of range ({len(match_elements)} matches)")
            return []

        # Get match info
        match_text = await match_elements[match_index].text_content()
        home_team, away_team = self._parse_team_names(match_text)

        # Extract date/time
        dt_match = re.search(r'(\d{2}\.\d{2}\.\s*\d{2}:\d{2})', match_text or "")
        match_datetime = dt_match.group(1) if dt_match else ""

        # Click the match
        try:
            await match_elements[match_index].click()
            await self.page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  Failed to click match: {e}")
            return []

        # Get odds from match detail page
        odds_elements = await self.page.query_selector_all("[class*='odd'], [class*='Odd']")
        odds_parts = []
        for el in odds_elements:
            text = await el.text_content()
            if text:
                odds_parts.append(text)
        all_odds_text = " ".join(odds_parts)

        bookmakers = self._extract_bookmaker_1x2(all_odds_text)

        # Deduplicate bookmakers by odds triplet
        seen = set()
        unique_bookmakers = []
        for bm in bookmakers:
            key = (bm["home"], bm["draw"], bm["away"])
            if key not in seen:
                seen.add(key)
                unique_bookmakers.append(bm)

        results = []
        for bm_idx, bm in enumerate(unique_bookmakers):
            results.append({
                "type": "match_1x2",
                "match_index": match_index,
                "bookmaker_index": bm_idx,
                "home_team": home_team,
                "away_team": away_team,
                "match_datetime": match_datetime,
                "odds_home": bm["home"],
                "odds_draw": bm["draw"],
                "odds_away": bm["away"],
                "market": "match_winner",
                "source": "flashscore_match_detail",
                "timestamp": datetime.now().isoformat()
            })

        print(f"[{datetime.now().isoformat()}] Found {len(results)} unique bookmaker odds for {home_team} vs {away_team}")
        return results

    async def scrape_all(self) -> dict[str, list[dict[str, Any]]]:
        """Scrape both outright and match odds."""
        outright = await self.scrape_outright_winner()

        match_odds = []
        for i in range(min(self.max_matches, 15)):
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
    async with FlashScoreOddsScraper(headless=True, max_matches=5) as scraper:
        results = await scraper.scrape_all()
        scraper.save_results(results)

        # Print summary
        print("\n" + "="*60)
        print("📊 SCRAPING SUMMARY")
        print("="*60)

        print(f"\n🏆 OUTRIGHT WINNER ({len(results['outright_winner'])} unique entries):")
        for o in results['outright_winner']:
            print(f"  {o['team_name']} ({o['team_code']}): {o['odds']}")

        print(f"\n⚽ MATCH 1X2 ODDS ({len(results['match_1x2'])} bookmaker entries):")
        current_match = None
        for m in results['match_1x2']:
            match_key = f"{m['home_team']} vs {m['away_team']}"
            if match_key != current_match:
                current_match = match_key
                print(f"\n  {m['match_datetime']} {match_key}")
            print(f"    BM{m['bookmaker_index']}: 1={m['odds_home']}  X={m['odds_draw']}  2={m['odds_away']}")


if __name__ == "__main__":
    asyncio.run(main())