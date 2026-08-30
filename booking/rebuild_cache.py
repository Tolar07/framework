#!/usr/bin/env python3
"""Rebuild SportyBet fixture cache for all leagues needed by today's acca.

Uses the same resolver-pinned direct-URL approach that worked in poc_book_single.py.
Writes directly to the booker's authoritative cache dir (data/cache/sportybet/fixtures/).
"""

from __future__ import annotations
import asyncio
import json
import os
import socket
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)


def safe_print(msg: str) -> None:
    """Print message, handling Unicode encoding issues on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace non-encodable chars
        safe_msg = msg.encode(sys.stdout.encoding or 'cp1252', 'replace').decode(sys.stdout.encoding or 'cp1252')
        print(safe_msg)

from booking.league_map import SPORTYBET_LEAGUES

# ─── Constants ──────────────────────────────────────────────────────────────
BASE_URL = "https://www.sportybet.com.ng"
PAGE_LOAD_TIMEOUT = 45_000
BOOKER_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"

# Known Cloudflare IPs for SportyBet hosts
SPORTYBET_HOSTS = ("sportybet.com", "www.sportybet.com", "sportybet.com.ng", "www.sportybet.com.ng")
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

# Direct URL mappings (from SPORTYBET_CATEGORY_TOURNAMENT in sportybet_fixtures.py)
# Many leagues have (0, 0) meaning no direct URL - we'll fall back to sidebar nav
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
    "EFL Cup": (1, 17),
    "Ekstraklasa": (0, 0),
    "Eliteserien": (0, 0),
    "Eredivisie": (0, 0),
    "Europa League": (393, 679),
    "Greek Super League": (0, 0),
    "HNL": (0, 0),
    "La Liga": (31, 23),
    "La Liga 2": (31, 8),
    "LaLiga": (31, 23),
    "Liga Portugal": (32, 8),
    "Ligue 1": (7, 34),
    "Ligue 2": (7, 34),
    "Norwegian Eliteserien": (0, 0),
    "Premier League": (32, 8),
    "Primeira Liga": (32, 8),
    "Pro League": (0, 0),
    "Russian Premier League": (0, 0),
    "Scottish Premiership": (0, 0),
    "Serie A": (30, 35),
    "Serie B": (30, 35),
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


def _resolver_rule() -> str:
    """Match PoC: only pin sportybet.com.ng with fallback IPs."""
    host = "sportybet.com.ng"
    rules = []
    for ip in FALLBACK_IPS:
        rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules) if rules else ""


async def _dismiss_overlays(page: Page) -> None:
    """Dismiss any overlays (cookie banners, etc.)"""
    try:
        await page.evaluate("""
            () => {
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
            }
        """)
        await page.wait_for_timeout(500)
    except Exception:
        pass


async def _wait_for_fixtures(page: Page, timeout: int = 15_000) -> bool:
    """Wait for match rows to appear on the page."""
    try:
        await page.wait_for_selector(".m-table-row.match-row", timeout=timeout)
        return True
    except Exception:
        return False


async def _extract_fixtures(page: Page, league: str) -> List[CachedFixture]:
    """Extract fixtures from the current league page."""
    fixtures: List[CachedFixture] = []
    try:
        rows = await page.query_selector_all(".m-table-row.match-row")
        for row in rows:
            try:
                # Get game ID
                gid_el = await row.query_selector(".game-id")
                gid = (await gid_el.inner_text()) if gid_el else ""
                gid = gid.strip().replace("ID:", "").strip()

                # Get teams
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                home = (await home_el.inner_text()).strip() if home_el else ""
                away = (await away_el.inner_text()).strip() if away_el else ""

                # Get kickoff time
                clock_el = await row.query_selector(".clock-time")
                kickoff = (await clock_el.inner_text()).strip() if clock_el else ""

                if home and away:
                    fixtures.append(CachedFixture(
                        id=gid or str(len(fixtures)),
                        home=home,
                        away=away,
                        kickoff=kickoff,
                        league=league,
                        raw_market={}
                    ))
            except Exception:
                continue
    except Exception as e:
        safe_print(f"  x extraction error: {e}")
    return fixtures


async def _scrape_league(page: Page, league: str, country: str) -> List[CachedFixture]:
    """Scrape a single league using direct URL when available, fallback to sidebar nav."""
    host = "sportybet.com.ng"

    # Try direct URL if available in SPORTYBET_CATEGORY_TOURNAMENT
    from booking.sportybet_fixtures import SPORTYBET_CATEGORY_TOURNAMENT
    cat_tour = SPORTYBET_CATEGORY_TOURNAMENT.get(league)
    direct_url_attempted = False

    if cat_tour and cat_tour[0] != 0 and cat_tour[1] != 0:
        direct_url_attempted = True
        cat_id, tour_id = cat_tour

        # First try the domain name (with resolver rule in effect)
        direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"
        try:
            safe_print(f"  -> Direct URL (domain): {direct_url}")
            await page.goto(direct_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            await page.wait_for_timeout(5000)
            # Verify we're on the right page by checking for fixture rows
            rows = await page.query_selector_all(".m-table-row.match-row")
            if rows:
                safe_print(f"  [OK] {league}: direct URL worked, found {len(rows)} rows")
                fixtures = await _extract_fixtures(page, league)
                if fixtures:
                    safe_print(f"  [OK] {league}: extracted {len(fixtures)} fixtures")
                    return fixtures
                else:
                    safe_print(f"  [WARN] {league}: direct URL worked but no fixtures extracted")
            else:
                safe_print(f"  [WARN] {league}: direct URL loaded but no fixture rows found")
        except Exception as e:
            safe_print(f"  [ERROR] direct nav error (domain): {str(e)[:100]}")

    # Fallback: go to football homepage and click via sidebar (like PoC does)
    safe_print(f"  [RETRY] Trying sidebar navigation for {league}")
    try:
        base_url = f"https://{host}/ng/sport/football"
        safe_print(f"  -> Fallback to homepage: {base_url}")
        await page.goto(base_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(3000)
        await _dismiss_overlays(page)

        # Try to click the league link in popular-list
        league_link = page.locator(
            f'.popular-list .top-link:has(.top-link-item:has-text("{league}"))'
        ).first
        if await league_link.count():
            await league_link.click()
            await page.wait_for_timeout(4000)

            # Wait for fixtures to load
            if await _wait_for_fixtures(page):
                fixtures = await _extract_fixtures(page, league)
                if fixtures:
                    safe_print(f"  [OK] {league}: sidebar nav worked, extracted {len(fixtures)} fixtures")
                    return fixtures
                else:
                    safe_print(f"  [WARN] {league}: sidebar nav worked but no fixtures extracted")
            else:
                safe_print(f"  [WARN] {league}: sidebar nav clicked but no fixture rows found")
        else:
            safe_print(f"  [WARN] league link not found for {league} in popular-list")
    except Exception as e:
        safe_print(f"  [ERROR] click nav error: {str(e)[:100]}")

    if not direct_url_attempted:
        safe_print(f"  [WARN] {league}: no direct URL mapping and sidebar nav failed")
    else:
        safe_print(f"  [FAIL] {league}: all methods failed")
    return []


def _write_cache(league: str, country: str, fixtures: List[CachedFixture]) -> None:
    """Write cache file to booker's authoritative directory."""
    BOOKER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = league.replace(" ", "_").replace("/", "_")
    path = BOOKER_CACHE_DIR / f"{safe_name}.json"

    payload = {
        "fetched_at": time.time(),
        "league": league,
        "country": country,
        "fixtures": [asdict(f) for f in fixtures],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    safe_print(f"  → wrote {path.name} ({len(fixtures)} fixtures)")


async def main():
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")
    safe_print(f"Launch args: {launch_args}")

    # Leagues needed by today's acca (from investigation)
    target_leagues = [
        "Belgian Pro League",
        "Bundesliga",
        "Championship",
        "La Liga 2",
        "Ligue 1",
        "Ligue 2",
        "Premier League",
        "Primeira Liga",
        "Russian Premier League",
        "Scottish Premiership",
        "Serie A",
        "Serie B",
        "Swiss Super League",
        "Turkish Super Lig",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        # Use new_context with user agent like PoC
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900})
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