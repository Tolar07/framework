#!/usr/bin/env python3
"""Test what sport category 34 contains."""

import asyncio
from playwright.async_api import async_playwright

async def test_category_34():
    # Test category 34 with different tournament IDs
    cat_id = 34

    host = "sportybet.com.ng"

    # Test several tournament IDs that might be for different leagues
    test_tournaments = [
        (1, "Possibly Premier League"),
        (2, "Possibly Championship"),
        (3, "Possibly League One"),
        (4, "Possibly League Two"),
        (5, "Possibly Scottish Premiership"),
        (8, "Original Premier League mapping"),
        (23, "Original La Liga mapping"),
        (34, "Original Bundesliga mapping"),
        (35, "Original Ligue 1 mapping"),
        (36, "Original Ligue 2 / Serie B mapping"),
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
                            english_teams = ["Arsenal", "Liverpool", "Man City", "Chelsea", "Tottenham", "Newcastle", "Aston Villa", "West Ham", "Brighton", "Crystal Palace", "Fulham", "Brentford", "Everton", "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich"]
                            found_english = sum(1 for team in teams if any(eng in team for eng in english_teams))

                            if found_english > 0:
                                print(f"  >>> ENGLISH TEAMS FOUND: {found_english}/{len(teams)} <<<")
                            else:
                                # Check for Italian teams
                                italian_teams = ["Inter", "Juventus", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino"]
                                found_italian = sum(1 for team in teams if any(ita in team for ita in italian_teams))
                                if found_italian > 0:
                                    print(f"  >>> ITALIAN TEAMS FOUND: {found_italian}/{len(teams)} <<<")
                                else:
                                    # Check for German teams
                                    german_teams = ["Bayern", "Dortmund", "Leipzig", "Frankfurt", "Leverkusen", "Wolfsburg", "Union", "Freiburg", "Mainz", "Augsburg"]
                                    found_german = sum(1 for team in teams if any(ger in team for ger in german_teams))
                                    if found_german > 0:
                                        print(f"  >>> GERMAN TEAMS FOUND: {found_german}/{len(teams)} <<<")
                                    else:
                                        # Check for French teams
                                        french_teams = ["PSG", "Marseille", "Lyon", "Lille", "Monaco", "Nice", "Rennes", "Reims", "Montpellier", "Toulouse"]
                                        found_french = sum(1 for team in teams if any(fre in team for fre in french_teams))
                                        if found_french > 0:
                                            print(f"  >>> FRENCH TEAMS FOUND: {found_french}/{len(teams)} <<<")
                                        else:
                                            # Check for Spanish teams
                                            spanish_teams = ["Real Madrid", "Barcelona", "Atletico", "Sevilla", "Valencia", "Villarreal", "Betis", "Real Sociedad"]
                                            found_spanish = sum(1 for team in teams if any(spa in team for spa in spanish_teams))
                                            if found_spanish > 0:
                                                print(f"  >>> SPANISH TEAMS FOUND: {found_spanish}/{len(teams)} <<<")
                                            else:
                                                print(f"  Teams don't match major European leagues")
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
    asyncio.run(test_category_34())