"""Debug Playwright — force-click Serie A."""
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

            # Click Italy with force
            italy = page.locator(".category-list-item", has_text="Italy").first
            await italy.click()
            await page.wait_for_timeout(2000)

            # Wait for tournaments to appear
            await page.wait_for_timeout(1000)

            # Find all tournament-name elements that contain "Serie A"
            results['serie_a_raw'] = await page.locator(".tournament-name").filter(has_text="Serie A").count()

            # Try force click
            try:
                await page.locator(".tournament-name", has_text="Serie A").first.click(force=True)
                results['serie_a_clicked'] = True
            except Exception as e1:
                results['serie_a_force_error'] = str(e1)
                try:
                    await page.locator("text='Serie A'").first.click(force=True)
                    results['serie_a_text_clicked'] = True
                except Exception as e2:
                    results['serie_a_text_error'] = str(e2)

            await page.wait_for_timeout(4000)
            results['url'] = page.url

            # screenshot
            await page.screenshot(path="C:/tmp/sportybet_debug.png")
            results['screenshot'] = "saved"

            # Check for fixture content
            body = await page.locator("body").inner_text()
            results['body_after'] = body[:800]

        except Exception as e:
            results['fatal'] = str(e)
        finally:
            await browser.close()

        for k, v in results.items():
            print(f"{k}: {v}")
        print("Done.")

if __name__ == "__main__":
    asyncio.run(debug())
    sys.exit(0)