#!/usr/bin/env python3
"""Test sidebar navigation using popular-list format (Country League)."""

import asyncio
from playwright.async_api import async_playwright

from booking.league_map import SPORTYBET_LEAGUES

async def test_popular_list_nav(league_name):
    """Test navigation using the popular-list format: '{Country} {League}'."""
    host = "sportybet.com.ng"
    homepage_url = f"https://{host}/ng/sport/football?source=sport_menu&sort=2"
    resolver_rule = "MAP sportybet.com.ng:443 104.21.10.148,MAP sportybet.com.ng:443 172.67.163.154"

    print(f"Testing popular-list navigation for: '{league_name}'")
    print(f"Homepage: {homepage_url}")

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

            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)

            # Get country and league from mapping
            bookmaker_league = SPORTYBET_LEAGUES.get(league_name)
            if not bookmaker_league:
                print(f"  ERROR: League '{league_name}' not found in SPORTYBET_LEAGUES")
                await browser.close()
                return False

            country = bookmaker_league.country
            league = bookmaker_league.league
            print(f"  Country: {country}, League: {league}")

            # Format for popular-list: "{Country} {League}"
            popular_list_text = f"{country} {league}"
            print(f"  Looking for in popular-list: '{popular_list_text}'")

            # Dismiss overlays
            await _dismiss_overlays(page)

            # Try to click the league link in popular-list using the formatted text
            league_link = page.locator(
                f'.popular-list .top-link:has(.top-link-item:has-text("{popular_list_text}"))'
            ).first
            if await league_link.count():
                print(f"  Clicking popular-list item: {popular_list_text}")
                await league_link.click()
                await page.wait_for_timeout(4000)

                # Wait for fixtures to load
                if await _wait_for_fixtures(page):
                    fixtures = await _extract_fixtures(page, league_name)
                    if fixtures:
                        print(f"  [OK] {league_name}: popular-list nav worked, extracted {len(fixtures)} fixtures")
                        # Show sample teams
                        teams = []
                        rows = await page.query_selector_all(".m-table-row.match-row")
                        for i, row in enumerate(rows[:3]):
                            home_el = await row.query_selector(".teams .home-team")
                            away_el = await row.query_selector(".teams .away-team")
                            if home_el and away_el:
                                home = (await home_el.inner_text()).strip()
                                away = (await away_el.inner_text()).strip()
                                if home and away:
                                    teams.append(f"{home} v {away}")
                        print(f"  Sample teams: {teams}")
                        await browser.close()
                        return True
                    else:
                        print(f"  [WARN] {league_name}: popular-list worked but no fixtures extracted")
                else:
                    print(f"  [WARN] {league_name}: popular-list clicked but no fixture rows found")
            else:
                print(f"  [WARN] popular-list item not found for '{popular_list_text}'")

            await browser.close()
            return False

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def _dismiss_overlays(page: object) -> None:
    """Dismiss any overlays that might block clicks."""
    selectors = [
        ".onesignal-slidedown-container",
        ".onesignal-popover-container",
        ".onesignal-popover",
        "[class*=\"onesignal\"]",
        ".modal",
        ".popup",
        "[id*=\"onesignal\"]",
    ]
    for selector in selectors:
        try:
            els = await page.query_selector_all(selector)
            for el in els:
                if await el.is_visible():
                    await el.evaluate("el => el.remove()")
                    await page.wait_for_timeout(500)
        except Exception:
            pass

async def _wait_for_fixtures(page: object, timeout: int = 15_000) -> bool:
    """Wait for match rows to appear on the page."""
    try:
        await page.wait_for_selector(".m-table-row.match-row", timeout=timeout)
        return True
    except Exception:
        return False

async def _extract_fixtures(page: object, league: str) -> list:
    """Extract fixtures from the current league page."""
    fixtures = []
    try:
        rows = await page.query_selector_all(".m-table-row.match-row")
        for row in rows:
            try:
                # Get game ID
                gid_el = await row.query_selector(".game-id")
                gid = (await gid_el.inner_text()) if gid_el else ""
                gid = gid.strip().replace("ID:", "").strip()

                # Get teams
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                home = (await home_el.inner_text()).strip() if home_el else ""
                away = (await away_el.inner_text()).strip() if away_el else ""

                # Get kickoff time
                clock_el = await row.query_selector(".clock-time")
                kickoff = (await clock_el.inner_text()).strip() if clock_el else ""

                if home and away:
                    fixtures.append({
                        'id': gid or str(len(fixtures)),
                        'home': home,
                        'away': away,
                        'kickoff': kickoff,
                        'league': league,
                        'raw_market': {}
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"  x extraction error: {e}")
    return fixtures

if __name__ == "__main__":
    # Test a few leagues that should be in the popular-list
    test_leagues = [
        "Premier League",
        "La Liga",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
    ]

    print("=== Testing popular-list navigation (Country League format) ===")
    for league in test_leagues:
        print()
        found = asyncio.run(test_popular_list_nav(league))
        print(f"Result for '{league}': {'SUCCESS' if found else 'FAILED'}")