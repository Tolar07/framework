#!/usr/bin/env python3
"""Try to find correct category/tournament IDs for Premier League."""

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

# Known Premier League teams to verify correct mapping
PREMIER_LEAGUE_TEAMS = [
    "Arsenal", "Liverpool", "Manchester City", "Manchester United",
    "Chelsea", "Tottenham", "Newcastle", "Brighton", "Aston Villa",
    "West Ham", "Crystal Palace", "Fulham", "Brentford", "Everton",
    "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich"
]

async def test_premier_league_mapping(page, cat_id, tour_id):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"\nTesting Premier League: category={cat_id}, tournament={tour_id}")
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
            for i, row in enumerate(rows[:5]):
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                if home_el and away_el:
                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    if home and away:
                        teams.append(f"{home} v {away}")

            if teams:
                print(f"Sample teams: {teams[:3]}")

                # Check for Premier League teams
                all_teams_text = " ".join(teams)
                found_pl_teams = []
                for team in PREMIER_LEAGUE_TEAMS:
                    if team.lower() in all_teams_text.lower():
                        found_pl_teams.append(team)

                print(f"Premier League teams found: {found_pl_teams}")
                score = len(found_pl_teams)
                print(f"Score: {score}/{len(PREMIER_LEAGUE_TEAMS)} (threshold: 2)")

                if score >= 2:
                    print(f"  *** LIKELY CORRECT PREMIER LEAGUE MAPPING: cat={cat_id}, tour={tour_id} ***")
                    return True, cat_id, tour_id, teams[:3]
                else:
                    print(f"  x Insufficient Premier League teams found")
                    return False, cat_id, tour_id, teams[:3] if teams else []
            else:
                print("  No team names extracted")
                return False, cat_id, tour_id, []
        else:
            print("  No fixture rows found")
            return False, cat_id, tour_id, []

    except Exception as e:
        print(f"  Error: {str(e)[:50]}")
        return False, cat_id, tour_id, []

async def main():
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")

    print(f"Launch args: {launch_args}")
    print("Searching for Premier League category/tournament IDs...")
    print("=" * 60)

    # Hypothesis: Category ID might be in the 30-40 range for major European leagues
    # Based on current mappings: 30=Italy, 31=Spain, 32=?, 34=?, 393=Champions League

    category_range = list(range(30, 45))  # Test categories 30-44
    tournament_range = list(range(1, 30))  # Test tournaments 1-29

    found_mappings = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"),
                viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()

            # First test the current mapping to confirm it's wrong
            print("\nTesting CURRENT mapping (32, 8) to confirm it's incorrect:")
            is_correct, cat, tour, teams = await test_premier_league_mapping(page, 32, 8)
            if is_correct:
                print("  UNEXPECTED: Current mapping appears to be correct!")
                found_mappings.append((32, 8, teams))
            else:
                print("  CONFIRMED: Current mapping is incorrect (returns non-PL teams)")

            # Systematic search
            print("\nSystematically testing category/tournament combinations:")
            print("-" * 60)

            tested = 0
            for cat_id in category_range:
                for tour_id in tournament_range:
                    # Skip if we've already tested this combination in a previous loop
                    # (we're doing a simple nested loop, so no need for complex skipping)

                    is_correct, cat, tour, teams = await test_premier_league_mapping(page, cat_id, tour_id)
                    tested += 1

                    if is_correct:
                        found_mappings.append((cat_id, tour_id, teams))
                        # Once we find a good mapping, we can be reasonably confident
                        # but let's continue searching for a bit to see if there are others

                    # Progress indicator
                    if tested % 20 == 0:
                        print(f"  Tested {tested} combinations so far...")

            await browser.close()

    except Exception as e:
        print(f"Overall error: {e}")

    print("\n" + "=" * 60)
    print("SEARCH RESULTS")
    print("=" * 60)

    if found_mappings:
        print(f"Found {len(found_mappings)} potential Premier League mappings:")
        for cat_id, tour_id, teams in found_mappings:
            print(f"  Category {cat_id}, Tournament {tour_id}: {teams}")

        # Recommend the first one found
        best_cat, best_tour, best_teams = found_mappings[0]
        print(f"\nRECOMMENDED MAPPING FOR PREMIER LEAGUE: ({best_cat}, {best_tour})")
        print(f"  Sample teams: {best_teams}")
    else:
        print("No clear Premier League mappings found in the tested range.")
        print("Suggestions:")
        print("  1. Expand the search range (categories 1-50, tournaments 1-50)")
        print("  2. Check if there are regional variations (maybe different for Nigeria)")
        print("  3. Verify network connectivity and resolver rules are working correctly")

if __name__ == "__main__":
    asyncio.run(main())