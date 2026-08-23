"""Inspect fixture row structure on Serie A page."""
import asyncio, json
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

        await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.locator(".category-list-item", has_text="Italy").first.click()
        await page.wait_for_timeout(2000)
        sa_container = page.locator(".category-list-item", has_text="Italy").first.locator(".tournament-list-item", has_text="Serie A")
        await sa_container.first.evaluate("el => el.click()")
        await page.wait_for_timeout(4000)

        print(f"URL: {page.url}")

        # Get first 5 match-row HTML
        rows_html = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.match-row');
                return Array.from(rows).slice(0, 5).map(r => r.innerHTML.substring(0, 1500));
            }
        """)
        print(f"\nFirst 5 .match-row HTML bodies:\n")
        for i, html in enumerate(rows_html):
            print(f"--- ROW {i} ---\n{html}\n")

        # Also get first 3 m-table-row
        table_html = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.m-table-row');
                return Array.from(rows).slice(0, 3).map(r => r.innerHTML.substring(0, 2000));
            }
        """)
        print(f"\n\nFirst 3 .m-table-row HTML bodies:\n")
        for i, html in enumerate(table_html):
            print(f"--- TABLE ROW {i} ---\n{html}\n")

        await browser.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(debug())
    sys.exit(0)