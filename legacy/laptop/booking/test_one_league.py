#!/usr/bin/env python3
"""Test one SportyBet league URL."""

import asyncio
from playwright.async_api import async_playwright

FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

def _resolver_rule():
    host = "sportybet.com.ng"
    rules = []
    for ip in FALLBACK_IPS:
        rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules)

async def test_league(league, cat_id, tour_id):
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", f"--host-resolver-rules={resolver_rule}"]

    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"Testing: {league}")
    print(f"URL: {direct_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        try:
            await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

            rows = await page.query_selector_all(".m-table-row.match-row")
            print(f"Fixture rows found: {len(rows)}")

            if rows:
                teams = []
                for i, row in enumerate(rows[:8]):
                    home_el = await row.query_selector(".teams .home-team")
                    away_el = await row.query_selector(".teams .away-team")
                    if home_el and away_el:
                        home = (await home_el.inner_text()).strip()
                        away = (await away_el.inner_text()).strip()
                        if home and away:
                            teams.append(f"{home} v {away}")

                if teams:
                    print(f"Teams: {teams}")
                else:
                    print("No team names extracted")

            await browser.close()
            return teams
        except Exception as e:
            print(f"Error: {e}")
            await browser.close()
            return []

if __name__ == "__main__":
    import sys
    league = sys.argv[1] if len(sys.argv) > 1 else "Bundesliga"
    cat_id = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    tour_id = int(sys.argv[3]) if len(sys.argv) > 3 else 34
    asyncio.run(test_league(league, cat_id, tour_id))