#!/usr/bin/env python3
"""Test what category 1 contains (hypothesis: English football)."""

import asyncio
from playwright.async_api import async_playwright

async def test_category_1():
    # Test category 1 with different tournament IDs
    cat_id = 1

    host = "sportybet.com.ng"

    # Test several tournament IDs that might be for different English leagues
    test_tournaments = [
        (16, "Possibly Championship (original is 17)"),
        (17, "Championship (original mapping)"),
        (18, "EFL Cup (original mapping)"),
        (19, "Possibly League One"),
        (20, "Possibly League Two"),
        (21, "Possibly Premier League"),
        (22, "Possibly Premier League"),
        (23, "Possibly Premier League"),
        (24, "Possibly Premier League"),
        (25, "Possibly Premier League"),
        (26, "Possibly Premier League"),
        (27, "Possibly Premier League"),
        (28, "Possibly Premier League"),
        (29, "Possibly Premier League"),
        (30, "Possibly Premier League"),
        (31, "Possibly Premier League"),
        (32, "Possibly Premier League"),
    ]

    print(f"Testing category {cat_id} with various tournament IDs")
    print("=" * 60)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            for tour_id, description in test_tournaments:
                direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

                print(f"\nTesting: cat={cat_id}, tour={tour_id} ({description})")
                print(f"URL: {direct_url}")

                try:
                    await page.goto(direct_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

                    # Check for fixture rows
                    rows = await page.query_selector_all(".m-table-row.match-row")
                    print(f"Fixture rows found: {len(rows)}")

                    if rows and len(rows) > 0:
                        # Extract team names from first few rows
                        teams = []
                        for i, row in enumerate(rows[:3]):
                            home_el = await row.query_selector(".teams .home-team")
                            away_el = await row.query_selector(".teams .away-team")
                            if home_el and away_el:
                                home = (await home_el.inner_text()).strip()
                                away = (await away_el.inner_text()).strip()
                                if home and away:
                                    teams.append(f"{home} v {away}")

                        if teams:
                            print(f"Sample teams: {teams[:3]}")

                            # Quick check for English teams
                            english_teams = ["Arsenal", "Liverpool", "Man City", "Chelsea", "Tottenham", "Newcastle", "Aston Villa", "West Ham", "Brighton", "Crystal Palace", "Fulham", "Brentford", "Everton", "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich", "Leeds", "Sheffield", "Sunderland", "Middlesbrough", "Norwich", "Watford", "West Brom", "Coventry", "Preston", "Cardiff", "Swansea", "Bristol City", "Hull", "QPR", "Blackburn", "Millwall", "Plymouth", "Stoke", "Oxford", "Derby", "Portsmouth", "Derby", "Oxford", "Peterborough", "Bolton", "Stockport", "Wrexham", "Mansfield", "Doncaster", "Carlisle"]
                            found_english = sum(1 for team in teams if any(eng in team for eng in english_teams))

                            if found_english > 0:
                                print(f"  >>> ENGLISH TEAMS FOUND: {found_english}/{len(teams)} <<<")
                                # If we found English teams, this might be correct
                                if tour_id == 21:  # Let's check this one more carefully
                                    print(f"  *** POTENTIAL PREMIER LEAGUE MAPPING: cat={cat_id}, tour={tour_id} ***")
                            else:
                                # Check for Scottish teams
                                scottish_teams = ["Celtic", "Rangers", "Hearts", "Hibs", "Aberdeen", "St. Mirren", "Motherwell", "Dundee", "Kilmarnock", "St. Johnstone", "Ross County", "Falkirk"]
                                found_scottish = sum(1 for team in teams if any(sco in team for sco in scottish_teams))
                                if found_scottish > 0:
                                    print(f"  >>> SCOTTISH TEAMS FOUND: {found_scottish}/{len(teams)} <<<")
                                else:
                                    print(f"  Teams don't match English/Scottish leagues")
                        else:
                            print("  No team names extracted")
                    else:
                        print("  No fixture rows found")

                except Exception as e:
                    print(f"  Error: {str(e)[:50]}")

            await browser.close()

    except Exception as e:
        print(f"Overall error: {e}")

if __name__ == "__main__":
    asyncio.run(test_category_1())