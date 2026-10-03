"""Debug SportyBet Nav"""
import asyncio
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
        await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.locator(".category-list-item", has_text="Italy").first.click()
        await page.wait_for_timeout(2000)
        sa = page.locator(".category-list-item", has_text="Italy").first.locator(".tournament-list-item", has_text="Serie A").first
        vis = None
        try:
            vis = await sa.is_visible()
        except Exception:
            vis = "not_ok"
        print("Serie A element visibility:", vis)
        await browser.close()

asyncio.run(main())