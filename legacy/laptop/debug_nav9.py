"""Test fixed _navigate_to_league function."""
import asyncio, sys
from playwright.async_api import async_playwright

BASE_URL = "https://www.sportybet.com"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=500)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        from booking.sportybet_fixtures import _navigate_to_league
        try:
            ok = await _navigate_to_league(page, "Italy", "Serie A")
            print(f"Navigation: {ok}")
            print(f"URL: {page.url}")

            # Count rows
            rows = page.query_selector_all(".match-row")
            print(f"Match rows: {len(rows)}")

            # Get first row game-id
            for r in rows[:3]:
                gid = r.query_selector(".game-id")
                if gid:
                    print(f"  Row game-id: {gid.inner_text()}")
                home = r.query_selector(".teams .home-team")
                away = r.query_selector(".teams .away-team")
                if home and away:
                    print(f"  Fixture: {home.inner_text()} v {away.inner_text()}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        finally:
            await browser.close()

asyncio.run(main())
sys.exit(0)