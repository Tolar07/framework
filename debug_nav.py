"""Debug Playwright navigation to SportyBet league pages."""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://www.sportybet.com"

async def debug_navigation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print("1. Loading football homepage...")
        try:
            await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
            print(f"   URL: {page.url}")
            print(f"   Title: {await page.title()}")
        except Exception as e:
            print(f"   ERROR: {e}")

        print("\n2. Checking page content...")
        content = await page.content()
        print(f"   HTML length: {len(content)}")

        # Check for Cloudflare challenge
        if "challenge" in content.lower() or "checking your browser" in content.lower():
            print("   *** CLOUDFLARE CHALLENGE DETECTED ***")

        # Check for sidebar
        print("\n3. Looking for sidebar country items...")
        countries = await page.locator(".category-list-item").count()
        print(f"   Found {countries} category-list-items")

        # Try to find Italy
        print("\n4. Trying to find Italy in sidebar...")
        italy = page.locator(".category-list-item", has_text="Italy").first
        if await italy.count() > 0:
            print("   Found Italy!")
            await italy.click()
            await page.wait_for_timeout(2000)

            # Look for Serie A
            print("\n5. Looking for Serie A...")
            serie_a = page.locator(".tournament-name, .tournament-list-item", has_text="Serie A").first
            if await serie_a.count() > 0:
                print("   Found Serie A!")
                await serie_a.click()
                await page.wait_for_timeout(3000)

                print(f"   After click URL: {page.url}")
                print(f"   Title: {await page.title()}")

                # Check for fixtures
                fixtures = await page.locator("[class*='fixture'], [class*='match'], [class*='row']").count()
                print(f"   Fixture elements found: {fixtures}")
            else:
                print("   Serie A NOT found in sidebar")
        else:
            print("   Italy NOT found in sidebar")

        print("\n6. Dumping page text for inspection...")
        body_text = await page.locator("body").inner_text()
        print(body_text[:3000])

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_navigation())