#!/usr/bin/env python3
"""Test if the sidebar selector works correctly."""

import asyncio
from playwright.async_api import async_playwright

async def test_sidebar_search(league_name):
    host = "sportybet.com.ng"
    homepage_url = f"https://{host}/ng/sport/football?source=sport_menu&sort=2"

    # Resolver rules - same as used in cache builder
    resolver_rule = "MAP sportybet.com.ng:443 104.21.10.148,MAP sportybet.com.ng:443 172.67.163.154"

    print(f"Testing search for: '{league_name}'")

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
            await page.wait_for_timeout(5000)

            # Test the exact selector we use in rebuild_cache.py
            league_link = page.locator(
                f'.popular-list .top-link:has(.top-link-item:has-text("{league_name}"))'
            ).first

            count = await league_link.count()
            print(f"Selector '.popular-list .top-link:has(.top-link-item:has-text(\"{league_name}\"))' found {count} matches")

            if count > 0:
                # Get the actual text of what we found
                link_el = league_link.locator('.top-link-item').first
                actual_text = await link_el.inner_text()
                print(f"  Actual text found: '{actual_text.strip()}'")

                # Try to click it
                await league_link.click()
                await page.wait_for_timeout(3000)

                # Check if we navigated somewhere different
                new_url = page.url
                print(f"  URL after click: {new_url}")

                # Look for match rows to see if we got fixture data
                await page.wait_for_timeout(2000)  # Give time for content to load
                rows = await page.query_selector_all(".m-table-row.match-row")
                print(f"  Found {len(rows)} match rows after click")

                if rows:
                    # Extract sample teams
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
            return count > 0

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Test searching for some leagues that should be in the popular-list
    test_leagues = [
        "Premier League",
        "La Liga",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
        "Championship"  # This one might not be in the popular-list we saw
    ]

    print("=== Testing sidebar search for various leagues ===")
    for league in test_leagues:
        print()
        found = asyncio.run(test_sidebar_search(league))
        print(f"Result for '{league}': {'FOUND' if found else 'NOT FOUND'}")