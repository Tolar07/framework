"""Debug Playwright — click Serie A via evaluate and dump HTML."""
import asyncio, sys, json
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

        try:
            await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Click Italy then click the FIRST visible .tournament-list-item under Italy that contains "Serie A"
            await page.locator(".category-list-item", has_text="Italy").first.click()
            await page.wait_for_timeout(2000)

            # Find the container where Italy's leagues appear (the expanded section)
            # and click the first 'Serie A' there.
            sa_container = page.locator(".category-list-item", has_text="Italy").first.locator(".tournament-list-item", has_text="Serie A")
            cnt = await sa_container.count()
            print(f"Serie A tournament-list-item under Italy: {cnt}")

            for i in range(min(cnt, 3)):
                el = sa_container.nth(i)
                vis = await el.is_visible()
                print(f"  [{i}] visible={vis}")
                try:
                    await el.evaluate("el => el.click()")
                    print(f"  [{i}] JS click succeeded")
                    break
                except Exception as e:
                    print(f"  [{i}] JS click failed: {e}")

            await page.wait_for_timeout(4000)
            print(f"URL: {page.url}")

            # Inspect page — what are the common fixture row classes?
            html_snippet = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('[class*="match"], [class*=\"fixture\"], [class*=\"event\"], [class*=\"game\"]');
                    const classes = new Set();
                    rows.forEach(r => r.classList.forEach(c => classes.add(c)));
                    return Array.from(classes).slice(0, 30);
                }
            """)
            print(f"Common match/fixture/event/game classes: {json.dumps(html_snippet)}")

            # Count rows per class prefix
            counts = await page.evaluate("""
                () => {
                    const counts = {};
                    document.querySelectorAll('*').forEach(el => {
                        el.classList.forEach(c => {
                            const lc = c.toLowerCase();
                            if (lc.includes('match') || lc.includes('fixture') || lc.includes('event') || lc.includes('game') || lc.includes('row')) counts[c] = (counts[c]||0)+1;
                        });
                    });
                    return counts;
                }
            """)
            print(f"Element counts: {json.dumps(counts)}")

            # Dump body text
            body = await page.locator("body").inner_text()
            print(f"Body (first 800 chars):\n{body[:800]}")

        except Exception as e:
            print(f"FATAL: {type(e).__name__}: {e}")
        finally:
            await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(debug())
    sys.exit(0)