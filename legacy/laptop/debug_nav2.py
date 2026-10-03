"""Debug Playwright navigation to SportyBet league pages — version 2."""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://www.sportybet.com"

async def debug_navigation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=500)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="Africa/Lagos",
        )
        page = await context.new_page()

        # Intercept and log requests
        async def log_request(req):
            print(f"  -> {req.method} {req.url[:100]}")
        page.on("request", log_request)

        print("=== Navigate to football page ===")
        await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"URL: {page.url}")
        print(f"Title: {await page.title()}")

        print("\n=== Check Cloudflare challenge ===")
        body_text = await page.locator("body").inner_text()
        print(f"Body text summary (first 500 chars):\n{body_text[:500]}")
        print()

        print("=== Check for challenge elements ===")
        challenge_selectors = [
            "#challenge-stage", "#challenge-form", ".cf-challenge-running",
            "iframe[src*='challenge']", "iframe[src*='cloudflare']",
            '#cf-turnstile', '[id*="turnstile"]', '[id*="challenge"]',
        ]
        for sel in challenge_selectors:
            count = await page.locator(sel).count()
            if count:
                print(f"  FOUND challenge element: {sel} (count={count})")

        print("\n=== Clicking Italy sidebar ===")
        italy = page.locator(".category-list-item", has_text="Italy")
        count = await italy.count()
        print(f"  Italy items found: {count}")
        if count > 0:
            await italy.first.click()
            await page.wait_for_timeout(2000)

            print("\n=== After Italy click, listing all visible tournament names ===")
            # Get all visible tournament text under Italy
            texts = []
            for item in await page.locator(".category-list-item:has-text='Italy' .tournament-list-item, .category-list-item:has-text='Italy' .tournament-name").all():
                t = await item.inner_text()
                if t.strip():
                    texts.append(t.strip())
            print(f"  Found {len(texts)} tournaments under Italy:")
            for t in texts[:20]:
                print(f"    - {t}")

        print("\n=== Trying Serie A click with more specific selector ===")
        # After clicking Italy, find Serie A specifically within the Italy section
        serie_a = page.locator(".category-list-item:has(.category-list-title:text('Italy')) .tournament-list-item:text('Serie A')")
        count = await serie_a.count()
        print(f"  Serie A under Italy count: {count}")
        if count > 0:
            await serie_a.first.click()
            await page.wait_for_timeout(4000)
            print(f"  After click URL: {page.url}")
            print(f"  Body first 500 chars: {(await page.locator('body').inner_text())[:500]}")

        print("\n=== Checking page.fixture elements ===")
        fixture_selectors = [
            "[class*='fixture']",
            "[class*='match-row']",
            "[class*='event-row']",
            "[data-testid*='fixture']",
            "tr[class*='match']",
        ]
        for sel in fixture_selectors:
            c = await page.locator(sel).count()
            if c:
                print(f"  {sel}: {c} elements")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_navigation())