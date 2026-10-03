#!/usr/bin/env python3
"""Test English league mappings on SportyBet."""

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

# Test English leagues with suspected correct mappings
ENGLISH_TESTS = [
    ("Premier League", 34, 1, ["Arsenal", "Liverpool", "Man City", "Chelsea", "Tottenham"]),
    ("Championship", 1, 17, ["Leeds", "Sheffield", "Middlesbrough", "Norwich", "Watford"]),
    ("League One", 1, 18, ["Portsmouth", "Derby", "Oxford", "Peterborough", "Bolton"]),  # guessed
    ("League Two", 1, 19, ["Stockport", "Wrexham", "Mansfield", "Doncaster", "Carlisle"]),  # guessed
]

async def test_english_league(page, league, cat_id, tour_id, expected_teams):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"\nTesting: {league}")
    print(f"URL: {direct_url}")

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
                    return True
                else:
                    print(f"  x Low score - likely incorrect mapping")
                    return False
            else:
                print("Rows found but no team names extracted")
                return False
        else:
            print("No fixture rows found")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

async def main():
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        results = {}
        for league, cat_id, tour_id, expected_teams in ENGLISH_TESTS:
            result = await test_english_league(page, league, cat_id, tour_id, expected_teams)
            results[league] = result

        await browser.close()

        print("\n\n" + "="*50)
        print("RESULTS")
        print("="*50)
        for league, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status} {league}")

if __name__ == "__main__":
    asyncio.run(main())