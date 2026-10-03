#!/usr/bin/env python3
"""Test what we get when we use the Champions League mapping (393, 7)."""

import asyncio
from playwright.async_api import async_playwright

async def test_mapping(cat_id, tour_id, description):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"\nTesting {description}")
    print(f"URL: {direct_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

            # Get the actual URL after any redirects
            actual_url = page.url
            print(f"Actual URL after navigation: {actual_url}")

            # Get page title
            title = await page.title()
            print(f"Page title: {title}")

            # Look for match rows
            rows = await page.query_selector_all(".m-table-row.match-row")
            print(f"Found {len(rows)} match rows")

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
            return actual_url, title, teams

    except Exception as e:
        print(f"Error: {e}")
        return None, None, []

if __name__ == "__main__":
    # Test the Champions League mapping
    asyncio.run(test_mapping(393, 7, "Champions League mapping (393, 7)"))