#!/usr/bin/env python3
"""Inspect what's actually in the popular-list on the SportyBet homepage."""

import asyncio
from playwright.async_api import async_playwright

async def inspect_popular_list():
    host = "sportybet.com.ng"
    homepage_url = f"https://{host}/ng/sport/football?source=sport_menu&sort=2"

    # Resolver rules - same as used in cache builder
    resolver_rule = "MAP sportybet.com.ng:443 104.21.10.148,MAP sportybet.com.ng:443 172.67.163.154"

    print(f"Inspecting popular-list on: {homepage_url}")

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
            await page.wait_for_timeout(5000)

            # Look for the popular-list container
            popular_list = await page.query_selector(".popular-list")
            if not popular_list:
                print("ERROR: Could not find .popular-list element")
                await browser.close()
                return

            # Look for top-link items within popular-list
            top_links = await popular_list.query_selector_all(".top-link")
            print(f"Found {len(top_links)} top-link items in popular-list")

            # Extract the text from each top-link-item
            league_names = []
            for i, link in enumerate(top_links):
                # Look for the text element within the top-link
                text_el = await link.query_selector(".top-link-item")
                if text_el:
                    text = await text_el.inner_text()
                    text = text.strip()
                    if text:
                        league_names.append(text)
                        print(f"  {i+1}. '{text}'")
                else:
                    # Fallback: get all text from the link
                    text = await link.inner_text()
                    text = text.strip()
                    if text:
                        league_names.append(text)
                        print(f"  {i+1}. '{text}' (fallback)")

            print(f"\nExtracted league names: {league_names}")

            await browser.close()
            return league_names

    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(inspect_popular_list())