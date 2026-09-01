#!/usr/bin/env python3
"""Simple test to verify navigation and data extraction works."""

import asyncio
from playwright.async_api import async_playwright

async def test_navigation():
    host = "sportybet.com.ng"
    # Try a known working URL pattern - let's try to get ANY data
    direct_url = f"https://{host}/ng/sport/football?source=sport_menu&sort=2"

    print(f"Testing basic navigation: {direct_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

            # Get page title
            title = await page.title()
            print(f"Page title: {title}")

            # Look for any match rows
            rows = await page.query_selector_all(".m-table-row.match-row")
            print(f"Found {len(rows)} match rows on homepage")

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

                print(f"Sample teams: {teams}")

            await browser.close()
            return True

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_navigation())
    print(f"Test result: {'PASS' if result else 'FAIL'}")