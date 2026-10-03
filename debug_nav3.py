"""Debug Playwright navigation — version 3 with better error handling."""
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
            # 1. Load football page
            await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            results['url'] = page.url
            results['title'] = await page.title()
            body = await page.locator("body").inner_text()
            results['body_preview'] = body[:1000]

            # 2. Check Cloudflare
            cf = any(x in body for x in ['checking your browser', 'verify you are human', 'challenge',
                                          'cloudflare', 'Just a moment'])
            results['cloudflare'] = cf

            # 3. Count sidebar items
            results['sidebar_count'] = await page.locator(".category-list-item").count()

            # 4. Click Italy
            try:
                italy = page.locator(".category-list-item", has_text="Italy")
                c = await italy.count()
                results['italy_count'] = c
                if c > 0:
                    await italy.first.click()
                    await page.wait_for_timeout(2000)
                    results['italy_clicked'] = True
                else:
                    results['italy_clicked'] = False
            except Exception as e:
                results['italy_error'] = str(e)
                results['italy_clicked'] = False

            # 5. List tournaments under Italy
            try:
                texts = []
                items = await page.locator(".category-list-item:has-text('Italy') .tournament-list-item, .category-list-item:has-text('Italy') .tournament-name").all()
                for item in items:
                    try:
                        t = await item.inner_text()
                        if t.strip():
                            texts.append(t.strip())
                    except:
                        pass
                results['italy_tournaments'] = texts[:15]
                results['italy_tournament_count'] = len(texts)
            except Exception as e:
                results['italy_tournaments_error'] = str(e)

            # 6. Click Serie A
            try:
                results['serie_a_before'] = await page.locator("text='Serie A'").count()
                # Use force=True to avoid strict mode
                links = await page.locator("text='Serie A'").all()
                if links:
                    await links[0].click(force=True)
                    await page.wait_for_timeout(4000)
                    results['serie_a_clicked'] = True
                    results['serie_a_url'] = page.url
                else:
                    results['serie_a_clicked'] = False
            except Exception as e:
                results['serie_a_error'] = str(e)
                results['serie_a_clicked'] = False

            # 7. Check for fixture rows
            fixture_selectors = [
                "[class*='preMatch']",
                "[class*='fixture']",
                "[class*='match-row']",
                "[class*='event-row']",
            ]
            fixture_info = {}
            for sel in fixture_selectors:
                try:
                    c = await page.locator(sel).count()
                    fixture_info[sel] = c
                except:
                    fixture_info[sel] = "error"
            results['fixtures'] = fixture_info

            # 8. Final body
            try:
                results['final_body'] = (await page.locator("body").inner_text())[:500]
            except:
                results['final_body'] = "error"

        except Exception as e:
            results['fatal'] = str(e)
        finally:
            await browser.close()

        # Print results
        for k, v in results.items():
            print(f"{k}: {v}")
        print("\nDone.")

if __name__ == "__main__":
    asyncio.run(debug())
    sys.exit(0)