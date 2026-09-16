from __future__ import annotations
import asyncio
import json
import re
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

from booking.league_map import SPORTYBET_LEAGUES
from resilient_pipeline_stage import rebuild_sportybet_cache_non_blocking

PAGE_LOAD_TIMEOUT = 45_000
BOOKER_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

# Pause between competitions so a multi-league pass is not refused part-way.
INTER_LEAGUE_DELAY_S = 4.0

# (sr:category, sr:tournament) per league, used to build the direct SportyBet URL.
#
# REBUILT 2026-09-16 from SportyBet's own factsCenter/popularAndSportList API
# (91 categories with live tournament ids and names), NOT from recall. The
# previous table was systematically wrong -- entries carried a neighbouring
# league's ids, so every scrape silently returned the wrong competition while
# reporting success:
#
#   "Premier League": (32, 8)  -> (32, 8) is Spain/LaLiga, so Premier_League.json
#                                 filled with "Betis v Getafe"
#   "Serie A":        (30, 35) -> (30, 35) is Germany/Bundesliga, so Serie_A.json
#                                 filled with "Bayern Munich v Union Berlin"
#   "Bundesliga":     (7, 34)  -> (7, 34) is France/Ligue 1  -> "Monaco v Lens"
#   "Championship":   (1, 17)  -> (1, 17) is England/Premier League
#   "Premier League" and "Liga Portugal" held the IDENTICAL pair (32, 8)
#
# _verify_league_page did not catch any of it. A booking code built on that
# cache would attach to a real fixture in the WRONG competition, which is worse
# than no code at all.
#
# Entries left as (0, 0) are leagues SportyBet did not list at capture time;
# they are deliberately not guessed -- a wrong id produces confident wrong data,
# a zero produces an honest miss.
SPORTYBET_CATEGORY_TOURNAMENT: dict[str, tuple[int, int]] = {
    # England (cat 1)
    "Premier League": (1, 17),
    "Championship": (1, 18),
    "EFL Cup": (1, 21),
    "FA Cup": (1, 19),
    # Spain (cat 32)
    "La Liga": (32, 8),
    "LaLiga": (32, 8),
    "La Liga 2": (32, 54),          # LALIGA HYPERMOTION
    "Copa del Rey": (32, 329),
    # Italy (cat 31)
    "Serie A": (31, 23),
    "Serie B": (31, 53),
    "Coppa Italia": (31, 328),
    # Germany (cat 30)
    "Bundesliga": (30, 35),
    "2. Bundesliga": (30, 44),
    "DFB-Pokal": (30, 217),
    # France (cat 7)
    "Ligue 1": (7, 34),
    "Ligue 2": (7, 182),
    "Coupe de France": (7, 335),
    # Netherlands (cat 35)
    "Eredivisie": (35, 37),
    "KNVB Beker": (35, 330),
    # Portugal (cat 44)
    "Primeira Liga": (44, 238),
    "Liga Portugal": (44, 238),
    # Others
    "Scottish Premiership": (22, 36),
    "Belgian Pro League": (33, 38),
    "Pro League": (33, 38),
    "Russian Premier League": (21, 203),
    "Swiss Super League": (25, 215),
    "Super League": (25, 215),
    "Turkish Super Lig": (46, 52),
    "Süper Lig": (46, 52),
    # International clubs (cat 393) — these were already correct
    "Champions League": (393, 7),
    "Europa League": (393, 679),
    "Conference League": (393, 34480),
    # Not listed by SportyBet at capture time — left unresolved on purpose.
    "Taça de Portugal": (0, 0),
    "UEFA Super Cup": (0, 0),
    "Allsvenskan": (0, 0),
    "Swedish Allsvenskan": (0, 0),
    "Austrian Bundesliga": (0, 0),
    "Czech First League": (0, 0),
    "Danish Superliga": (0, 0),
    "Ekstraklasa": (0, 0),
    "Eliteserien": (0, 0),
    "Norwegian Eliteserien": (0, 0),
    "Greek Super League": (0, 0),
    "Super League Greece": (0, 0),
    "HNL": (0, 0),
}

@dataclass
class CachedFixture:
    id: str
    home: str
    away: str
    kickoff: str
    league: str
    # 1X2 prices read off the fixture row. These are the field names
    # booking.bridge builds PipelineFixture from (`fx_data.get("home_odds")`),
    # so they must be top-level -- the writer only ever emitted `raw_market`,
    # which nothing reads, and the odds were never captured at all. Every
    # cached fixture carried raw_market: {} and therefore no price, so no leg
    # could ever be priced from SportyBet. None means not readable (HR35),
    # never a guessed number.
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
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
        # First, get all date headers and their associated rows
        # SportyBet pages typically have date headers like "Today", "Tomorrow", or specific dates
        # We'll find all elements and build a map of row -> date

        # Get the page content to understand structure
        all_rows = await page.query_selector_all(".m-table-row.match-row")

        # Try to find date headers - they might be in elements like .date-header, .match-date, etc.
        date_headers = await page.query_selector_all(".m-table-date, .match-date, .date-header, [class*='date']")
        date_map = {}  # Maps row index to date string

        # If we have date headers, try to associate them with rows
        # Strategy: date headers appear before the rows they apply to
        if date_headers:
            # Get all relevant elements in order
            all_elements = await page.query_selector_all(".m-table-date, .match-date, .date-header, [class*='date'], .m-table-row.match-row")

            current_date = None
            row_index = 0
            for el in all_elements:
                class_attr = await el.get_attribute("class") or ""
                is_date_header = any(cls in class_attr for cls in ["date", "Date"])
                is_match_row = "m-table-row" in class_attr and "match-row" in class_attr

                if is_date_header:
                    text = (await el.inner_text()).strip()
                    # Skip the site clock. The [class*='date'] selector also
                    # matches SportyBet's "m-date" element, whose text is the
                    # CURRENT time ("16/09/2026 23:56") rather than a fixture
                    # date -- so it was being read as a date header and applied
                    # to every row that followed it.
                    is_clock = bool(re.search(r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}', text))
                    if text and not is_clock:
                        parsed = _parse_sportybet_date(text)
                        # Empty means unparseable; leave current_date alone so
                        # those rows fall through to kickoff-time inference
                        # instead of inheriting a fabricated date.
                        if parsed:
                            current_date = parsed
                elif is_match_row:
                    if current_date:
                        date_map[row_index] = current_date
                    row_index += 1

        # If no date headers found, try to infer from page URL or default to today
        if not date_map:
            # Try to get date from URL or page content
            url = page.url
            current_date = _infer_date_from_page(page, url)
            for i in range(len(all_rows)):
                date_map[i] = current_date

        # Now extract fixtures with dates
        for i, row in enumerate(all_rows):
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

                # 1X2 prices. The row renders them as .m-outcome-odds in
                # home/draw/away order, followed by the goals markets --
                # verified on the live Europa League page, where OFI Crete v
                # Hoffenheim read ['7.58', '5.38', '1.42', '1.84', '2.00'].
                # These were never read: every cached fixture had raw_market: {}
                # and no price, so nothing downstream could price a leg from
                # SportyBet even when the cache was otherwise correct.
                h_odds = d_odds = a_odds = None
                try:
                    odds_els = await row.query_selector_all(".m-outcome-odds")
                    vals = []
                    for oe in odds_els[:3]:
                        raw = (await oe.inner_text()).strip()
                        try:
                            v = float(raw)
                        except (TypeError, ValueError):
                            v = None
                        # A decimal price is > 1.0 by definition; anything else
                        # is a handicap line or placeholder, not a price.
                        vals.append(v if (v is not None and v > 1.0) else None)
                    while len(vals) < 3:
                        vals.append(None)
                    h_odds, d_odds, a_odds = vals[0], vals[1], vals[2]
                except Exception:
                    # Unreadable odds leave the fixture priceless rather than
                    # dropping it -- identity is still useful for booking.
                    pass

                if home and away and kickoff_time:
                    # Combine date with time to create ISO datetime
                    fixture_date = date_map.get(i)
                    if fixture_date:
                        kickoff_iso = _combine_date_time(fixture_date, kickoff_time)
                    else:
                        # No date header parsed for this row. This used to stamp
                        # date.today() onto the fixture, which is a fabricated
                        # date, not a missing one -- on 2026-09-16 at 23:40 it
                        # dated nine Europa League ties "2026-09-16T17:45",
                        # i.e. six hours in the past, while three independent
                        # sources placed them on the 17th. Anything filtering
                        # the cache by date then found nothing for the real
                        # match day.
                        #
                        # SportyBet lists UPCOMING fixtures only, so a bare
                        # clock time is the next FUTURE occurrence of that time:
                        # today if it has not passed, otherwise tomorrow. That
                        # is an inference from the source's own semantics rather
                        # than an assumption that everything is today.
                        kickoff_iso = _next_occurrence_of(kickoff_time)

                    fixtures.append(CachedFixture(
                        id=gid or str(len(fixtures)),
                        home=home,
                        away=away,
                        kickoff=kickoff_iso,  # Now stores full ISO datetime
                        league=league,
                        home_odds=h_odds,
                        draw_odds=d_odds,
                        away_odds=a_odds,
                        raw_market={}
                    ))
            except Exception:
                continue
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

    # Pattern for "2026-09-03"
    iso_pattern = r'(\d{4})-(\d{2})-(\d{2})'
    match = re.search(iso_pattern, text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # SportyBet's actual header format, captured from the live page on
    # 2026-09-16: "17/09 Thursday" -- day/month, no year. None of the patterns
    # above match it, so every header fell through to the "default to today"
    # below and an entire matchday was dated a day early. Verified against
    # ESPN: those ties are on the 17th.
    #
    # Also handles the full "17/09/2026" form. The year, when absent, is chosen
    # as the one that puts the date nearest to now, so a January fixture read
    # in December resolves forward rather than eleven months back.
    dm = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', text)
    if dm:
        day, month = int(dm.group(1)), int(dm.group(2))
        year = int(dm.group(3)) if dm.group(3) else today.year
        for candidate_year in ((year,) if dm.group(3) else (year, year + 1, year - 1)):
            try:
                d = date(candidate_year, month, day)
            except ValueError:
                continue
            if dm.group(3) or -30 <= (d - today).days <= 330:
                return d.isoformat()

    # Unparseable. Return empty rather than today's date: the caller treats a
    # missing date as "resolve from the kickoff time" (_next_occurrence_of),
    # which is an inference from SportyBet's upcoming-only listing. Defaulting
    # to today here silently fabricated a date and was indistinguishable from a
    # correctly-parsed one.
    return ""


def _infer_date_from_page(page: Page, url: str) -> str:
    """Infer the date from page URL or content."""
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

    # Check if page has "today" or "tomorrow" in title or body
    try:
        title = page.title()
        if "tomorrow" in title.lower():
            return (date.today() + timedelta(days=1)).isoformat()
        if "today" in title.lower():
            return date.today().isoformat()
    except Exception:
        pass

    # Default to today
    return date.today().isoformat()


def _next_occurrence_of(time_str: str) -> str:
    """Resolve a bare 'HH:MM' to the next FUTURE datetime with that clock time.

    Used when a fixture row carries a kickoff time but no date header.
    SportyBet's fixture list is upcoming-only, so a bare time necessarily
    refers to the next occurrence: today if it has not passed yet, otherwise
    tomorrow. A small grace window keeps a match that kicked off minutes ago
    on today's date rather than flipping it a day forward.

    The previous behaviour -- stamping date.today() unconditionally -- produced
    kickoffs in the past and silently mis-dated an entire matchday.
    """
    from datetime import date, datetime, timedelta
    import re as _re

    t = (time_str or "").strip().split("\n")[0]
    if not _re.match(r"^\d{1,2}:\d{2}$", t):
        return f"{date.today().isoformat()}T00:00:00"

    hh, mm = (int(x) for x in t.split(":"))
    now = datetime.now()
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    # 3h grace: a fixture that started recently is still "today", not tomorrow.
    if candidate < now - timedelta(hours=3):
        candidate += timedelta(days=1)
    return candidate.strftime("%Y-%m-%dT%H:%M:%S")


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

def _guard_redirects(page, limit=3):
    """Attach a redirect guard to the page. Returns a cleanup function.

    Does not raise exceptions in the event handler - instead tracks redirect
    loops and the caller can check the hops dict after navigation.
    """
    hops = {}
    loop_detected = {"url": None}

    def _on_response(resp):
        if 300 <= resp.status < 400:
            hops[resp.url] = hops.get(resp.url, 0) + 1
            if hops[resp.url] > limit:
                loop_detected["url"] = resp.url

    # page.on() registers a listener and returns None -- it does NOT return a
    # cleanup callable, despite the comment that used to sit here. So `cleanup`
    # was None and combined_cleanup() raised "'NoneType' object is not callable"
    # on the line right after every page.goto.
    #
    # That exception was swallowed by the broad `except Exception` in
    # _scrape_league and reported as "direct nav error", which reads like a
    # network problem. It is not: EVERY direct-URL navigation failed here before
    # a page was ever inspected, for every league, on every run. The IP-based
    # fallbacks then failed on TLS (SNI mismatch when connecting by address), so
    # the scrape returned 0 fixtures across 0 leagues while taking 5+ minutes.
    # That empty cache is why booking codes report "fixture not found in
    # SportyBet cache" and never produce a code.
    page.on("response", _on_response)

    def combined_cleanup():
        # Playwright removes listeners via remove_listener(event, handler).
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            # Detaching is best-effort: the page may already be closed, and
            # failing to unhook a listener must not mask the navigation result.
            pass
        if loop_detected["url"]:
            raise RedirectLoop(f"redirect loop: {loop_detected['url']}")

    return combined_cleanup

async def _scrape_league(page: Page, league: str, country: str) -> List[CachedFixture]:
    host = "www.sportybet.com"
    cat_tour = SPORTYBET_CATEGORY_TOURNAMENT.get(league)
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
                # Apply redirect guard
                cleanup_redirects = _guard_redirects(page)
                await page.goto(direct_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
                cleanup_redirects()
                await _dismiss_overlays(page)
                # Wait for fixtures to load
                if not await _wait_for_fixtures(page):
                    safe_print(f"  [WARN] {league}: no fixture rows found after waiting")
                    rows = []
                else:
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
            # Apply redirect guard
            _guard_redirects(page)
            await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
        except Exception as e:
            error_str = str(e)
            if "net::ERR_TOO_MANY_REDIRECTS" in error_str or "interrupted by another navigation" in error_str:
                safe_print(f"  [INFO] Redirect/interrupt error detected, trying base domain for {league}")
                base_url = f"https://{host}"
                safe_print(f"  -> Trying base domain: {base_url}")
                # Apply redirect guard
                cleanup_redirects = _guard_redirects(page)
                try:
                    await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
                    cleanup_redirects()
                except Exception as e2:
                    error_str2 = str(e2)
                    if "net::ERR_TOO_MANY_REDIRECTS" in error_str2 or "interrupted by another navigation" in error_str2:
                        safe_print(f"  [WARN] Base domain also had redirect/interrupt error for {league}, skipping")
                        return []  # Return empty fixtures for this league
                    else:
                        raise
            else:
                raise  # Re-raise if it's not a redirect error
        try:
            await page.wait_for_timeout(3000)
        except Exception as e:
            error_str = str(e)
            if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                safe_print(f"  [WARN] Page crashed during wait for {league}, skipping")
                return []  # Return empty fixtures for this league
            else:
                raise
        await _dismiss_overlays(page)

        league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-is("{league}"))').first
        if await league_link.count() == 0:
            league_link = page.locator(f'.popular-list .top-link:has(.top-link-item:text-matches("{league}", "i"))').first

        if await league_link.count():
            safe_print(f"  Clicking popular-list item: {league}")
            await league_link.click()
            try:
                await page.wait_for_timeout(4000)
            except Exception as e:
                error_str = str(e)
                if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                    safe_print(f"  [WARN] Page crashed during wait after click for {league}, skipping")
                    return []  # Return empty fixtures for this league
                else:
                    raise
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
                try:
                    await page.goto(base_url, wait_until="commit", timeout=PAGE_LOAD_TIMEOUT)
                except Exception as e2:
                    error_str2 = str(e2)
                    if "net::ERR_TOO_MANY_REDIRECTS" in error_str2 or "interrupted by another navigation" in error_str2:
                        safe_print(f"  [WARN] Base domain also had redirect/interrupt error for {league}, skipping")
                        return []  # Return empty fixtures for this league
                    else:
                        raise
            else:
                raise
        try:
            await page.wait_for_timeout(3000)
        except Exception as e:
            error_str = str(e)
            if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                safe_print(f"  [WARN] Page crashed during wait for {league} (sidebar expand), skipping")
                return []  # Return empty fixtures for this league
            else:
                raise
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
                            try:
                                await page.wait_for_timeout(2000)
                            except Exception as e:
                                error_str = str(e)
                                if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                                    safe_print(f"  [WARN] Page crashed during wait after country click for {league}, skipping")
                                    return []  # Return empty fixtures for this league
                                else:
                                    raise
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
                    try:
                        await page.wait_for_timeout(2000)
                    except Exception as e:
                        error_str = str(e)
                        if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                            safe_print(f"  [WARN] Page crashed during wait after direct country click for {league}, skipping")
                            return []  # Return empty fixtures for this league
                        else:
                            raise
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
                            try:
                                await page.wait_for_timeout(4000)
                            except Exception as e:
                                error_str = str(e)
                                if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                                    safe_print(f"  [WARN] Page crashed during wait after league click for {league}, skipping")
                                    return []  # Return empty fixtures for this league
                                else:
                                    raise
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
                    try:
                        await page.wait_for_timeout(4000)
                    except Exception as e:
                        error_str = str(e)
                        if "Page.wait_for_timeout: Page crashed" in error_str or "TargetClosedError" in error_str:
                            safe_print(f"  [WARN] Page crashed during wait after direct league click for {league}, skipping")
                            return []  # Return empty fixtures for this league
                        else:
                            raise
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


async def main(leagues: Optional[List[str]] = None) -> Dict[str, int]:
    """Rebuild the SportyBet fixture cache.

    `leagues` restricts the scrape to the competitions the caller actually
    needs. That matters for more than speed: SportyBet throttles, and scraping
    30 competitions to serve a board that references 4 is what gets the whole
    run refused. Callers should pass the board's own leagues.

    Returns {league: fixture_count}, so the caller can report what was actually
    cached rather than guessing.
    """
    launch_args = _build_launch_args()
    safe_print(f"Launch args: {launch_args}")

    # Derived, not hardcoded. This used to be a fixed list of 14 domestic
    # leagues that excluded EVERY continental competition and EVERY cup --
    # no Champions League, Europa League, Conference League, EFL Cup, FA Cup,
    # Copa del Rey, DFB-Pokal. It also listed "La Liga 2" but not "La Liga".
    #
    # So the cache could never hold odds for a cup or continental fixture, and
    # a board made of those (2026-09-17 is 11 Europa League ties and an EFL Cup
    # tie) got no prices at all -- which meant no EV, no capital-eligible leg,
    # no acca payload and therefore no booking code. The board reported
    # "no capital-eligible pick today", which is indistinguishable from a
    # genuinely quiet day.
    #
    # Scrape what production can actually deploy on: every competition with a
    # resolved SportyBet tournament id that the booker also knows how to
    # navigate. Adding a league to the registry now reaches the cache
    # automatically instead of needing this list edited too.
    bookable = {lg for lg, ids in SPORTYBET_CATEGORY_TOURNAMENT.items()
                if ids != (0, 0) and lg in SPORTYBET_LEAGUES}

    if leagues:
        # Only what the caller asked for, intersected with what is actually
        # bookable. Keeps the request count proportional to the board.
        target_leagues = sorted(set(leagues) & bookable)
        skipped = sorted(set(leagues) - bookable)
        if skipped:
            safe_print(f"  [INFO] not bookable, skipped: {', '.join(skipped[:8])}")
    else:
        target_leagues = sorted(bookable)

    safe_print(f"Cache targets: {len(target_leagues)} competitions"
               f"{' (caller-restricted)' if leagues else ' (all bookable)'}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=REALISTIC_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True
        )
        page = await ctx.new_page()

        total = 0
        per_league: Dict[str, int] = {}
        for idx, lg in enumerate(target_leagues):
            mapping = SPORTYBET_LEAGUES.get(lg)
            if not mapping:
                safe_print(f"  [WARN] {lg} not in SPORTYBET_LEAGUES")
                continue

            # Space the requests out. Scraping competitions back to back is what
            # gets the run refused part-way through -- once SportyBet starts
            # throttling, every remaining league returns nothing and the cache
            # ends up partially populated with no indication why. A short pause
            # costs seconds and keeps the whole pass usable.
            if idx:
                await asyncio.sleep(INTER_LEAGUE_DELAY_S)

            # Create a closure that captures the league and country for the scrape function
            async def scrape_league_closure():
                return await _scrape_league(page, lg, mapping.country)

            # Use non-blocking wrapper with fallback to previous cache
            cache_file = BOOKER_CACHE_DIR / f"{lg.replace(' ', '_').replace('/', '_')}.json"
            result = await rebuild_sportybet_cache_non_blocking(
                scrape_func=scrape_league_closure,
                fallback_cache_path=str(cache_file) if cache_file.exists() else None
            )

            if result.success:
                fixtures = result.data
                if fixtures:
                    _write_cache(lg, mapping.country, fixtures)
                    total += len(fixtures)
                    per_league[lg] = len(fixtures)
                    if result.error:  # Indicates fallback was used
                        safe_print(f"  [INFO] {lg}: used fallback cache ({result.error})")
                else:
                    safe_print(f"  [WARN] {lg}: no fixtures available (scraping failed and no fallback)")
            else:
                safe_print(f"  [ERROR] {lg}: failed to get fixtures: {result.error}")

        await browser.close()
        safe_print(f"\n=== DONE: {total} total fixtures cached "
                   f"across {len(per_league)} competition(s) ===")
        # Returned so callers report what was really cached. build_cache used to
        # `return {}` with a note that counts were "logged during rebuild", so
        # every run announced "0 fixtures across 0 leagues" no matter what was
        # scraped -- a false alarm that masked both real failures and real
        # successes for weeks.
        return per_league


if __name__ == "__main__":
    asyncio.run(main())