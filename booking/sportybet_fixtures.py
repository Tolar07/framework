"""
SportyBet fixtures cache builder — Playwright-based cache warmer.

This module uses Playwright (headless Chromium) to build a complete fixture
cache for SportyBet Nigeria. It navigates the JavaScript-rendered site,
extracts all fixtures for configured leagues, and writes a JSON cache that
the requests-based `sportybet_client.SportyBetClient` can serve instantly.

WHY PLAYWRIGHT
  SportyBet's fixture pages are heavily JavaScript-rendered (Next.js). The
  requests client can parse some embedded JSON, but the full fixture list
  requires browser rendering. This module runs once (scheduled or manual)
  to populate the cache; the daily run then uses the fast requests client.

USAGE
  # Build cache for all mapped leagues (run weekly or before matchdays)
  python -m booking.sportybet_fixtures build --days-ahead 7

  # Build cache for specific leagues only
  python -m booking.sportybet_fixtures build --leagues "Premier League" "La Liga"

  # List cached leagues
  python -m booking.sportybet_fixtures list

CACHE STRUCTURE
  data/cache/sportybet/fixtures/
    {league_key}.json  -> { "fetched_at": timestamp, "fixtures": [...], "league": "...", "country": "..." }

DEPLOY GATE
  Phase 3 live — capital authority is the Architect's. This module NEVER
  places bets. It only reads and caches.
"""

from __future__ import annotations

import json
import re
import time
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import date, timedelta

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
except ImportError:
    sync_playwright = None

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.league_map import SPORTYBET_LEAGUES, BookmakerLeague
from booking.team_map import resolve_team, resolve_team_to_model


# --- Configuration ---
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"
BASE_URL = "https://www.sportybet.com"

# Maximum wait for page loads (ms)
PAGE_LOAD_TIMEOUT = 30000
# Wait for network idle after navigation (ms)
NETWORK_IDLE_TIMEOUT = 5000

# Default leagues to cache (all mapped leagues)
DEFAULT_LEAGUES = list(SPORTYBET_LEAGUES.keys())


@dataclass
class CachedFixture:
    """A fixture as cached from SportyBet."""
    fixture_id: str
    home_team: str
    away_team: str
    kickoff_utc: str
    sportybet_home: str  # SportyBet's official home team name
    sportybet_away: str  # SportyBet's official away team name
    model_home: str      # Mapped to OLP XDV model key
    model_away: str      # Mapped to OLP XDV model key
    league: str
    country: str
    # 1X2 odds as displayed on the league page (first market cell of the row).
    # None means the row had no readable odds that pass (the row is still
    # cached — a missing price is a miss, never a fabricated one, HR35).
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None


@dataclass
class LeagueCache:
    """Cache file for one league."""
    fetched_at: float
    league: str
    country: str
    fixtures: List[Dict[str, Any]]


def _league_key(league: str) -> str:
    """Generate filesystem-safe key for a league."""
    return league.replace(" ", "_").replace("/", "_")


def _cache_path(league: str) -> Path:
    """Get cache file path for a league."""
    return CACHE_DIR / f"{_league_key(league)}.json"


def _read_cache(league: str, max_age_seconds: int = 6 * 3600) -> Optional[LeagueCache]:
    """Read cache if fresh."""
    path = _cache_path(league)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data.get("fetched_at", 0)
        if age > max_age_seconds:
            return None
        # An EMPTY fixture list is NOT treated as fresh: it usually means the
        # previous run used a too-narrow days-ahead window and filtered
        # everything out. Treating it as fresh would block a wider window from
        # retrying for the full TTL.
        if not data.get("fixtures"):
            return None
        return LeagueCache(**data)
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def _write_cache(league: str, country: str, fixtures: List[CachedFixture]) -> None:
    """Write cache for a league."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(league)
    data = LeagueCache(
        fetched_at=time.time(),
        league=league,
        country=country,
        fixtures=[asdict(f) for f in fixtures],
    )
    path.write_text(
        json.dumps(asdict(data), ensure_ascii=False, indent=2), encoding="utf-8")


def _wait_for_fixtures(page: Page, timeout: int = 15000) -> bool:
    """Wait for fixture elements to appear on page."""
    try:
        # SportyBet renders match rows inside a match table after navigation.
        page.wait_for_selector(".match-row, .m-table.match-table", timeout=timeout)
        return True
    except Exception:
        return False


def _scroll_to_bottom(page: Page, max_scrolls: int = 10) -> None:
    """Scroll to bottom to load all fixtures (infinite scroll)."""
    last_height = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def _extract_fixtures_from_page(page: Page, league: str, country: str) -> List[CachedFixture]:
    """Extract fixtures from the current page.

    SportyBet renders fixtures as `.m-table-row.match-row` elements inside a
    `.m-table.match-table`. Rows are grouped under `.date-row` headers
    (e.g. "21/08 Friday"); the current date carries forward to the rows that
    follow it."""
    fixtures = []

    # Track the date from the date-row headers
    current_date = ""
    rows = page.query_selector_all(".m-table-row")
    for row in rows:
        cls = row.get_attribute("class") or ""
        if "date-row" in cls:
            date_text = row.inner_text().strip()
            # "21/08 Friday" -> "2026-08-21"
            parsed = _parse_date_row(date_text)
            if parsed:
                current_date = parsed
            continue
        if "match-row" in cls:
            fixture = _parse_fixture_element(row, league, country, current_date)
            if fixture:
                fixtures.append(fixture)

    # Strategy 2: If DOM parsing yielded nothing, try JSON extraction
    if not fixtures:
        fixtures = _extract_fixtures_from_json(page, league, country)

    return fixtures


def _parse_date_row(text: str) -> str:
    """Parse a date header like '21/08 Friday' into ISO date '2026-08-21'.

    SportyBet uses DD/MM format without the year. Returns today's year, or
    next year if the month is behind the current month (late-year matches)."""
    import re
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if not m:
        return ""
    day, month = int(m.group(1)), int(m.group(2))
    today = date.today()
    year = today.year
    # If this month is already past, the fixture is next year (Dec->Jan)
    if (month, day) < (today.month, today.day):
        year += 1
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return ""


def _parse_fixture_element(elem, league: str, country: str,
                           match_date: str = "") -> Optional[CachedFixture]:
    """Parse a single fixture element (`.m-table-row.match-row`)."""
    try:
        # Fixture ID from the game-id block: "ID: 39515"
        fixture_id = ""
        game_id_elem = elem.query_selector(".game-id")
        if game_id_elem:
            game_id_text = game_id_elem.inner_text().strip()
            import re
            m = re.search(r"(\d+)", game_id_text)
            if m:
                fixture_id = m.group(1)
        if not fixture_id:
            return None

        # Team names — .home-team and .away-team are siblings inside .teams
        home_elem = elem.query_selector(".teams .home-team")
        away_elem = elem.query_selector(".teams .away-team")
        sportybet_home = home_elem.inner_text().strip() if home_elem else ""
        sportybet_away = away_elem.inner_text().strip() if away_elem else ""

        if not sportybet_home or not sportybet_away:
            return None

        # Kickoff time — "20:00" plus the date from the date-row header
        kickoff_utc = ""
        time_elem = elem.query_selector(".clock-time")
        clock = time_elem.inner_text().strip().replace(" ", "") if time_elem else ""
        if clock and match_date:
            kickoff_utc = f"{match_date}T{clock}:00Z"

        # Map to model keys — REVERSE resolution (SportyBet -> model key), never
        # the forward map: the old code called resolve_team backwards, which
        # fuzzy-matched the SportyBet name against SportyBet VALUES and stored a
        # different club (e.g. "Millwall FC" -> "AC Milan").
        model_home = resolve_team_to_model(sportybet_home)
        model_away = resolve_team_to_model(sportybet_away)

        # 1X2 odds: the row's FIRST market cell (.market) carries the three
        # match-result prices in order Home / Draw / Away. A row without
        # readable prices keeps None for that side (HR35 — never fabricated).
        home_odds, draw_odds, away_odds = None, None, None
        first_market = elem.query_selector(".market-cell .market")
        if first_market is not None:
            outcome_elems = first_market.query_selector_all(".m-outcome-odds")
            prices = []
            for oe in outcome_elems:
                raw = oe.inner_text().strip().replace(" ", "")
                try:
                    prices.append(float(raw))
                except ValueError:
                    prices.append(None)
            if len(prices) >= 3 and all(p is not None for p in prices[:3]):
                home_odds, draw_odds, away_odds = prices[0], prices[1], prices[2]

        return CachedFixture(
            fixture_id=fixture_id,
            home_team=sportybet_home,
            away_team=sportybet_away,
            kickoff_utc=kickoff_utc,
            sportybet_home=sportybet_home,
            sportybet_away=sportybet_away,
            model_home=model_home,
            model_away=model_away,
            league=league,
            country=country,
            home_odds=home_odds,
            draw_odds=draw_odds,
            away_odds=away_odds,
        )
    except Exception:
        return None


def _extract_fixtures_from_json(page: Page, league: str, country: str) -> List[CachedFixture]:
    """Extract fixtures from embedded JSON (__NEXT_DATA__)."""
    fixtures = []
    try:
        # Get __NEXT_DATA__ script content
        script = page.query_selector("script#__NEXT_DATA__, script[type='application/json']")
        if script:
            content = script.inner_text()
            data = json.loads(content)
            fixtures.extend(_parse_next_data(data, league, country))
    except Exception:
        pass
    return fixtures


def _parse_next_data(data: Dict, league: str, country: str) -> List[CachedFixture]:
    """Parse fixtures from Next.js __NEXT_DATA__."""
    fixtures = []
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        initial_state = page_props.get("initialState", {})
        matches = initial_state.get("matches", {}).get("data", {}) or initial_state.get("fixtures", {})

        for match_id, match in matches.items():
            if isinstance(match, dict):
                sportybet_home = match.get("homeTeam", {}).get("name", "")
                sportybet_away = match.get("awayTeam", {}).get("name", "")
                fixtures.append(CachedFixture(
                    fixture_id=str(match_id),
                    home_team=sportybet_home,
                    away_team=sportybet_away,
                    kickoff_utc=match.get("startTime", ""),
                    sportybet_home=sportybet_home,
                    sportybet_away=sportybet_away,
                    model_home=resolve_team_to_model(sportybet_home),
                    model_away=resolve_team_to_model(sportybet_away),
                    league=league,
                    country=country,
                ))
    except Exception:
        pass
    return fixtures


def _navigate_to_league(page: Page, country: str, league: str) -> bool:
    """Navigate to a league page on SportyBet.

    SportyBet's fixture page is a SPA: the country must be clicked in the
    sidebar first, then the league name. Direct URL navigation does NOT load
    fixtures ("Failed to load game data"). This function replicates the
    click-through that a user performs.

    CRITICAL (2026-08-15): After navigation, we VERIFY the page shows the
    expected league by checking the visible breadcrumb/heading. If verification
    fails, the cache write is ABORTED — this prevents silent cross-contamination
    (e.g. Bosnian/Israeli/Welsh "Premier League" all colliding with England's).
    """
    try:
        # Step 1: ensure we're on a clean football page. The guard is NOT just
        # "/sport/football" — a deep tournament link (e.g. .../sr:tournament:36)
        # also contains it, and after a BTTS leg we're left on that deep link in
        # an EXPANDED GG/NG state. Reusing it (clicking the sidebar again) drives
        # a corrupted DOM, so force a clean home reload whenever the URL is a
        # deep /sr: link (verified live 2026-08-09: second leg after a BTTS leg
        # failed until the hard reload was added).
        if "/sr:" in page.url or "/ng/sport/football" not in page.url:
            page.goto(f"{BASE_URL}/ng/sport/football", wait_until="domcontentloaded",
                      timeout=PAGE_LOAD_TIMEOUT)
            page.wait_for_timeout(1500)

        # Handle any modal dialogs that might block clicks
        try:
            dialog = page.query_selector(".es-dialog-wrap, .es-dialog.m-dialog")
            if dialog:
                close_btn = page.query_selector(".es-dialog .close, .es-dialog-wrap .close, button:has-text('×'), button:has-text('Close')")
                if close_btn:
                    close_btn.click()
                    page.wait_for_timeout(500)
                else:
                    # Try clicking outside the dialog or pressing Escape
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
        except Exception:
            pass

        # Step 2: click the country in the sidebar (e.g. "England").
        # The sidebar country is a DIV.category-item inside LI.category-list-item.
        country_loc = page.locator(
            ".category-item:visible, .category-list-item:visible",
            has_text=country).first
        if country_loc.count() == 0:
            country_loc = page.locator(
                f"text={country} >> visible=true").first
        if country_loc.count() == 0:
            print(f"  x Country '{country}' not found in sidebar")
            return False

        # Click with force to handle potential overlay
        try:
            country_loc.click(force=True)
        except Exception:
            # Try alternative click method
            country_loc.dispatch_event("click")
        page.wait_for_timeout(2500)

        # Step 3: click the league name — SCOPED to the just-expanded country.
        # After clicking the country, only that country's tournaments are visible.
        # Match the tournament-name INSIDE the expanded country section, NOT
        # globally — this prevents "Premier League" colliding across countries.
        league_loc = page.locator(
            ".category-list-item:visible").filter(
            has=page.locator(f"text={country}")).first.locator(
            ".tournament-name:visible, .tournament-list-item:visible",
            has_text=league).first
        if league_loc.count() == 0:
            # NO FALLBACK — global match caused catastrophic cross-contamination
            # (Welsh Premier League getting English PL fixtures, Bosnian getting England's, etc.)
            print(f"  x League '{league}' not found in sidebar for {country} (scoped search only; no global fallback per HR35)")
            return False

        try:
            league_loc.click(force=True)
        except Exception:
            league_loc.dispatch_event("click")

        # Step 4: wait for fixtures to render
        page.wait_for_timeout(3000)
        if not _wait_for_fixtures(page):
            print(f"  x Fixtures did not render for {country}/{league}")
            return False

        # Step 5: VERIFY the page actually shows the expected league.
        # Read the breadcrumb/heading that SportyBet displays on the league page.
        # If it doesn't match, ABORT — this is the anti-contamination gate.
        if not _verify_league_page(page, country, league):
            print(f"  x PAGE VERIFICATION FAILED: expected {country}/{league}")
            return False

        return True
    except Exception as e:
        print(f"  x Navigation failed for {country}/{league}: {e}")
        return False


def _verify_league_page(page: Page, expected_country: str, expected_league: str) -> bool:
    """Verify the current page is the expected league.

    SportyBet renders a breadcrumb/heading like "Spain > LaLiga" or a page
    title. We check for the expected league name in the visible page header.
    This is the anti-contamination gate (ID408): if the sidebar click landed
    on the wrong tournament, we catch it BEFORE caching wrong fixtures.

    FIX (2026-08-16): Multiple elements can match the breadcrumb selectors.
    The first one in DOM order (e.g., a "Live Betting" label) may not contain
    the league name. We must check ALL visible matching elements and return
    True if ANY contains the expected league/country.

    FIX (2026-08-17): Country-name fallback REMOVED. The old code allowed
    `expected_country.lower() in text` as a secondary signal — this caused
    catastrophic cross-contamination (e.g., Premier League fixtures cached under
    "Bosnian Premier League" because both breadcrumbs contained "England" or
    similar). Now ONLY the exact league name (case-insensitive) in the breadcrumb
    or page title passes. This is strict but necessary — HR35: absence = unavailable,
    never fabricated.
    """
    try:
        # Strategy 1: Check the breadcrumb/heading in the main content area
        # SportyBet shows "Spain / LaLiga" or similar in .breadcrumb or .tournament-header
        # Use .all() instead of .first() — multiple elements can match; any one
        # containing the league name means we're on the right page.
        breadcrumbs = page.locator(
            ".breadcrumb:visible, .tournament-header:visible, .page-header:visible, .league-title:visible").all()
        for bc in breadcrumbs:
            try:
                text = bc.inner_text().strip().lower()
                # STRICT: Only league name match passes. Country fallback REMOVED.
                if expected_league.lower() in text:
                    return True
            except Exception:
                continue

        # Strategy 2: Check the URL — SportyBet URLs contain /sr:tournament:<id>
        # Not reliable for name matching, but a last resort
        url = page.url.lower()
        # Could add tournament ID mapping later, for now skip

        # Strategy 3: Check page <title> — STRICT: league name only
        title = page.title().lower()
        if expected_league.lower() in title:
            return True

        # Safely get breadcrumb text for debug logging (handle Unicode chars that
        # can't encode to Windows console cp1252)
        try:
            if breadcrumbs:
                breadcrumb_text = breadcrumbs[0].inner_text().strip()
            else:
                breadcrumb_text = 'none'
            # Replace non-encodable chars with placeholder
            breadcrumb_text = breadcrumb_text.encode('ascii', 'replace').decode('ascii')
        except Exception:
            breadcrumb_text = 'unreadable'
        print(f"  ! Verification: breadcrumb='{breadcrumb_text}', title='{title}'")
        return False
    except Exception as e:
        # Safely print error message (handle Unicode in exception)
        try:
            err_msg = str(e).encode('ascii', 'replace').decode('ascii')
        except Exception:
            err_msg = 'unprintable error'
        print(f"  ! Verification error: {err_msg}")
        return False


def build_cache(
    leagues: Optional[List[str]] = None,
    days_ahead: int = 7,
    headless: bool = True,
    slow_mo: int = 0,
) -> Dict[str, int]:
    """Build fixture cache for specified leagues using Playwright.

    Args:
        leagues: List of OLP XDV league names to cache. Default: all mapped leagues.
        days_ahead: How many days ahead to cache (filter by kickoff date).
        headless: Run browser headless.
        slow_mo: Slow down Playwright operations by N ms (debugging).

    Returns:
        Dict mapping league name -> fixture count cached.
    """
    if sync_playwright is None:
        raise RuntimeError("playwright not installed — pip install playwright && playwright install chromium")

    leagues = leagues or DEFAULT_LEAGUES
    results = {}
    cutoff_date = date.today() + timedelta(days=days_ahead)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        for olp_league in leagues:
            mapping = SPORTYBET_LEAGUES.get(olp_league)
            if not mapping:
                print(f"! {olp_league}: not mapped for SportyBet, skipping")
                results[olp_league] = 0
                continue

            print(f"-> Building cache for {mapping.country} / {mapping.league} ({olp_league})...")

            # Check if cache is fresh
            existing = _read_cache(olp_league, max_age_seconds=6 * 3600)
            if existing:
                print(f"  - Cache fresh ({len(existing.fixtures)} fixtures), skipping")
                results[olp_league] = len(existing.fixtures)
                continue

            # Navigate to league page
            if not _navigate_to_league(page, mapping.country, mapping.league):
                print(f"  x Failed to load page")
                results[olp_league] = 0
                continue

            # Scroll to load all fixtures
            _scroll_to_bottom(page)

            # Extract fixtures
            fixtures = _extract_fixtures_from_page(page, olp_league, mapping.country)

            # Filter by date
            filtered = []
            for fx in fixtures:
                if fx.kickoff_utc:
                    try:
                        kickoff_date = date.fromisoformat(fx.kickoff_utc[:10])
                        if kickoff_date <= cutoff_date:
                            filtered.append(fx)
                    except ValueError:
                        filtered.append(fx)  # Keep if date unparseable
                else:
                    filtered.append(fx)  # Keep if no date

            # Write cache
            _write_cache(olp_league, mapping.country, filtered)
            print(f"  + Cached {len(filtered)} fixtures (of {len(fixtures)} total)")
            results[olp_league] = len(filtered)

            # Polite delay between leagues
            time.sleep(1.0)

        context.close()
        browser.close()

    return results


def list_cache() -> Dict[str, Dict[str, Any]]:
    """List all cached leagues with metadata."""
    result = {}
    if not CACHE_DIR.exists():
        return result

    for path in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            league = data.get("league", path.stem)
            result[league] = {
                "country": data.get("country", ""),
                "fixture_count": len(data.get("fixtures", [])),
                "fetched_at": data.get("fetched_at", 0),
                "age_hours": round((time.time() - data.get("fetched_at", 0)) / 3600, 1),
            }
        except Exception:
            pass
    return result


def clear_cache(leagues: Optional[List[str]] = None) -> int:
    """Clear cache for specified leagues (or all if None)."""
    count = 0
    targets = leagues or [p.stem for p in CACHE_DIR.glob("*.json")]
    for league in targets:
        path = _cache_path(league)
        if path.exists():
            path.unlink()
            count += 1
    return count


def main():
    # Reconfigure stdout/stderr to UTF-8 so page-derived text (team names,
    # breadcrumbs, web-font glyphs) prints cleanly on Windows' cp1252 console
    # instead of raising UnicodeEncodeError. No-op if already utf-8.
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8")
        _sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="SportyBet fixtures cache builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # build command
    build_parser = subparsers.add_parser("build", help="Build fixture cache")
    build_parser.add_argument("--leagues", nargs="*", help="OLP XDV league names to cache (default: all mapped)")
    build_parser.add_argument("--days-ahead", type=int, default=7, help="Days ahead to cache")
    build_parser.add_argument("--headed", action="store_true", help="Run browser headed (visible)")
    build_parser.add_argument("--slow-mo", type=int, default=0, help="Slow down operations by N ms")

    # list command
    subparsers.add_parser("list", help="List cached leagues")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear cache")
    clear_parser.add_argument("--leagues", nargs="*", help="Leagues to clear (default: all)")

    args = parser.parse_args()

    if args.command == "build":
        print(f"Building SportyBet fixture cache for {len(args.leagues or DEFAULT_LEAGUES)} leagues...")
        results = build_cache(
            leagues=args.leagues,
            days_ahead=args.days_ahead,
            headless=not args.headed,
            slow_mo=args.slow_mo,
        )
        total = sum(results.values())
        print(f"\nDone. Total fixtures cached: {total}")
        for league, count in results.items():
            status = "+" if count > 0 else "x"
            print(f"  {status} {league}: {count}")

    elif args.command == "list":
        caches = list_cache()
        if not caches:
            print("No cached leagues.")
        else:
            print(f"{'League':<30} {'Country':<20} {'Fixtures':>8} {'Age (hrs)':>10}")
            print("-" * 70)
            for league, info in sorted(caches.items()):
                print(f"{league:<30} {info['country']:<20} {info['fixture_count']:>8} {info['age_hours']:>10.1f}")

    elif args.command == "clear":
        count = clear_cache(args.leagues)
        print(f"Cleared {count} cache file(s).")


if __name__ == "__main__":
    main()