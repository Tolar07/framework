#!/usr/bin/env python3
"""Test specific league mappings based on common patterns."""

import asyncio
from playwright.async_api import async_playwright

# Known working IPs for sportybet.com.ng
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

def _resolver_rule():
    host = "sportybet.com.ng"
    rules = []
    for ip in FALLBACK_IPS:
        rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules)

# Test cases for known leagues
TEST_CASES = [
    # (league, country, category_id, tournament_id, expected_teams)
    ("Premier League", "England", 34, 1, ["Arsenal", "Liverpool", "Man City", "Chelsea"]),
    ("Championship", "England", 1, 17, ["Leeds", "Sheffield", "Middlesbrough", "Norwich"]),
    ("Serie A", "Italy", 30, 35, ["Inter", "Juventus", "Milan", "Napoli"]),
    ("Serie B", "Italy", 30, 36, ["Cremonese", "Catanzaro", "Palermo", "Sampdoria"]),
    ("Bundesliga", "Germany", 7, 34, ["Bayern", "Dortmund", "Leipzig", "Frankfurt"]),  # Currently wrong
    ("Ligue 1", "France", 7, 35, ["PSG", "Marseille", "Lyon", "Lille"]),  # Currently wrong
    ("Ligue 2", "France", 7, 36, ["Metz", "Bordeaux", "Annecy", "Guingamp"]),  # Currently wrong
    ("La Liga", "Spain", 31, 23, ["Real Madrid", "Barcelona", "Atletico", "Sevilla"]),
    ("La Liga 2", "Spain", 31, 9, ["Levante", "Oviedo", "Almeria", "Granada"]),
    ("Primeira Liga", "Portugal", 32, 9, ["Porto", "Benfica", "Sporting", "Braga"]),
    ("Turkish Super Lig", "Turkiye", 41, 1, ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor"]),
    ("Russian Premier League", "Russia", 11, 1, ["Zenit", "Spartak", "CSKA", "Lokomotiv"]),
    ("Swiss Super League", "Switzerland", 39, 1, ["Young Boys", "Basel", "Zurich", "Servette"]),
    ("Belgian Pro League", "Belgium", 21, 1, ["Anderlecht", "Club Brugge", "Union SG", "Antwerp"]),
    ("Scottish Premiership", "Scotland", 15, 1, ["Celtic", "Rangers", "Hearts", "Hibs"]),
]

async def test_specific_league(page, league, country, cat_id, tour_id, expected_teams):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"\n{'='*60}")
    print(f"Testing: {league} ({country})")
    print(f"URL: {direct_url}")
    print(f"IDs: category={cat_id}, tournament={tour_id}")

    try:
        await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)

        # Check for fixture rows
        rows = await page.query_selector_all(".m-table-row.match-row")
        print(f"Fixture rows found: {len(rows)}")

        if rows:
            # Extract team names
            teams = []
            for i, row in enumerate(rows[:10]):
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                if home_el and away_el:
                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    if home and away:
                        teams.append(f"{home} v {away}")

            if teams:
                print(f"Sample teams: {teams[:5]}")

                # Check against expected teams
                all_teams_text = " ".join(teams)
                found_expected = []
                for expected in expected_teams:
                    if expected.lower() in all_teams_text.lower():
                        found_expected.append(expected)

                print(f"Expected teams found: {found_expected}")
                score = len(found_expected)
                print(f"Score: {score}/{len(expected_teams)}")

                if score >= 2:
                    print(f"  *** LIKELY CORRECT MAPPING FOR {league} ***")
                    return {
                        "league": league,
                        "country": country,
                        "cat_id": cat_id,
                        "tour_id": tour_id,
                        "works": True,
                        "score": score,
                        "sample_teams": teams[:5]
                    }
                else:
                    print(f"  x Low score - likely incorrect mapping")
                    return {"league": league, "works": False, "reason": f"low score {score}/{len(expected_teams)}"}
            else:
                print("Rows found but no team names extracted")
                return {"league": league, "works": False, "reason": "no team names"}
        else:
            print("No fixture rows found")
            return {"league": league, "works": False, "reason": "no rows"}

    except Exception as e:
        print(f"Error: {e}")
        return {"league": league, "works": False, "reason": str(e)[:100]}

async def main():
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")
    print(f"Launch args: {launch_args}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        results = []
        for league, country, cat_id, tour_id, expected_teams in TEST_CASES:
            result = await test_specific_league(page, league, country, cat_id, tour_id, expected_teams)
            results.append(result)

        await browser.close()

        print("\n\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        correct_count = 0
        for r in results:
            if r.get("works"):
                print(f"OK {r['league']}: cat={r['cat_id']}, tour={r['tour_id']} (score: {r['score']})")
                correct_count += 1
            else:
                print(f"✗ {r['league']}: FAILED - {r.get('reason', 'unknown')}")

        print(f"\nCorrect mappings: {correct_count}/{len(TEST_CASES)}")

if __name__ == "__main__":
    asyncio.run(main())