#!/usr/bin/env python3
"""Test different sort parameters to see if they change the content displayed."""

import asyncio
from playwright.async_api import async_playwright

async def test_sort_param(param):
    host = "sportybet.com.ng"
    base_url = f"https://{host}/ng/sport/football"
    sort_url = f"{base_url}?sort={param}"

    print(f"Testing sort parameter: {param}")
    print(f"URL: {sort_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(sort_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

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
            return len(rows)

    except Exception as e:
        print(f"Error: {e}")
        return 0

async def main():
    # Test different sort parameters
    print("Testing different sort parameters:")

    # Default (sort=2) - what we've been using
    await test_sort_param(2)

    # Try sort=1 (maybe newest first?)
    await test_sort_param(1)

    # Try sort=3 (maybe oldest first?)
    await test_sort_param(3)

if __name__ == "__main__":
    asyncio.run(main())