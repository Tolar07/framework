"""Debug Playwright — scroll Serie A into view and click."""
import asyncio, sys
from playwright.async_api import async_playwright

BASE_URL = "https://www.sportybet.com"

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=500)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        results = {}

        try:
            await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Click Italy — force scroll-into-view
            italy = page.locator(".category-list-item", has_text="Italy").first
            await italy.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await italy.click()
            await page.wait_for_timeout(2000)

            # Find Serie A, scroll into view, then click via JS
            sa = page.locator(".tournament-name", has_text="Serie A").first
            await sa.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)

            results['serie_a_visible_before'] = await sa.is_visible()
            results['serie_a_bounding'] = await sa.bounding_box()

            # Try JS click
            try:
                await sa.evaluate("el => el.click()")
                results['serie_a_method'] = "js_click"
            except Exception as e:
                results['serie_a_js_error'] = str(e)
                try:
                    await sa.click(force=True, timeout=5000)
                    results['serie_a_method'] = "force_click"
                except Exception as e2:
                    results['serie_a_force_error'] = str(e2)
                    # Try via tournament-item click
                    try:
                        item = page.locator(".tournament-list-item", has_text="Serie A").first
                        await item.scroll_into_view_if_needed()
                        await page.wait_for_timeout(200)
                        await item.evaluate("el => el.click()")
                        results['serie_a_method'] = "tournament_item_js"
                    except Exception as e3:
                        results['serie_a_item_error'] = str(e3)

            await page.wait_for_timeout(4000)
            results['final_url'] = page.url
            results['final_title'] = await page.title()

            body = await page.locator("body").inner_text()
            results['body_after'] = body[:600]

            # Check for fixture elements
            results['fixture_count'] = await page.locator("text=/\\d+ - \\d+/").count()

        except Exception as e:
            results['fatal'] = f"{type(e).__name__}: {e}"
        finally:
            await browser.close()

        for k, v in results.items():
            print(f"{k}: {v}")
        print("Done.")

if __name__ == "__main__":
    asyncio.run(debug())
    sys.exit(0)