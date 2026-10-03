#!/usr/bin/env python3
"""Simple test to verify current Premier League mapping."""

import asyncio
from playwright.async_api import async_playwright

async def test_current_mapping():
    # Current mapping for Premier League: (32, 8)
    cat_id = 32
    tour_id = 8

    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"Testing current mapping: {cat_id}/{tour_id}")
    print(f"URL: {direct_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

            # Check for fixture rows
            rows = await page.query_selector_all(".m-table-row.match-row")
            print(f"Fixture rows found: {len(rows)}")

            if rows:
                # Extract team names
                teams = []
                for i, row in enumerate(rows[:5]):
                    home_el = await row.query_selector(".teams .home-team")
                    away_el = await row.query_selector(".teams .away-team")
                    if home_el and away_el:
                        home = (await home_el.inner_text()).strip()
                        away = (await away_el.inner_text()).strip()
                        if home and away:
                            teams.append(f"{home} v {away}")

                print(f"Sample teams: {teams[:5]}")

                # Check if these are English teams
                english_teams = ["Arsenal", "Liverpool", "Man City", "Chelsea", "Tottenham", "Newcastle", "Aston Villa", "West Ham", "Brighton", "Crystal Palace"]
                found_english = sum(1 for team in teams if any(expected in team for expected in english_teams))

                print(f"English teams found: {found_english}/{len(teams)}")

                if found_english >= 2:
                    print("✓ Likely correct mapping")
                    return True
                else:
                    print("✗ Likely incorrect mapping")
                    return False

            else:
                print("No fixture rows found")
                return False

    except Exception as e:
        print(f"Error: {e}")
        return False

async def main():
    result = await test_current_mapping()
    if result:
        print("\nCurrent mapping appears to be working correctly")
    else:
        print("\nCurrent mapping appears to be incorrect")

if __name__ == "__main__":
    asyncio.run(main())