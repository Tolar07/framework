#!/usr/bin/env python3
"""Test to see what's on the SportyBet Nigeria homepage."""

import asyncio
from playwright.async_api import async_playwright

async def test_homepage():
    host = "sportybet.com.ng"
    homepage_url = f"https://{host}/ng/sport/football"

    print(f"Testing SportyBet Nigeria homepage: {homepage_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)

            # Get the page title
            title = await page.title()
            print(f"Page title: {title}")

            # Look for popular leagues or sidebar links
            # Try to find links that contain sport categories
            links = await page.query_selector_all("a[href*='sr:category']")
            print(f"Found {len(links)} links with sr:category in href")

            # Show first 10 such links
            for i, link in enumerate(links[:10]):
                href = await link.get_attribute("href")
                text = await link.inner_text()
                print(f"  {i+1}. {text.strip()} -> {href}")

            await browser.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_homepage())