#!/usr/bin/env python3
"""Test what we get when we use mapping (32, 8)."""

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

                # Try to guess what league this might be
                german_teams = ["Magdeburg", "Holstein Kiel", "Darmstadt", "Hannover", "St. Pauli", "Kaiserslautern", "Union Berlin", "Eintracht Frankfurt", "Werder Bremen", "Hamburg", "Nuremberg", "Schalke", "Hertha Bochum", "Fortuna Düsseldorf"]
                english_teams = ["Arsenal", "Liverpool", "Man City", "Man United", "Chelsea", "Tottenham", "Newcastle", "Brighton", "Aston Villa", "West Ham", "Crystal Palace", "Fulham", "Brentford", "Everton", "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich", "Leeds", "Sheffield", "Middlesbrough", "Norwich", "Watford", "West Brom", "Coventry", "Preston", "Cardiff", "Swansea", "Bristol City", "Portsmouth", "Reading", "Blackburn", "Burnley", "QPR", "Hull"]
                spanish_teams = ["Real Madrid", "Barcelona", "Atletico", "Sevilla", "Valencia", "Villarreal", "Betis", "Real Sociedad", "Athletic Bilbao", "Celta Vigo", "Eibar", "Granada", "Alaves", "Levante", "Valladolid", "Getafe", "Elche", "Alcorcon", "Las Palmas"]
                italian_teams = ["Inter", "Juventus", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino", "Genoa", "Cagliari", "Sassuolo", "Empoli", "Spezia", "Lecce", "Venezia", "Monza", "Salernitana", "Frosinone"]
                french_teams = ["PSG", "Marseille", "Lyon", "Lille", "Monaco", "Nice", "Rennes", "Reims", "Montpellier", "Toulouse", "Strasbourg", "Lens", "Brest", "Clermont", "Metz", "Auxerre", "Angers", "Le Havre", "Saint-Etienne"]

                def count_matches(team_list, teams_text):
                    return sum(1 for team in team_list if any(team.lower() in text.lower() for text in teams_text))

                matches = {
                    "German": count_matches(german_teams, teams),
                    "English": count_matches(english_teams, teams),
                    "Spanish": count_matches(spanish_teams, teams),
                    "Italian": count_matches(italian_teams, teams),
                    "French": count_matches(french_teams, teams),
                }

                print(f"League likelihood scores: {matches}")
                best_league = max(matches, key=matches.get)
                print(f"Best match: {best_league} (score: {matches[best_league]})")

            await browser.close()
            return teams

    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    # Test the mapping we think is for Premier League
    asyncio.run(test_mapping(32, 8, "Premier League mapping (32, 8)"))