#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live Odds Scraper v3 — FlashScore multi-league fixtures + odds.
Refactored 2026-08-16: iterates ALL whitelisted leagues via FLASHSCORE_LEAGUES map.
Produces match_1x2 JSONL entries (home/away/datetime) for the verification gate.
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

# Import the ratified FlashScore league mapping.
# NOTE: repo root also has a config.py module that SHADOWS the config/ package,
# so `from config.flashscore_leagues import` can fail. Load the file directly
# via importlib to avoid the package/module collision (HR35: one source of truth).
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT))
def _load_flashscore_map():
    fallback = ({"Premier League": "england/premier-league"},
                "https://www.flashscore.com/football/{slug}/")
    try:
        from config.flashscore_leagues import FLASHSCORE_LEAGUES, BASE_URL
        return FLASHSCORE_LEAGUES, BASE_URL
    except ImportError:
        pass
    # Direct file load (collision-safe)
    import importlib.util
    _p = _REPO_ROOT / "config" / "flashscore_leagues.py"
    if not _p.exists():
        return fallback
    _spec = importlib.util.spec_from_file_location("flashscore_leagues", _p)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return _mod.FLASHSCORE_LEAGUES, _mod.BASE_URL

FLASHSCORE_LEAGUES, BASE_URL = _load_flashscore_map()


class FlashScoreFixturesScraper:
    """Scrapes fixtures (match_1x2) from FlashScore for all mapped leagues."""

    OUTPUT_DIR = Path(__file__).parent.parent / "data" / "live_odds"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __init__(
        self,
        headless: bool = True,
        leagues: Optional[List[str]] = None,
        max_matches_per_league: int = 50,
    ):
        self.headless = headless
        self.leagues = leagues or list(FLASHSCORE_LEAGUES.keys())
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

    async def scrape_league_fixtures(self, league_name: str) -> List[dict[str, Any]]:
        """Scrape match_1x2 fixtures for a single league."""
        slug = FLASHSCORE_LEAGUES.get(league_name)
        if not slug:
            print(f"  [{datetime.now().isoformat()}] {league_name}: NOT MAPPED")
            return []

        url = BASE_URL.format(slug=slug)
        print(f"  [{datetime.now().isoformat()}] {league_name}: fetching {url}")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  [{datetime.now().isoformat()}] {league_name}: navigation failed: {e}")
            return []

        # Find match rows
        match_elements = await self.page.query_selector_all("[class*='event__match']")
        print(f"  [{datetime.now().isoformat()}] {league_name}: found {len(match_elements)} match rows")

        results = []
        for idx, el in enumerate(match_elements[:self.max_matches]):
            try:
                # Extract home/away from specific participant elements
                home_el = await el.query_selector(".event__homeParticipant")
                away_el = await el.query_selector(".event__awayParticipant")
                time_el = await el.query_selector(".event__time, .event__stageTime")

                if not home_el or not away_el:
                    continue

                home_team = (await home_el.text_content() or "").strip()
                away_team = (await away_el.text_content() or "").strip()

                # Get team name from image alt if available (more reliable)
                img_h = await home_el.query_selector("img")
                if img_h:
                    home_team = await img_h.get_attribute("alt") or home_team

                img_a = await away_el.query_selector("img")
                if img_a:
                    away_team = await img_a.get_attribute("alt") or away_team

                match_datetime = (await time_el.text_content() or "").strip() if time_el else ""

                if not home_team or not away_team:
                    continue

                results.append({
                    "type": "match_1x2",
                    "league": league_name,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_datetime": match_datetime,
                    "market": "match_winner",
                    "source": "flashscore_fixtures",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"    match {idx} parse error: {e}")
                continue

        print(f"  [{datetime.now().isoformat()}] {league_name}: parsed {len(results)} fixtures")
        return results

    async def scrape_all(self) -> List[dict[str, Any]]:
        """Scrape fixtures for all configured leagues."""
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
        """Save results to JSONL file."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outfile = self.OUTPUT_DIR / f"flashscore_odds_{ts}.jsonl"

        with outfile.open("w", encoding="utf-8") as f:
            for entry in results:
                f.write(json.dumps(entry) + "\n")

        print(f"[{datetime.now().isoformat()}] Saved {len(results)} entries to {outfile}")
        return outfile


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="FlashScore fixtures scraper")
    parser.add_argument("--leagues", nargs="*", help="Specific league names to scrape")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--max-matches", type=int, default=50)
    args = parser.parse_args()

    async with FlashScoreFixturesScraper(
        headless=args.headless,
        leagues=args.leagues,
        max_matches_per_league=args.max_matches,
    ) as scraper:
        results = await scraper.scrape_all()
        scraper.save_results(results)


if __name__ == "__main__":
    asyncio.run(main())