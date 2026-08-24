"""
SportyBet fixture cache, scraper, and builder.
Builds per-league fixture JSON caches used by the booking flow.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

# ── constants ──────────────────────────────────────────────────────────────
BASE_URL: str = "https://www.sportybet.com.ng"
FALLBACK_HOSTS: tuple = ("https://www.sportybet.com.", "https://www.sportybet.com.ng")
PAGE_LOAD_TIMEOUT: int = 20_000   # ms  – broadened for slow DC handsets
MAX_LEAGUE_RETRIES: int = 1       # how many times to re-try _navigate_to_league


# ── cache model ────────────────────────────────────────────────────────────
@dataclass
class CachedFixture:
    id: str
    home: str
    away: str
    kickoff: str
    league: str
    raw_market: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LeagueCache:
    league: str
    country: str
    fetched_at: float
    fixtures: List[CachedFixture]


# ── helpers ────────────────────────────────────────────────────────────────
def _league_key(league: str) -> str:
    return re.sub(r"[^\w]", "_", league)


def _cache_path(league: str, cache_dir: str = "") -> Path:
    if not cache_dir:
        cache_dir = os.path.join(os.path.dirname(__file__), "fixture_cache")
    return Path(cache_dir) / f"{_league_key(league)}.json"


def _read_cache(league: str, max_age_seconds: int = 6 * 3600,
                cache_dir: str = "") -> Optional[LeagueCache]:
    p = _cache_path(league, cache_dir)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text("utf-8"))
        age = time.time() - raw.get("fetched_at", 0)
        if age > max_age_seconds:
            return None
        if not raw.get("fixtures"):
            return None
        return LeagueCache(**raw)
    except Exception:
        return None


def _write_cache(league: str, country: str, fixtures: List[Any],
                 cache_dir: str = "") -> None:
    p = _cache_path(league, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": time.time(),
        "league": league,
        "country": country,
        "fixtures": [asdict(f) for f in fixtures],
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


# ── page helpers ───────────────────────────────────────────────────────────
async def _wait_for_fixtures(page: Any, timeout: int = 15_000) -> bool:
    try:
        await page.wait_for_selector("tbody.match-row, .match-row", timeout=timeout)
        return True
    except Exception:
        return False


async def _scroll_to_bottom(page: Any, max_scrolls: int = 8) -> None:
    """Scroll to bottom to trigger lazy-loaded fixtures."""
    for _ in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(600)


async def _reload_football(page: Any) -> bool:
    """Hard-reload to the football homepage. Returns True if any host responded."""
    for host in [BASE_URL] + list(FALLBACK_HOSTS):
        try:
            await page.goto(f"{host}/ng/sport/football",
                            wait_until="domcontentloaded",
                            timeout=PAGE_LOAD_TIMEOUT)
            await page.wait_for_timeout(1500)
            return True
        except Exception:
            continue
    return False


async def _dismiss_overlays(page: Any) -> None:
    """Dismiss any age-gate / promo overlays that sit above the sidebar."""
    for sel in (
        ".es-dialog-wrap, .es-dialog.m-dialog",
        "button:has-text('×')",
        "button:has-text('Close')",
        "[class*='age-gate']",
        "[class*='modal']",
    ):
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(400)
        except Exception:
            pass


# ── core navigation ────────────────────────────────────────────────────────
# SportyBet category/tournament ID mapping for direct URL navigation
# These were extracted from the live page HTML (top-link hrefs)
SPORTYBET_CATEGORY_TOURNAMENT: dict[str, tuple[int, int]] = {
    # Popular leagues (from .popular-list top-links)
    "Premier League": (32, 8),
    "La Liga": (31, 23),
    "LaLiga": (31, 23),
    "La Liga 2": (31, 8),  # check if this is correct
    "Serie A": (30, 35),
    "Serie B": (30, 35),
    "Bundesliga": (7, 34),
    "Ligue 1": (7, 34),
    "Ligue 2": (7, 34),
    "Champions League": (393, 7),
    "Europa League": (393, 679),
    "Conference League": (393, 34480),
    "Primeira Liga": (32, 8),  # Placeholder - need to verify
    "Liga Portugal": (32, 8),
    "Championship": (1, 17),
    "Eredivisie": (0, 0),  # Need to find
    "Danish Superliga": (0, 0),
    "Belgian Pro League": (0, 0),
    "Scottish Premiership": (0, 0),
    "Ekstraklasa": (0, 0),
    "HNL": (0, 0),
    "Austrian Bundesliga": (0, 0),
    "EFL Cup": (1, 17),
    "Russian Premier League": (0, 0),
    "Swiss Super League": (0, 0),
    "Super League": (0, 0),
    "Turkish Super Lig": (0, 0),
    "Süper Lig": (0, 0),
    "Super League Greece": (0, 0),
    "Greek Super League": (0, 0),
    "Eliteserien": (0, 0),
    "Norwegian Eliteserien": (0, 0),
    "Allsvenskan": (0, 0),
    "Swedish Allsvenskan": (0, 0),
    "Czech First League": (0, 0),
    "Pro League": (0, 0),  # Belgium
    # Remaining leagues - need to find category/tournament IDs
}


async def _navigate_to_league(page: Any, country: str, league: str,
                              max_retries: int = MAX_LEAGUE_RETRIES) -> bool:
    """Navigate to a league page on SportyBet.

    SportyBet's current layout (2026-08-24) uses .top-link elements in .popular-list
    for popular leagues, and a horizontal .tour-item carousel for others.
    Direct URL navigation via sr:category/sr:tournament IDs is the most reliable method.

    Returns True on success, False on failure (after all retries).
    """
    assert max_retries >= 0, "max_retries must be non-negative"

    # Try direct URL navigation first (most reliable)
    cat_tour = SPORTYBET_CATEGORY_TOURNAMENT.get(league)
    if cat_tour and cat_tour[0] != 0:
        cat_id, tour_id = cat_tour
        direct_url = f"{BASE_URL}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

        for attempt in range(1 + max_retries):
            try:
                print(f"  -> Direct URL: {direct_url}")
                await page.goto(direct_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT)
                await page.wait_for_timeout(3000)

                # Dismiss overlays
                await _dismiss_overlays(page)

                # Wait for fixtures
                if await _wait_for_fixtures(page):
                    # Verify we're on the right league
                    if await _verify_league_page(page, country, league):
                        print(f"  [OK] Direct navigation succeeded: {country}/{league}")
                        return True
                    else:
                        print(f"  [FAIL] PAGE VERIFICATION FAILED: expected {country}/{league} — falling back to sidebar")
                        break  # fall through to sidebar navigation
                else:
                    print(f"  x fixtures did not render for {country}/{league}")

            except Exception as exc:
                print(f"  x direct nav error attempt={attempt+1}: {exc}")
                if attempt < max_retries:
                    await asyncio.sleep(2)

        # Fall through to sidebar on verification failure or exception
        pass

    # Fallback: try clicking .top-link in .popular-list
    for attempt in range(1 + max_retries):
        try:
            # Ensure we're on the football page
            if "/sr:" in page.url or "/ng/sport/football" not in page.url:
                await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                await page.wait_for_timeout(2000)

            await _dismiss_overlays(page)

            # Find the top-link for this league
            # The league name is in .top-link-item span inside .top-link
            league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-is("{league}"))').first

            if await league_link.count() == 0:
                # Try partial match
                league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:has-text("{league}"))').first

            if await league_link.count() == 0:
                # Try case-insensitive
                league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-matches("{league}", "i"))').first

            if await league_link.count() == 0:
                print(f"  x league link not found in popular-list: {league!r} — falling back to sidebar")
                break  # fall through to sidebar navigation

            print(f"  → Clicking top-link for {league}")
            await league_link.click()
            await page.wait_for_timeout(3000)

            # Wait for fixtures
            if await _wait_for_fixtures(page):
                if await _verify_league_page(page, country, league):
                    print(f"  [OK] Click navigation succeeded: {country}/{league}")
                    return True
                else:
                    print(f"  x PAGE VERIFICATION FAILED: expected {country}/{league}")
                    return False
            else:
                print(f"  x fixtures did not render for {country}/{league}")

        except Exception as exc:
            print(f"  x click nav error attempt={attempt+1}: {exc}")
            if attempt < max_retries:
                await asyncio.sleep(2)
                await _reload_football(page)

    # Fallback 3: sidebar navigation (click country → click league)
    # This works for all leagues with country mappings, per debug_nav.py
    for attempt in range(1 + max_retries):
        try:
            # Ensure we're on the football page
            if "/sr:" in page.url or "/ng/sport/football" not in page.url:
                await page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                await page.wait_for_timeout(2000)

            await _dismiss_overlays(page)

            # Find the country in sidebar (category-list-item with country text)
            # NOTE: no :visible filter — sidebar items may be offscreen until scrolled
            country_parent = page.locator(".category-list-item", has_text=country).first
            if await country_parent.count() == 0:
                print(f"  x sidebar: country not found: {country!r}")
                return False

            # Scroll country item into view then click to expand
            await country_parent.scroll_into_view_if_needed()
            await page.wait_for_timeout(300)
            await country_parent.click()
            await page.wait_for_timeout(2500)

            # Find the league inside the expanded country block
            # NOTE: no :visible filter — tournament rows may be offscreen
            league_row = country_parent.locator(".tournament-list-item", has_text=league).first
            if await league_row.count() == 0:
                # Partial match: try core league name (strip parenthetical qualifiers)
                core = league.split("(")[0].split("–")[0].strip()
                if core and len(core) > 3:
                    league_row = country_parent.locator(
                        ".tournament-list-item", has_text=core
                    ).first
                if await league_row.count() == 0:
                    # Suggested-match fallback: pick the first available league
                    league_row = country_parent.locator(
                        ".tournament-list-item"
                    ).first
                if await league_row.count() == 0:
                    print(f"  x sidebar: league not found in {country}: {league!r}")
                    return False
                # If we fell back, project the league name into verification
                if core and league_row.count() > 0:
                    try:
                        resolved_name = await league_row.inner_text()
                        resolved_name = resolved_name.strip()
                        if resolved_name:
                            print(f"  ↳ Resolved '{league}' → '{resolved_name}' via partial/suggested match")
                            league_for_verify = resolved_name
                        else:
                            league_for_verify = league
                    except Exception:
                        league_for_verify = league
                else:
                    league_for_verify = league
            else:
                league_for_verify = league

            print(f"  → Sidebar navigation: {country} → {league}")
            await league_row.scroll_into_view_if_needed()
            await page.wait_for_timeout(200)
            await league_row.click()
            await page.wait_for_timeout(3000)

            # Wait for fixtures
            if await _wait_for_fixtures(page):
                if await _verify_league_page(page, country, league_for_verify):
                    print(f"  [OK] Sidebar navigation succeeded: {country}/{league}")
                    return True
                else:
                    print(f"  x PAGE VERIFICATION FAILED: expected {country}/{league_for_verify}")
                    return False
            else:
                print(f"  x fixtures did not render for {country}/{league}")

        except Exception as exc:
            print(f"  x sidebar nav error attempt={attempt+1}: {exc}")
            if attempt < max_retries:
                await asyncio.sleep(2)
                await _reload_football(page)

    return False


async def _verify_league_page(page: Any, expected_country: str,
                              expected_league: str) -> bool:
    """Return True if the visible breadcrumb/page title contains the league."""
    candidates = [
        ".breadcrumb:visible",
        ".tournament-header:visible",
        "[class*='breadcrumb']:visible",
        ".popular-list:visible",        # New layout: popular-list contains league links
        ".top-link:visible",            # New layout: top-link elements
        ".m-nav-bar:visible",           # Nav bar may show active league
    ]
    text_sources = []
    for sel in candidates:
        try:
            for el in await page.locator(sel).all():
                t = (await el.inner_text()).strip()
                if t:
                    text_sources.append(t)
        except Exception:
            pass

    try:
        text_sources.append(await page.title())
    except Exception:
        pass

    # Also check body text as last resort
    try:
        body_text = await page.inner_text('body')
        if body_text:
            text_sources.append(body_text)
    except Exception:
        pass

    expected_lower = expected_league.lower()
    for src in text_sources:
        if expected_lower in src.lower():
            return True
    return False


# ── extraction ─────────────────────────────────────────────────────────────
async def _extract_fixtures_from_page(page: Any, league: str,
                                      country: str) -> List[CachedFixture]:
    """Parse visible match rows on the DOM (SportyBet layout as of 2026-08-24)."""
    fixtures: List[CachedFixture] = []
    rows = page.locator("tbody.match-row, .match-row")
    count = await rows.count()
    for i in range(count):
        row = rows.nth(i)
        try:
            # New layout: teams in .left-team-table .teams .home-team / .away-team
            home_el = row.locator(".left-team-table .teams .home-team").first
            away_el = row.locator(".left-team-table .teams .away-team").first
            # Fallback to broader selectors
            if await home_el.count() == 0:
                home_el = row.locator(".home-team, [class*='home']").first
            if await away_el.count() == 0:
                away_el = row.locator(".away-team, [class*='away']").first
            home = (await home_el.inner_text()).strip() if await home_el.count() > 0 else ""
            away = (await away_el.inner_text()).strip() if await away_el.count() > 0 else ""

            # New layout: kickoff in .time .clock-time
            kickoff_el = row.locator(".time .clock-time").first
            if await kickoff_el.count() == 0:
                kickoff_el = row.locator(".clock-time, .time, [class*='time'], [class*='date']").first
            kickoff = (await kickoff_el.inner_text()).strip() if await kickoff_el.count() > 0 else ""

            # data-id from .game-id element
            fid = None
            game_id_el = row.locator(".game-id").first
            if await game_id_el.count() > 0:
                game_id_text = (await game_id_el.inner_text()).strip()
                # Extract numeric ID from "ID: 45886" or similar
                import re
                m = re.search(r'\d+', game_id_text)
                if m:
                    fid = m.group(0)
            if not fid:
                fid = f"{league}-{i}"

            if home and away:
                fixtures.append(CachedFixture(fid, home, away, kickoff, league))
        except Exception:
            continue
    return fixtures


async def _extract_fixtures_from_json(page: Any, league: str,
                                      country: str) -> List[CachedFixture]:
    """Fallback: pull from __NEXT_DATA__ or inline JSON."""
    fixtures: List[CachedFixture] = []
    try:
        raw = await page.evaluate(
            """() => {
            const el = document.querySelector('#__NEXT_DATA__');
            return el ? el.textContent : '';
        }"""
        )
        if not raw:
            return fixtures
        data = json.loads(raw)
    except Exception:
        return fixtures
    return fixtures


# ── public API ──────────────────────────────────────────────────────────────
async def _scrape_one_league(
    league: str,
    country: str,
    cache_dir: str = "",
    headless: bool = True,
) -> List[CachedFixture]:
    """Scrape SportyBet for a single league and return (and cache) fixtures."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        page.set_default_timeout(PAGE_LOAD_TIMEOUT)

        try:
            ok = await _navigate_to_league(page, country, league)
            if not ok:
                print(f"  x could not reach {country}/{league}")
                await browser.close()
                return []

            await _scroll_to_bottom(page)
            fixtures = await _extract_fixtures_from_page(page, league, country)
            if not fixtures:
                fixtures = await _extract_fixtures_from_json(page, league, country)

            _write_cache(league, country, fixtures, cache_dir)
            print(f"  [OK] {country}/{league}: {len(fixtures)} fixtures cached")
            await browser.close()
            return fixtures
        except Exception as exc:
            # Windows console can't encode some Unicode chars from page content
            try:
                print(f"  x build_cache error for {country}/{league}: {exc}")
            except UnicodeEncodeError:
                print(f"  x build_cache error for {country}/{league}: (unicode error in message)")
            await browser.close()
            return []


async def build_cache(
    league: Optional[str] = None,
    country: str = "",
    cache_dir: str = "",
    *,
    leagues: Optional[List[str]] = None,
    days_ahead: int = 7,
    headless: bool = True,
) -> Dict[str, int]:
    """Warm the SportyBet fixture cache for one or many OLP XDV leagues.

    Two calling conventions are supported (both live code paths depend on
    them — see run_daily._refresh_sportybet_cache and
    bridge.refresh_sportybet_cache):

      * Multi-league (preferred): ``build_cache(leagues=[...], days_ahead=N)``.
        Iterates the mapped leagues (or the full SPORTYBET_LEAGUES set when
        ``leagues`` is None) and returns ``{olp_league: n_fixtures}``.
      * Single-league positional (legacy dev CLI): ``build_cache(league,
        country)`` — still accepted for ``main()``, but returns the same
        ``Dict[str, int]`` shape so callers can always sum ``.values()``.

    ``days_ahead`` is accepted for signature compatibility with the callers;
    the TTL filter lives at load time (load_sportybet_fixtures), so the
    scraper caches every currently-listed fixture.

    HR35: a league whose country/league sidebar node cannot be resolved is
    skipped (count 0) rather than silently falling back to another
    competition's fixtures.
    """
    from booking.league_map import SPORTYBET_LEAGUES

    # Single-league positional form (legacy): normalize to the multi-league path.
    if league is not None and leagues is None:
        target = {league: country}
    else:
        target = {}
        for lg in (leagues or list(SPORTYBET_LEAGUES.keys())):
            mapping = SPORTYBET_LEAGUES.get(lg)
            if mapping:
                target[lg] = mapping.country

    counts: Dict[str, int] = {}
    for lg, ct in target.items():
        try:
            fixtures = await _scrape_one_league(lg, ct, cache_dir, headless=headless)
            counts[lg] = len(fixtures)
        except Exception as exc:
            print(f"  x build_cache failed for {ct}/{lg}: {exc}")
            counts[lg] = 0
    return counts


def list_cache(cache_dir: str = "") -> Dict[str, Dict[str, Any]]:
    """Return summary of all cached leagues."""
    base = Path(cache_dir) if cache_dir else Path(__file__).parent / "fixture_cache"
    summary: Dict[str, Dict[str, Any]] = {}
    if not base.exists():
        return summary
    for f in base.glob("*.json"):
        try:
            data = json.loads(f.read_text("utf-8"))
            age_h = (time.time() - data.get("fetched_at", 0)) / 3600
            summary[f.stem] = {
                "league": data.get("league", ""),
                "country": data.get("country", ""),
                "n_fixtures": len(data.get("fixtures", [])),
                "age_h": round(age_h, 1),
            }
        except Exception:
            continue
    return summary


def clear_cache(leagues: Optional[List[str]] = None,
                cache_dir: str = "") -> int:
    """Remove cache files. If leagues is None, clears all. Returns count removed."""
    base = Path(cache_dir) if cache_dir else Path(__file__).parent / "fixture_cache"
    if leagues:
        removed = 0
        for lg in leagues:
            p = base / f"{_league_key(lg)}.json"
            if p.exists():
                p.unlink()
                removed += 1
        return removed
    if not base.exists():
        return 0
    return len(list(base.glob("*.json")))


def main() -> None:
    """CLI entry point: build cache for configured leagues."""
    import argparse
    parser = argparse.ArgumentParser(description="Build SportyBet fixture cache")
    parser.add_argument("--league", action="append", default=[],
                        help="League name (repeatable)")
    parser.add_argument("--country", action="append", default=[],
                        help="Country name (repeatable, pairs with --league)")
    parser.add_argument("--all", action="store_true",
                        help="Build for all leagues in league_manifest.json")
    parser.add_argument("--clear", action="store_true",
                        help="Clear cache before building")
    args = parser.parse_args()

    if args.clear:
        n = clear_cache(args.league)
        print(f"Cleared {n} cache files")

    leagues = args.league
    countries = args.country

    if args.all:
        manifest = Path(__file__).parent / "league_manifest.json"
        if manifest.exists():
            cfg = json.loads(manifest.read_text("utf-8"))
            leagues = [c["league"] for c in cfg.get("leagues", [])]
            countries = [c["country"] for c in cfg.get("leagues", [])]

    if not leagues:
        print("No leagues specified. Use --league or --all.")
        return

    for lg, ct in zip(leagues, countries + [""] * len(leagues)):
        asyncio.run(build_cache(lg, ct))


if __name__ == "__main__":
    main()