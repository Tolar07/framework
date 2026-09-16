from __future__ import annotations
import asyncio
import json
import socket
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    print("ERROR: playwright not installed")
    sys.exit(1)

from booking.league_map import SPORTYBET_LEAGUES  # noqa: E402  (after sys.path setup)

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

def _competition_key(olp_name: str) -> tuple[str, str] | None:
    """Identify the real competition behind an OLP league name.

    SPORTYBET_LEAGUES carries several spelling aliases for one competition
    ("La Liga"/"LaLiga", "Primeira Liga"/"Liga Portugal"). Normalising the
    country + league name lets alias pairs be told apart from two genuinely
    different competitions that have been pointed at the same URL.
    """
    mapping = SPORTYBET_LEAGUES.get(olp_name)
    if mapping is None:
        return None
    return (
        mapping.country.strip().lower(),
        mapping.league.replace(" ", "").strip().lower(),
    )


def _resolve_direct_targets() -> dict[str, tuple[int, int]]:
    """Return the direct-URL map with genuinely-colliding entries disabled.

    Two DIFFERENT competitions sharing a category/tournament pair means one of
    them silently navigates to — and caches — the other's fixtures. As
    shipped, "Liga Portugal" (Portugal) and "Premier League" (England) both
    pointed at sr:category:32/sr:tournament:8.

    Spelling aliases for the SAME competition sharing a target are correct and
    are left alone ("La Liga"/"LaLiga" -> sr:category:31/sr:tournament:23).

    HR35 says never guess, so rather than pick a winner this drops every
    genuinely-colliding entry to (0, 0). Those leagues then go through sidebar
    navigation, which verifies the landed page before caching. Both the
    collision and any same-competition target disagreement are reported so
    they can be resolved against the live sidebar.
    """
    resolved = dict(SPORTYBET_CATEGORY_TOURNAMENT)

    # 1. One target claimed by two different competitions -> contamination.
    by_target: dict[tuple[int, int], list[str]] = {}
    for name, target in SPORTYBET_CATEGORY_TOURNAMENT.items():
        if all(target):
            by_target.setdefault(target, []).append(name)

    for target, names in by_target.items():
        if len(names) < 2:
            continue
        keys = {_competition_key(n) for n in names}
        if len(keys) < 2 and None not in keys:
            continue  # all aliases of one competition — correct as-is
        safe_print(
            f"  [COLLISION] {', '.join(sorted(names))} are different competitions "
            f"but all map to sr:category:{target[0]}/sr:tournament:{target[1]} — "
            f"direct URL disabled for these; falling back to verified sidebar nav. "
            f"Resolve against the live SportyBet sidebar (HR35)."
        )
        for n in names:
            resolved[n] = (0, 0)

    # 2. One competition claimed by two targets -> at least one is wrong.
    by_competition: dict[tuple[str, str], dict[str, tuple[int, int]]] = {}
    for name, target in SPORTYBET_CATEGORY_TOURNAMENT.items():
        if not all(target):
            continue
        key = _competition_key(name)
        if key is None:
            continue
        by_competition.setdefault(key, {})[name] = target

    for key, named_targets in by_competition.items():
        distinct = set(named_targets.values())
        if len(distinct) < 2:
            continue
        detail = ", ".join(
            f"{n} -> sr:category:{t[0]}/sr:tournament:{t[1]}"
            for n, t in sorted(named_targets.items())
        )
        safe_print(
            f"  [CONFLICT] {key[0]}/{key[1]} is one competition but has "
            f"disagreeing direct URLs ({detail}) — direct URL disabled for these; "
            f"falling back to verified sidebar nav. Resolve against the live "
            f"SportyBet sidebar (HR35)."
        )
        for n in named_targets:
            resolved[n] = (0, 0)

    return resolved


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
    """Build host-resolver-rules for Playwright to bypass DNS for non-Cloudflare IPs.

    Only creates resolver rules for IPs that are NOT the known Cloudflare IPs.
    If DNS lookup fails or only returns Cloudflare IPs, no resolver rules are created
    (empty string), letting Playwright use normal DNS resolution.
    """
    rules: list[str] = []
    seen: set[str] = set()
    cloudflare_ips = {"104.21.10.148", "172.67.163.154"}
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
            # DNS lookup failed - don't create resolver rules for this host
            # Let Playwright use normal DNS resolution
            pass
        # Filter out known Cloudflare IPs - we don't want resolver rules for these
        # as they won't help us bypass anything (they're just the CDN)
        non_cloudflare_ips = [ip for ip in ips if ip not in cloudflare_ips]
        for ip in non_cloudflare_ips:
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


async def _verify_league_page(
    page: Page,
    expected_league: str,
    expected_cat_tour: tuple[int, int] | None = None,
) -> bool:
    """Confirm the loaded page really is the expected league's page.

    HR35 — never guess. Returns True only on positive evidence from the URL's
    own category/tournament ids or from a header/breadcrumb element.

    It deliberately does NOT fall back to searching the whole page body, and
    does not treat `.top-link` as evidence. SportyBet renders a sidebar and a
    popular-list that name *every* competition, so the body text (and the
    top-link set) of ANY league page contains EVERY league name. The old
    whole-body fallback therefore returned True unconditionally, which is how
    Premier League fixtures ended up written into Bundesliga.json with
    league="Bundesliga".
    """
    # Strongest signal: we navigated by direct URL and the ids survived any
    # redirect, so the page is the one we asked for.
    if expected_cat_tour and all(expected_cat_tour):
        cat, tour = expected_cat_tour
        if f"sr:category:{cat}" in page.url and f"sr:tournament:{tour}" in page.url:
            return True

    strong_sources: list[str] = []
    for sel in (
        ".tournament-name",
        ".breadcrumb:visible",
        ".tournament-header:visible",
        "[class*='breadcrumb']:visible",
        ".m-nav-bar:visible",
    ):
        try:
            for el in await page.locator(sel).all():
                t = (await el.inner_text()).strip()
                if t:
                    strong_sources.append(t)
        except Exception:
            continue

    if not strong_sources:
        safe_print(
            f"  [VERIFY] {expected_league}: no tournament header or breadcrumb on page "
            f"— cannot confirm league, refusing to cache"
        )
        return False

    expected_lower = expected_league.lower()
    if any(expected_lower in src.lower() for src in strong_sources):
        return True

    safe_print(
        f"  [VERIFY] {expected_league}: page headers say {strong_sources[:3]} "
        f"— wrong league, refusing to cache"
    )
    return False


async def _extract_row_odds(row) -> Dict[str, Any]:
    """Read the 1X2 prices from a match row's first market cell.

    SportyBet renders each row's first `.market` cell as three
    `.m-outcome-odds` values in Home / Draw / Away order.

    Returns {} when the cell is missing or any price is unparseable. An empty
    raw_market is the honest "NO DATA — PENDING" signal the pipeline already
    understands (HR35); a fabricated or zero price would look like a real
    quote and could be staked against.
    """
    try:
        market_cell = await row.query_selector(".market")
        if not market_cell:
            return {}
        odds_els = await market_cell.query_selector_all(".m-outcome-odds")
        if len(odds_els) < 3:
            return {}
        prices: List[float] = []
        for el in odds_els[:3]:
            raw = (await el.inner_text()).strip()
            try:
                prices.append(float(raw))
            except ValueError:
                return {}
        # Decimal odds are strictly > 1.0; anything at or below is a
        # placeholder/suspended marker, not a price.
        if not all(p > 1.0 for p in prices):
            return {}
        home, draw, away = prices
        return {"1x2": {"home": home, "draw": draw, "away": away}}
    except Exception:
        return {}


async def _extract_fixtures(page: Page, league: str) -> List[CachedFixture]:
    fixtures: List[CachedFixture] = []
    try:
        # ONE ordered pass over date headers AND match rows.
        #
        # Previously the rows were indexed from one query and the headers from
        # a second, then zipped by position. Any element matching both
        # selectors (or any ordering difference between the two queries)
        # shifted every subsequent date onto the wrong fixture. Walking a
        # single ordered result set makes that desync impossible.
        #
        # `is_match_row` is also tested BEFORE the header test now: a row whose
        # class happens to contain "date" used to be swallowed as a header,
        # dropping the fixture and shifting the rest.
        ordered = await page.query_selector_all(
            ".m-table-date, .match-date, .date-header, [class*='date'], .m-table-row.match-row"
        )
        default_date = await _infer_date_from_page(page, page.url)

        current_date: str | None = None
        rows_with_dates: List[tuple[Any, str]] = []
        for el in ordered:
            class_attr = await el.get_attribute("class") or ""
            if "m-table-row" in class_attr and "match-row" in class_attr:
                rows_with_dates.append((el, current_date or default_date))
                continue
            text = (await el.inner_text()).strip()
            if text:
                current_date = _parse_sportybet_date(text)

        all_rows = [r for r, _ in rows_with_dates]

        for row, fixture_date in rows_with_dates:
            try:
                gid_el = await row.query_selector(".game-id")
                gid = (await gid_el.inner_text()) if gid_el else ""
                gid = gid.strip().replace("ID:", "").strip()
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                home = (await home_el.inner_text()).strip() if home_el else ""
                away = (await away_el.inner_text()).strip() if away_el else ""
                clock_el = await row.query_selector(".clock-time")
                kickoff_time = (await clock_el.inner_text()).strip() if clock_el else ""

                if home and away and kickoff_time:
                    kickoff_iso = _combine_date_time(fixture_date, kickoff_time)
                    fixtures.append(CachedFixture(
                        id=gid or str(len(fixtures)),
                        home=home,
                        away=away,
                        kickoff=kickoff_iso,  # full ISO datetime
                        league=league,
                        raw_market=await _extract_row_odds(row),
                    ))
            except Exception:
                continue

        priced = sum(1 for f in fixtures if f.raw_market)
        if fixtures and not priced:
            safe_print(
                f"  [WARN] {league}: {len(fixtures)} fixtures but 0 carry odds "
                f"— '.market .m-outcome-odds' matched nothing, check the row markup"
            )
    except Exception as e:
        safe_print(f"  x extraction error: {type(e).__name__}: {e}")
        # Log a sample of the page content for debugging if we have rows but extracted no fixtures
        if 'all_rows' in locals() and len(all_rows) > 0 and len(fixtures) == 0:
            safe_print(f"  DEBUG: Found {len(all_rows)} rows but extracted 0 fixtures")
            # Try to debug first few rows
            for i in range(min(3, len(all_rows))):
                try:
                    row = all_rows[i]
                    home_el = await row.query_selector(".teams .home-team")
                    away_el = await row.query_selector(".teams .away-team")
                    time_el = await row.query_selector(".match-time")
                    home = await home_el.inner_text() if home_el else "NULL"
                    away = await away_el.inner_text() if away_el else "NULL"
                    time_text = await time_el.inner_text() if time_el else "NULL"
                    safe_print(f"  DEBUG Row {i}: home='{home}', away='{away}', time='{time_text}'")
                except Exception as debug_e:
                    safe_print(f"  DEBUG Row {i} error: {debug_e}")
    return fixtures


def _parse_sportybet_date(text: str) -> str:
    """Parse SportyBet date header text to ISO date (YYYY-MM-DD)."""
    from datetime import date, timedelta
    text_lower = text.lower().strip()

    today = date.today()

    if "today" in text_lower:
        return today.isoformat()
    elif "tomorrow" in text_lower:
        return (today + timedelta(days=1)).isoformat()
    elif "yesterday" in text_lower:
        return (today - timedelta(days=1)).isoformat()

    # Try to parse specific date formats like "Sep 3", "03 Sep", "2026-09-03", etc.
    import re
    # Pattern for "Sep 3", "Sep 03", "3 Sep", "03 Sep"
    month_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})'
    match = re.search(month_pattern, text_lower)
    if match:
        month_str = match.group(1)[:3]
        day = int(match.group(2))
        month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                     'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
        month = month_map.get(month_str, today.month)
        try:
            return date(today.year, month, day).isoformat()
        except ValueError:
            pass

    # Pattern for "2026-09-03" or "03/09/2026"
    iso_pattern = r'(\d{4})-(\d{2})-(\d{2})'
    match = re.search(iso_pattern, text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Default to today
    return today.isoformat()


async def _infer_date_from_page(page: Page, url: str) -> str:
    """Infer the date from page URL or content.

    Async because `page.title()` is a coroutine on the async Playwright API.
    The previous sync version called it without awaiting, so `.lower()` ran
    against a coroutine object, raised AttributeError, and was swallowed by
    the surrounding except — meaning the title check could never fire and
    every undated fixture silently got today's date.
    """
    from datetime import date, timedelta

    # Check URL for date parameters
    import re
    # Patterns like ?date=2026-09-03 or &dates=20260903
    date_match = re.search(r'[?&]date=(\d{4}-\d{2}-\d{2})', url)
    if date_match:
        return date_match.group(1)

    date_match = re.search(r'[?&]dates=(\d{8})', url)
    if date_match:
        d = date_match.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    # Check if page has "today" or "tomorrow" in the title
    try:
        title = (await page.title()) or ""
        if "tomorrow" in title.lower():
            return (date.today() + timedelta(days=1)).isoformat()
        if "today" in title.lower():
            return date.today().isoformat()
    except Exception:
        pass

    # Default to today
    return date.today().isoformat()


def _combine_date_time(date_str: str, time_str: str) -> str:
    """Combine date (YYYY-MM-DD) and time (HH:MM) into ISO datetime string."""
    # Clean time string - remove any trailing garbage
    time_str = time_str.strip()
    if "\n" in time_str:
        time_str = time_str.split("\n")[0]

    # Validate time format HH:MM
    import re
    if not re.match(r'^\d{1,2}:\d{2}$', time_str):
        # Invalid time format, return date with 00:00
        return f"{date_str}T00:00:00"

    hour, minute = time_str.split(":")
    hour = int(hour)
    minute = int(minute)

    # Validate hour/minute
    if hour >= 24 or minute >= 60:
        # Malformed time, return date with 00:00
        return f"{date_str}T00:00:00"

    return f"{date_str}T{hour:02d}:{minute:02d}:00"


async def _wait_for_fixtures(page: Page, timeout: int = 10000) -> bool:
    try:
        await page.wait_for_function("""() => document.querySelectorAll('.m-table-row.match-row').length > 0""", timeout=timeout)
        return True
    except Exception:
        return False


class RedirectLoop(RuntimeError):
    pass

@contextmanager
def _guard_redirects(page, limit=3):
    """Watch for redirect loops across a navigation.

    Used as `with _guard_redirects(page): await page.goto(...)`. The listener
    is detached on every exit path, and RedirectLoop is raised afterwards only
    when the body itself succeeded — a loop report must not mask a real
    navigation error.

    This replaces a callable-cleanup version that was broken two ways:
    `page.on()` does NOT return an unsubscribe callable (Playwright's emitter
    returns the handler itself), so calling it invoked the handler with no
    arguments and raised TypeError on EVERY direct-URL attempt — silently
    downgrading the scraper to fuzzy popular-list/sidebar navigation for every
    league. And where the return value was discarded, the listener leaked,
    accumulating one handler per league scraped.
    """
    hops: dict[str, int] = {}
    loop_detected: dict[str, str | None] = {"url": None}

    def _on_response(resp):
        if 300 <= resp.status < 400:
            hops[resp.url] = hops.get(resp.url, 0) + 1
            if hops[resp.url] > limit:
                loop_detected["url"] = resp.url

    page.on("response", _on_response)
    try:
        yield
    finally:
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass

    if loop_detected["url"]:
        raise RedirectLoop(f"redirect loop: {loop_detected['url']}")

_DIRECT_TARGETS: dict[str, tuple[int, int]] | None = None


def _direct_targets() -> dict[str, tuple[int, int]]:
    """Collision-resolved direct-URL map, computed once per process."""
    global _DIRECT_TARGETS
    if _DIRECT_TARGETS is None:
        _DIRECT_TARGETS = _resolve_direct_targets()
    return _DIRECT_TARGETS


async def _scrape_league(page: Page, league: str, country: str) -> List[CachedFixture]:
    host = "www.sportybet.com"
    cat_tour = _direct_targets().get(league)
    direct_url_attempted = False

    # Start from a clean jar and set proper locale/headers
    try:
        await page.context.clear_cookies()
    except Exception:
        pass  # Continue even if clear_cookies fails

    # Set locale and headers to match target
    try:
        await page.set_extra_http_headers({"Accept-Language": "en-NG,en;q=0.9"})
    except Exception:
        pass  # Continue even if setting headers fails

    if cat_tour and cat_tour[0] != 0 and cat_tour[1] != 0:
        direct_url_attempted = True
        urls_to_try = []
        urls_to_try.append(("domain", f"https://{host}/ng/sport/football/sr:category:{cat_tour[0]}/sr:tournament:{cat_tour[1]}?source=sport_menu&sort=2"))
        try:
            resolved_ip = socket.gethostbyname(host)
            # Try the resolved IP first
            urls_to_try.append((f"ip-resolved-{resolved_ip}", f"https://{resolved_ip}/ng/sport/football/sr:category:{cat_tour[0]}/sr:tournament:{cat_tour[1]}?source=sport_menu&sort=2"))
            # Also try fallback IPs as last resort
            for ip_addr in FALLBACK_IPS:
                if ip_addr != resolved_ip:  # Avoid duplicate if resolved IP is one of fallbacks
                    urls_to_try.append((f"ip-{ip_addr}", f"https://{ip_addr}/ng/sport/football/sr:category:{cat_tour[0]}/sr:tournament:{cat_tour[1]}?source=sport_menu&sort=2"))
        except Exception:
            pass  # DNS lookup failed, we'll just try the domain URL and popular-list/sidebar approaches

        for url_type, direct_url in urls_to_try:
            try:
                safe_print(f"  -> Direct URL ({url_type}): {direct_url}")
                with _guard_redirects(page):
                    await page.goto(direct_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
                await _dismiss_overlays(page)
                # Wait for fixtures to load
                if not await _wait_for_fixtures(page):
                    safe_print(f"  [WARN] {league}: no fixture rows found after waiting")
                    rows = []
                else:
                    rows = await page.query_selector_all(".m-table-row.match-row")
                if rows:
                    if await _verify_league_page(page, league, cat_tour):
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
            except RedirectLoop:
                safe_print(f"  [INFO] Redirect loop detected on {url_type}, trying next approach")
                continue
            except Exception as e:
                safe_print(f"  [ERROR] direct nav error ({url_type}): {str(e)[:100]}")

    safe_print(f"  [RETRY] Trying popular-list navigation for {league}")
    try:
        base_url = f"https://{host}/ng/sport/football"
        safe_print(f"  -> Fallback to homepage: {base_url}")
        try:
            with _guard_redirects(page):
                await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            error_str = str(e)
            if "net::ERR_TOO_MANY_REDIRECTS" in error_str or "interrupted by another navigation" in error_str:
                safe_print(f"  [INFO] Redirect/interrupt error detected, trying base domain for {league}")
                # Try without the /ng/sport/football path
                base_url = f"https://{host}"
                safe_print(f"  -> Trying base domain: {base_url}")
                with _guard_redirects(page):
                    await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
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
            await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            error_str = str(e)
            if "net::ERR_TOO_MANY_REDIRECTS" in error_str or "interrupted by another navigation" in error_str:
                safe_print(f"  [INFO] Redirect/interrupt error detected, trying base domain for {league}")
                base_url = f"https://{host}"
                safe_print(f"  -> Trying base domain: {base_url}")
                await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
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