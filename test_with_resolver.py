#!/usr/bin/env python3
"""Test URL navigation with explicit resolver rules."""

import asyncio
from playwright.async_api import async_playwright

async def test_with_resolver_rules(cat_id, tour_id, description):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    # Resolver rules - same as used in cache builder
    resolver_rule = "MAP sportybet.com.ng:443 104.21.10.148,MAP sportybet.com.ng:443 172.67.163.154"

    print(f"\nTesting {description} with resolver rules")
    print(f"URL: {direct_url}")
    print(f"Resolver rule: {resolver_rule}")

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
    # Test a few mappings with explicit resolver rules
    print("=== Testing mappings with explicit resolver rules ===")

    # Test Premier League mapping
    url1, title1, teams1 = asyncio.run(test_with_resolver_rules(32, 8, "Premier League (32, 8)"))

    # Test Championship mapping
    url2, title2, teams2 = asyncio.run(test_with_resolver_rules(1, 17, "Championship (1, 17)"))

    # Test Bundesliga mapping
    url3, title3, teams3 = asyncio.run(test_with_resolver_rules(7, 34, "Bundesliga (7, 34)"))

    # Test Serie A mapping
    url4, title4, teams4 = asyncio.run(test_with_resolver_rules(30, 35, "Serie A (30, 35)"))

    print("\n=== SUMMARY WITH RESOLVER RULES ===")
    print(f"Premier League URL:  {url1}")
    print(f"Championship URL:    {url2}")
    print(f"Bundesliga URL:      {url3}")
    print(f"Serie A URL:         {url4}")

    print(f"\nPremier League title: {title1}")
    print(f"Championship title:   {title2}")
    print(f"Bundesliga title:     {title3}")
    print(f"Serie A title:        {title4}")

    print(f"\nPremier League teams:  {teams1}")
    print(f"Championship teams:    {teams2}")
    print(f"Bundesliga teams:      {teams3}")
    print(f"Serie A teams:         {teams4}")