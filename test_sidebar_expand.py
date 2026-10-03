#!/usr/bin/env python3
"""Test sidebar navigation by expanding country and clicking league."""

import asyncio
from playwright.async_api import async_playwright

from booking.league_map import SPORTYBET_LEAGUES

async def test_sidebar_expand(league_name):
    host = "sportybet.com.ng"
    homepage_url = f"https://{host}/ng/sport/football?source=sport_menu&sort=2"
    resolver_rule = "MAP sportybet.com.ng:443 104.21.10.148,MAP sportybet.com.ng:443 172.67.163.154"

    print(f"Testing sidebar expand for: '{league_name}'")
    print(f"Homepage: {homepage_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    f"--host-resolver-rules={resolver_rule}"
                ]
            )
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

            # Get country and league from mapping
            bookmaker_league = SPORTYBET_LEAGUES.get(league_name)
            if not bookmaker_league:
                print(f"  ERROR: League '{league_name}' not found in SPORTYBET_LEAGUES")
                await browser.close()
                return False

            country = bookmaker_league.country
            league = bookmaker_league.league
            print(f"  Country: {country}, League: {league}")

            # Dismiss overlays
            await _dismiss_overlays(page)

            # Wait for sidebar to be present
            sidebar = page.locator('.sidebar')
            await sidebar.wait_for(timeout=10000)
            print(f"  Sidebar is present")

            # Click country in sidebar to expand it
            country_locator = page.locator(f'.sidebar .country-item:has-text("{country}")').first
            if await country_locator.count() == 0:
                # fallback to text selector
                country_locator = page.locator(f'text={country}').first
                if await country_locator.count() == 0:
                    print(f"  ERROR: Could not find country '{country}' in sidebar")
                    await browser.close()
                    return False
            print(f"  Clicking country: {country}")
            await country_locator.click()
            await page.wait_for_timeout(2000)  # wait for expansion

            # Click league under that country
            # Now the league should be visible under the country
            league_locator = page.locator(f'.sidebar .league-item:has-text("{league}")').first
            if await league_locator.count() == 0:
                # fallback to text selector
                league_locator = page.locator(f'text={league}').first
                if await league_locator.count() == 0:
                    print(f"  ERROR: Could not find league '{league}' under country '{country}' in sidebar")
                    await browser.close()
                    return False
            print(f"  Clicking league: {league}")
            await league_locator.click()
            await page.wait_for_timeout(4000)

            # Check if we have fixture rows
            rows = await page.query_selector_all(".m-table-row.match-row")
            print(f"  Found {len(rows)} match rows after sidebar navigation")

            if rows:
                # Extract first few teams
                teams = []
                for i, row in enumerate(rows[:3]):
                    home_el = await row.query_selector(".teams .home-team")
                    away_el = await row.query_selector(".teams .away-team")
                    if home_el and away_el:
                        home = (await home_el.inner_text()).strip()
                        away = (await away_el.inner_text()).strip()
                        if home and away:
                            teams.append(f"{home} v {away}")
                print(f"  Sample teams: {teams}")

            await browser.close()
            return len(rows) > 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def _dismiss_overlays(page: object) -> None:
    """Dismiss any overlays that might block clicks."""
    selectors = [
        ".onesignal-slidedown-container",
        ".onesignal-popover-container",
        ".onesignal-popover",
        "[class*=\"onesignal\"]",
        ".modal",
        ".popup",
        "[id*=\"onesignal\"]",
    ]
    for selector in selectors:
        try:
            els = await page.query_selector_all(selector)
            for el in els:
                if await el.is_visible():
                    await el.evaluate("el => el.remove()")
                    await page.wait_for_timeout(500)
        except Exception:
            pass

if __name__ == "__main__":
    # Test a few leagues that are not in popular-list
    test_leagues = [
        "Belgian Pro League",
        "Russian Premier League",
        "Scottish Premiership",
        "Swiss Super League",
        "Turkish Super Lig",
    ]

    print("=== Testing sidebar expand navigation ===")
    for league in test_leagues:
        print()
        found = asyncio.run(test_sidebar_expand(league))
        print(f"Result for '{league}': {'SUCCESS' if found else 'FAILED'}")