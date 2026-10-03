#!/usr/bin/env python3
"""DOM inspector — tests Champions League navigation via .top-link click."""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://www.sportybet.com.ng"

async def test_nav():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Go to football homepage
        await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"Initial URL: {page.url}")

        # Dismiss overlays minimally
        for sel in ["button:has-text('Close')"]:
            try:
                el = await page.query_selector(sel)
                if el:
                    await el.click()
                    await page.wait_for_timeout(400)
            except:
                pass

        # Find Champions League link
        cl_link = page.locator(".popular-list .top-link .top-link-item:text('Champions League')")
        if await cl_link.count() > 0:
            print("Found Champions League link, clicking...")
            btn = cl_link.first
            await btn.locator("xpath=..").click()
            await page.wait_for_timeout(5000)
            print(f"After click URL: {page.url}")

            # Check for fixtures
            rows = await page.query_selector_all("tbody.match-row, .match-row")
            print(f"Match rows found: {len(rows)}")

            # Check .category-name elements
            cats = await page.query_selector_all(".category-name")
            print(f".category-name elements: {len(cats)}")
            for c in cats[:5]:
                txt = await c.inner_text()
                print(f"  - {txt!r}")

            # Check .tour-item elements
            tour_items = await page.query_selector_all(".tour-item")
            print(f".tour-item elements: {len(tour_items)}")
            for t in tour_items[:5]:
                cls = await t.get_attribute("class")
                txt = await t.inner_text()
                print(f"  - class={cls!r} text={txt[:80]!r}")

            # Save page HTML for analysis
            html = await page.evaluate("() => document.body.innerText")
            print(f"\n=== PAGE BODY TEXT (first 2000 chars) ===\n{html[:2000]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_nav())