from __future__ import annotations
import asyncio
import json
import socket
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

from booking.league_map import SPORTYBET_LEAGUES

PAGE_LOAD_TIMEOUT = 45_000
BOOKER_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

SPORTYBET_CATEGORY_TOURNAMENT: dict[str, tuple[int, int]] = {
    "Allsvenskan": (0, 0),
    "Austrian Bundesliga": (0, 0),
    "Belgian Pro League": (0, 0),
    "Bundesliga": (7, 34),
    "Champions League": (393, 7),
    "Championship": (1, 17),
    "Conference League": (393, 34480),
    "Czech First League": (0, 0),
    "Danish Superliga": (0, 0),
    "EFL Cup": (1, 18),
    "Ekstraklasa": (0, 0),
    "Eliteserien": (0, 0),
    "Eredivisie": (0, 0),
    "Europa League": (393, 679),
    "Greek Super League": (0, 0),
    "HNL": (0, 0),
    "La Liga": (31, 23),
    "La Liga 2": (31, 9),
    "LaLiga": (31, 23),
    "Liga Portugal": (32, 8),
    "Ligue 1": (7, 35),
    "Ligue 2": (7, 36),
    "Norwegian Eliteserien": (0, 0),
    "Premier League": (32, 8),
    "Primeira Liga": (32, 9),
    "Pro League": (0, 0),
    "Russian Premier League": (0, 0),
    "Scottish Premiership": (0, 0),
    "Serie A": (30, 35),
    "Serie B": (30, 36),
    "Super League": (0, 0),
    "Super League Greece": (0, 0),
    "Swedish Allsvenskan": (0, 0),
    "Swiss Super League": (0, 0),
    "Süper Lig": (0, 0),
    "Turkish Super Lig": (0, 0),
}

@dataclass
class CachedFixture:
    id: str
    home: str
    away: str
    kickoff: str
    league: str
    raw_market: Dict[str, Any] = None

    def __post_init__(self):
        if self.raw_market is None:
            self.raw_market = {}


def safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        safe_msg = msg.encode(sys.stdout.encoding or 'cp1252', 'replace').decode(sys.stdout.encoding or 'cp1252')
        print(safe_msg)


def _build_resolver_rule() -> str:
    rules: list[str] = []
    seen: set[str] = set()
    hosts = ("sportybet.com", "www.sportybet.com", "sportybet.com.ng", "www.sportybet.com.ng")
    for host in hosts:
        ips: list[str] = []
        try:
            for fam, _, _, _, sockaddr in socket.getaddrinfo(host, 443):
                ip = sockaddr[0]
                if ip not in seen:
                    seen.add(ip)
                    ips.append(ip)
        except Exception:
            pass
        if not ips:
            ips = FALLBACK_IPS
        ips = [ip for ip in ips if ip not in ["104.21.10.148", "172.67.163.154"]]
        for ip in ips:
            rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules) if rules else ""


REALISTIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _build_launch_args() -> list[str]:
    args = [
        "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
        "--ignore-certificate-errors", "--ignore-ssl-errors",
        "--allow-running-insecure-content"
    ]
    resolver_rule = _build_resolver_rule()
    if resolver_rule:
        args.append(f"--host-resolver-rules={resolver_rule}")
    return args


async def _dismiss_overlays(page: Page) -> None:
    try:
        await page.evaluate("""() => {
            const selectors = [
                '[id*="cookie"]', '[class*="cookie"]', '.es-dialog', '.modal',
                '[class*="overlay"]', '[class*="popup"]', 'button:has-text("Accept")',
                'button:has-text("I Agree")', 'button:has-text("Allow")'
            ];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    if (el.style.display !== 'none' && el.offsetParent !== null) {
                        el.click().catch(() => {});
                    }
                }
            }
        }""")
        await page.wait_for_timeout(500)
    except Exception:
        pass


async def _verify_league_page(page: Page, expected_league: str) -> bool:
    strong_sources = []
    try:
        for el in await page.locator(".tournament-name").all():
            t = (await el.inner_text()).strip()
            if t: strong_sources.append(t)
    except Exception:
        pass
    for sel in [".breadcrumb:visible", ".tournament-header:visible", "[class*='breadcrumb']:visible", ".top-link:visible", ".m-nav-bar:visible"]:
        try:
            for el in await page.locator(sel).all():
                t = (await el.inner_text()).strip()
                if t: strong_sources.append(t)
        except Exception:
            pass
    expected_lower = expected_league.lower()
    for src in strong_sources:
        if expected_lower in src.lower():
            return True
    try:
        body_text = await page.inner_text('body')
        if body_text and expected_lower in body_text.lower():
            return True
    except Exception:
        pass
    return False


async def _extract_fixtures(page: Page, league: str) -> List[CachedFixture]:
    fixtures: List[CachedFixture] = []
    try:
        rows = await page.query_selector_all(".m-table-row.match-row")
        for row in rows:
            try:
                gid_el = await row.query_selector(".game-id")
                gid = (await gid_el.inner_text()) if gid_el else ""
                gid = gid.strip().replace("ID:", "").strip()
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                home = (await home_el.inner_text()).strip() if home_el else ""
                away = (await away_el.inner_text()).strip() if away_el else ""
                clock_el = await row.query_selector(".clock-time")
                kickoff = (await clock_el.inner_text()).strip() if clock_el else ""
                if home and away:
                    fixtures.append(CachedFixture(id=gid or str(len(fixtures)), home=home, away=away, kickoff=kickoff, league=league, raw_market={}))
            except Exception:
                continue
    except Exception as e:
        safe_print(f"  x extraction error: {e}")
    return fixtures


async def _wait_for_fixtures(page: Page, timeout: int = 10000) -> bool:
    try:
        await page.wait_for_function("""() => document.querySelectorAll('.m-table-row.match-row').length > 0""", timeout=timeout)
        return True
    except Exception:
        return False


async def _scrape_league(page: Page, league: str, country: str) -> List[CachedFixture]:
    host = "sportybet.com.ng"
    cat_tour = SPORTYBET_CATEGORY_TOURNAMENT.get(league)
    direct_url_attempted = False

    if cat_tour and cat_tour[0] != 0 and cat_tour[1] != 0:
        direct_url_attempted = True
        urls_to_try = []
        urls_to_try.append(("domain", f"https://{host}/ng/sport/football/sr:category:{cat_tour[0]}/sr:tournament:{cat_tour[1]}?source=sport_menu&sort=2"))
        try:
            ip = socket.gethostbyname(host)
            for ip_addr in FALLBACK_IPS:
                urls_to_try.append((f"ip-{ip_addr}", f"https://{ip_addr}/ng/sport/football/sr:category:{cat_tour[0]}/sr:tournament:{cat_tour[1]}?source=sport_menu&sort=2"))
        except Exception:
            pass

        for url_type, direct_url in urls_to_try:
            try:
                safe_print(f"  -> Direct URL ({url_type}): {direct_url}")
                await page.goto(direct_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                await page.wait_for_timeout(5000)
                await _dismiss_overlays(page)
                rows = await page.query_selector_all(".m-table-row.match-row")
                if rows:
                    if await _verify_league_page(page, league):
                        safe_print(f"  [OK] {league}: direct URL ({url_type}) worked, found {len(rows)} rows")
                        fixtures = await _extract_fixtures(page, league)
                        if fixtures:
                            safe_print(f"  [OK] {league}: extracted {len(fixtures)} fixtures")
                            return fixtures
                        safe_print(f"  [WARN] {league}: direct URL worked but no fixtures extracted")
                    else:
                        safe_print(f"  [WARN] {league}: direct URL loaded but wrong league page (got {await page.title()})")
                else:
                    safe_print(f"  [WARN] {league}: direct URL ({url_type}) loaded but no fixture rows found")
            except Exception as e:
                safe_print(f"  [ERROR] direct nav error ({url_type}): {str(e)[:100]}")

    safe_print(f"  [RETRY] Trying popular-list navigation for {league}")
    try:
        base_url = f"https://{host}/ng/sport/football"
        safe_print(f"  -> Fallback to homepage: {base_url}")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            error_str = str(e)
            if "net::ERR_TOO_MANY_REDIRECTS" in error_str or "interrupted by another navigation" in error_str:
                safe_print(f"  [INFO] Redirect/interrupt error detected, trying base domain for {league}")
                # Try without the /ng/sport/football path
                base_url = f"https://{host}"
                safe_print(f"  -> Trying base domain: {base_url}")
                await page.goto(base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            else:
                raise  # Re-raise if it's not a redirect error
        await page.wait_for_timeout(3000)
        await _dismiss_overlays(page)

        league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-is("{league}"))').first
        if await league_link.count() == 0:
            league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-matches("{league}", "i"))').first

        if await league_link.count():
            safe_print(f"  Clicking popular-list item: {league}")
            await league_link.click()
            await page.wait_for_timeout(4000)
            await _dismiss_overlays(page)
            if await _wait_for_fixtures(page):
                fixtures = await _extract_fixtures(page, league)
                if fixtures:
                    if await _verify_league_page(page, league):
                        safe_print(f"  [OK] {league}: popular-list nav worked, extracted {len(fixtures)} fixtures")
                        return fixtures
                    safe_print(f"  [WARN] {league}: popular-list nav worked but wrong league page")
                else:
                    safe_print(f"  [WARN] {league}: popular-list nav worked but no fixtures extracted")
        else:
            safe_print(f"  [INFO] {league}: not found in popular-list, trying sidebar expand")

    except Exception as e:
        safe_print(f"  [ERROR] popular-list nav error: {str(e)[:100]}")

    safe_print(f"  [RETRY] Trying sidebar expand navigation for {league}")
    try:
        base_url = f"https://{host}/ng/sport/football"
        safe_print(f"  -> Fallback to homepage: {base_url}")
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            error_str = str(e)
            if "net::ERR_TOO_MANY_REDIRECTS" in error_str or "interrupted by another navigation" in error_str:
                safe_print(f"  [INFO] Redirect/interrupt error detected, trying base domain for {league}")
                base_url = f"https://{host}"
                safe_print(f"  -> Trying base domain: {base_url}")
                await page.goto(base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            else:
                raise
        await page.wait_for_timeout(3000)
        await _dismiss_overlays(page)

        country_found = False
        sidebar_selectors = ['.sidebar', '[class*="sidebar"]', '[class*="nav"]', '[class*="menu"]', 'aside', '[role="navigation"]', '[role="menubar"]', '.m-item', '[class*="item"]']

        for selector in sidebar_selectors:
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    try:
                        text_content = await element.text_content()
                        if text_content and country in text_content:
                            safe_print(f"  Found country '{country}' in element with selector '{selector}'")
                            await element.click()
                            country_found = True
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
                if country_found:
                    break
            except Exception:
                continue

        if not country_found:
            try:
                safe_print(f"  Trying direct text search for country: {country}")
                country_locator = page.locator(f'text={country}').first
                if await country_locator.count() > 0:
                    await country_locator.click()
                    country_found = True
                    await page.wait_for_timeout(2000)
                    safe_print(f"  Clicked country via direct text: {country}")
                else:
                    safe_print(f"  Country '{country}' not found via direct text search")
            except Exception as e:
                safe_print(f"  Error in direct text search for country: {str(e)[:100]}")

        if not country_found:
            safe_print(f"  ERROR: Could not find country '{country}' in any navigation element")
            return []

        safe_print(f"  Looking for league '{league}' under expanded country '{country}'...")

        league_found = False
        for selector in sidebar_selectors:
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    try:
                        text_content = await element.text_content()
                        if text_content and league in text_content:
                            safe_print(f"  Found league '{league}' in element with selector '{selector}'")
                            await element.click()
                            league_found = True
                            await page.wait_for_timeout(4000)
                            break
                    except Exception:
                        continue
                if league_found:
                    break
            except Exception:
                continue

        if not league_found:
            try:
                safe_print(f"  Trying direct text search for league: {league}")
                league_locator = page.locator(f'text={league}').first
                if await league_locator.count() > 0:
                    await league_locator.click()
                    league_found = True
                    await page.wait_for_timeout(4000)
                    safe_print(f"  Clicked league via direct text: {league}")
                else:
                    safe_print(f"  League '{league}' not found via direct text search")
            except Exception as e:
                safe_print(f"  Error in direct text search for league: {str(e)[:100]}")

        if not league_found:
            safe_print(f"  ERROR: Could not find league '{league}' after expanding country '{country}'")
            return []

        rows = await page.query_selector_all(".m-table-row.match-row")
        safe_print(f"  Found {len(rows)} match rows after sidebar navigation")

        if rows:
            teams = []
            for i, row in enumerate(rows[:3]):
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                if home_el and away_el:
                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    if home and away:
                        teams.append(f"{home} v {away}")
            safe_print(f"  Sample teams: {teams}")

            fixtures = await _extract_fixtures(page, league)
            if fixtures:
                if await _verify_league_page(page, league):
                    safe_print(f"  [OK] {league}: sidebar expand worked, extracted {len(fixtures)} fixtures")
                    return fixtures
                safe_print(f"  [WARN] {league}: sidebar expand worked but wrong league page")
            else:
                safe_print(f"  [WARN] {league}: sidebar expand worked but no fixtures extracted")
        else:
            safe_print(f"  [WARN] {league}: sidebar expand clicked but no fixture rows found")

    except Exception as e:
        safe_print(f"  [ERROR] sidebar nav error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()

    if not direct_url_attempted:
        safe_print(f"  [WARN] {league}: no direct URL mapping and sidebar nav failed")
    else:
        safe_print(f"  [FAIL] {league}: all methods failed")
    return []


def _write_cache(league: str, country: str, fixtures: List[CachedFixture]) -> None:
    BOOKER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = league.replace(" ", "_").replace("/", "_")
    path = BOOKER_CACHE_DIR / f"{safe_name}.json"
    payload = {"fetched_at": time.time(), "league": league, "country": country, "fixtures": [asdict(f) for f in fixtures]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    safe_print(f"  → wrote {path.name} ({len(fixtures)} fixtures)")


async def main():
    launch_args = _build_launch_args()
    safe_print(f"Launch args: {launch_args}")

    target_leagues = [
        "Belgian Pro League", "Bundesliga", "Championship", "La Liga 2",
        "Ligue 1", "Ligue 2", "Premier League", "Primeira Liga",
        "Russian Premier League", "Scottish Premiership", "Serie A",
        "Serie B", "Swiss Super League", "Turkish Super Lig",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=REALISTIC_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True
        )
        page = await ctx.new_page()

        total = 0
        for lg in target_leagues:
            mapping = SPORTYBET_LEAGUES.get(lg)
            if not mapping:
                safe_print(f"  [WARN] {lg} not in SPORTYBET_LEAGUES")
                continue
            fixtures = await _scrape_league(page, lg, mapping.country)
            if fixtures:
                _write_cache(lg, mapping.country, fixtures)
                total += len(fixtures)

        await browser.close()
        safe_print(f"\n=== DONE: {total} total fixtures cached ===")


if __name__ == "__main__":
    asyncio.run(main())