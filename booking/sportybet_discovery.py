"""Availability-driven competition discovery from SportyBet.

WHY THIS EXISTS
  rebuild_cache.py used to walk a hardcoded list of 14 leagues and scrape each
  one's page. That asks the wrong question. On 2026-09-16 that list spent its
  whole run on leagues that were dark -- the Premier League, Serie A, the
  Bundesliga and Ligue 1 all had zero fixtures -- while the four EFL Cup ties
  and nine Europa League ties that WERE on went uncached, because neither
  competition is in the list.

  The question to ask first is "which competitions are up today", and only
  then "what is on in them". This module asks it in that order: one call to
  SportyBet's upcoming-events feed returns every football competition with a
  fixture inside the window, and the caller picks from what is actually there.

WHY THE FEED AND NOT THE PAGES
  Each event in the feed carries its own sport/category/tournament block, so a
  fixture is labelled by the source with the competition it belongs to. That
  removes the failure the id table and the purity gate in rebuild_cache.py
  exist to catch -- you cannot get Serie A rows filed under La Liga when every
  row names its own tournament. It also arrives with odds attached, so the
  fixture and its price come from one read instead of two.

  The id table is still worth keeping correct: it is what the DOM scraper
  falls back to, and what the booking codes navigate by.

TRANSPORT
  SportyBet answers a plain `requests` call to this endpoint with `202 ACCEPTED`
  and an empty body -- it wants a browser that has been to the site. So the
  fetch runs through Playwright's request context on a page that has already
  loaded sportybet.com and holds its cookies. That is the same path
  rebuild_cache.py already uses.

READ ONLY
  Phase 2. This module reads the public odds feed and writes cache files. It
  never books and never stakes.

USAGE
    py -3.12 -m booking.sportybet_discovery              # list today
    py -3.12 -m booking.sportybet_discovery --days 2
    py -3.12 -m booking.sportybet_discovery --mapped-only --write-cache
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from booking.league_map import SPORTYBET_LEAGUES

API_URL = "https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"
WARMUP_URL = "https://www.sportybet.com/ng/sport/football"
FOOTBALL = "sr:sport:1"

# 1 = 1X2, 18 = Over/Under, 10 = Double Chance, 29 = Both Teams To Score.
# The feed returns whichever of these each event actually has open.
MARKET_IDS = "1,18,10,29"

PAGE_SIZE = 100
MAX_PAGES = 40           # 4000 events; the 48h window is ~500
REQUEST_TIMEOUT_MS = 60_000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# --- Simulated fixtures ----------------------------------------------------

# SportyBet carries "Simulated Reality League" alongside real football: engine-
# generated matches between real clubs, priced and bookable like anything else.
# On 2026-09-16 the feed offered "LaLiga SRL -- Atletico Madrid SRL v Osasuna
# SRL" at 08:00, a simulation of the same card as the real 17:00 fixture.
#
# Nothing downstream distinguishes them, and the " SRL" suffix is inconsistently
# cased ("Racing de Santander Srl"), so a fuzzy team matcher will happily pair a
# simulated fixture with a real one. These are dropped at the source and can
# never reach a board, whatever anyone later adds to SPORTYBET_LEAGUES.
EXCLUDED_CATEGORY_IDS = {
    "sr:category:2123",          # Simulated Reality League
}

EXCLUDED_CATEGORY_PATTERNS = (
    "simulatedreality",
    "srl",
)


def is_simulated(category: str, category_id: str = "", tournament: str = "") -> bool:
    """True for engine-generated fixtures that must never reach a board."""
    if category_id in EXCLUDED_CATEGORY_IDS:
        return True
    cat = _norm(category)
    if any(pat in cat for pat in EXCLUDED_CATEGORY_PATTERNS):
        return True
    # Tournament names end in SRL rather than containing it; matching the
    # suffix avoids catching a real competition whose name happens to contain
    # those letters.
    return _norm(tournament).endswith("srl")


# --- OLP league name lookup ------------------------------------------------

def _norm(s: str) -> str:
    """Fold the spelling differences between our map and SportyBet's feed.

    Our map says "La Liga", the feed says "LaLiga"; our map says "HNL", the
    feed says "1. HNL". Case, spaces, dots and punctuation are noise here.
    """
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# SPORTYBET_LEAGUES carries several names for one competition, and after
# normalisation a few more collide ("La Liga" / "LaLiga"). The label we emit has
# to be the one the rest of the framework indexes on, so it is stated rather
# than derived: counted against the codebase on 2026-09-16, each of these
# outnumbers its alias by at least 8:1. A length or alphabetical tie-break
# would have chosen wrong in seven of these eight.
CANONICAL_OLP_NAMES = {
    "La Liga",                  # over "LaLiga"            (369 vs 13)
    "Belgian Pro League",       # over "Pro League"        (211 vs 8)
    "Greek Super League",       # over "Super League Greece" (120 vs 17)
    "Norwegian Eliteserien",    # over "Eliteserien"       (210 vs 24)
    "Primeira Liga",            # over "Liga Portugal"     (245 vs 13)
    "Swedish Allsvenskan",      # over "Allsvenskan"       (239 vs 30)
    "Swiss Super League",       # over "Super League"      (194 vs 17)
    "Turkish Super Lig",        # over "Süper Lig"         (217 vs 22)
}


def _build_olp_index() -> dict[tuple[str, str], str]:
    """(category, tournament) as SportyBet spells them -> our league name.

    Where several OLP names point at one competition, CANONICAL_OLP_NAMES
    decides; failing that the first one wins, which keeps the mapping stable
    but is a sign the alias should be added to that set.
    """
    index: dict[tuple[str, str], str] = {}
    for olp_name, bm in SPORTYBET_LEAGUES.items():
        key = (_norm(bm.country), _norm(bm.league))
        prior = index.get(key)
        if prior is None or (olp_name in CANONICAL_OLP_NAMES
                             and prior not in CANONICAL_OLP_NAMES):
            index[key] = olp_name
    return index


OLP_INDEX = _build_olp_index()


def olp_league_name(category: str, tournament: str) -> str | None:
    """Our name for this competition, or None if we do not have one.

    Returning None is deliberate and is the HR35 behaviour: an unmapped
    competition is reported as unmapped, never guessed into the nearest
    league. Filing Egypt's Second Division B under "Serie B" because the
    names rhyme is exactly the contamination this pipeline keeps getting bitten
    by.
    """
    return OLP_INDEX.get((_norm(category), _norm(tournament)))


# --- Shapes ----------------------------------------------------------------

@dataclass
class DiscoveredEvent:
    """One fixture as the feed gives it, with its 1X2 price if one is open."""
    event_id: str                 # "sr:match:74158488" -- Betradar's id
    home: str
    away: str
    kickoff: str                  # ISO-8601, UTC
    game_id: str = ""             # SportyBet's own id; what booking codes use
    home_id: str = ""
    away_id: str = ""
    venue: str = ""
    odds: dict[str, float] = field(default_factory=dict)   # home/draw/away
    markets: list[dict[str, Any]] = field(default_factory=list)

    @property
    def kickoff_date(self) -> str:
        return self.kickoff[:10]

    @property
    def has_odds(self) -> bool:
        return len(self.odds) == 3


@dataclass
class Competition:
    """One competition that has at least one fixture inside the window."""
    category: str                 # "England"
    tournament: str               # "EFL Cup"
    category_id: str              # "sr:category:1"
    tournament_id: str            # "sr:tournament:21"
    events: list[DiscoveredEvent] = field(default_factory=list)

    @property
    def olp_name(self) -> str | None:
        return olp_league_name(self.category, self.tournament)

    @property
    def is_mapped(self) -> bool:
        return self.olp_name is not None

    @property
    def label(self) -> str:
        return f"{self.category} / {self.tournament}"

    @property
    def numeric_ids(self) -> tuple[int, int] | None:
        """(category, tournament) as the plain integers the URLs use."""
        cat = re.search(r"(\d+)$", self.category_id or "")
        tour = re.search(r"(\d+)$", self.tournament_id or "")
        if not cat or not tour:
            return None
        return int(cat.group(1)), int(tour.group(1))

    @property
    def priced_events(self) -> list[DiscoveredEvent]:
        return [e for e in self.events if e.has_odds]


# --- Parsing ---------------------------------------------------------------

_OUTCOME_SLOT = {"1": "home", "2": "draw", "3": "away"}


def _parse_1x2(markets: Iterable[dict[str, Any]]) -> dict[str, float]:
    """Pull home/draw/away out of the 1X2 market.

    Returns {} unless all three are present, active and priced above evens --
    a partial or suspended market is not a quote, and 1.00 is the feed's
    placeholder for "no price", not a price. Same rule as _extract_row_odds in
    rebuild_cache.py.
    """
    for m in markets or []:
        if str(m.get("id")) != "1" or m.get("specifier"):
            continue
        if m.get("status") not in (0, None):     # non-zero = suspended/settled
            continue
        out: dict[str, float] = {}
        for oc in m.get("outcomes") or []:
            slot = _OUTCOME_SLOT.get(str(oc.get("id")))
            if slot is None or not oc.get("isActive"):
                continue
            try:
                price = float(oc.get("odds"))
            except (TypeError, ValueError):
                continue
            if price <= 1.0:
                continue
            out[slot] = price
        if len(out) == 3:
            return out
    return {}


def _parse_event(raw: dict[str, Any]) -> DiscoveredEvent | None:
    ts = raw.get("estimateStartTime")
    home, away = raw.get("homeTeamName"), raw.get("awayTeamName")
    if not ts or not home or not away:
        return None                      # incomplete row -> drop it, HR35
    kickoff = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    markets = raw.get("markets") or []
    return DiscoveredEvent(
        event_id=raw.get("eventId") or "",
        home=home.strip(),
        away=away.strip(),
        kickoff=kickoff.isoformat(),
        game_id=str(raw.get("gameId") or ""),
        home_id=raw.get("homeTeamId") or "",
        away_id=raw.get("awayTeamId") or "",
        venue=((raw.get("fixtureVenue") or {}).get("name") or ""),
        odds=_parse_1x2(markets),
        markets=markets,
    )


def _collect(payload: dict[str, Any], into: dict[tuple[str, str], Competition]) -> int:
    """Fold one page into `into`, keyed by the feed's own tournament ids."""
    added = 0
    for t in (payload.get("data") or {}).get("tournaments") or []:
        cat_id = t.get("categoryId") or ""
        tour_id = t.get("id") or ""
        key = (cat_id, tour_id)
        if is_simulated((t.get("categoryName") or ""), cat_id, (t.get("name") or "")):
            continue
        comp = into.get(key)
        if comp is None:
            comp = Competition(
                category=(t.get("categoryName") or "").strip(),
                tournament=(t.get("name") or "").strip(),
                category_id=cat_id,
                tournament_id=tour_id,
            )
            into[key] = comp
        for raw in t.get("events") or []:
            ev = _parse_event(raw)
            if ev is not None:
                comp.events.append(ev)
                added += 1
    return added


# --- Fetch -----------------------------------------------------------------

async def fetch_competitions(page, timeline_hours: int = 24) -> list[Competition]:
    """Every football competition with a fixture in the next `timeline_hours`.

    `page` is a Playwright Page that has already loaded sportybet.com; the
    request context inherits its cookies, which is what gets us a 200 instead
    of the empty 202 a bare HTTP client receives.
    """
    found: dict[tuple[str, str], Competition] = {}
    pages_expected = MAX_PAGES

    for page_num in range(1, MAX_PAGES + 1):
        resp = await page.request.get(
            API_URL,
            params={
                "sportId": FOOTBALL,
                "marketId": MARKET_IDS,
                "pageSize": PAGE_SIZE,
                "pageNum": page_num,
                "option": 1,
                "timeline": timeline_hours,
                "productId": 3,
            },
            timeout=REQUEST_TIMEOUT_MS,
        )
        if resp.status != 200:
            raise RuntimeError(
                f"SportyBet upcoming-events returned HTTP {resp.status} on page "
                f"{page_num}. Not falling back to a partial list -- a short read "
                f"looks identical to a quiet day (HR35)."
            )
        payload = await resp.json()

        if page_num == 1:
            total = (payload.get("data") or {}).get("totalNum")
            if isinstance(total, int) and total > 0:
                pages_expected = min(MAX_PAGES, math.ceil(total / PAGE_SIZE))

        if _collect(payload, found) == 0:
            break
        if page_num >= pages_expected:
            break

    return list(found.values())


async def discover(
    days: int = 1,
    start: date | None = None,
    require_odds: bool = False,
    browser_args: list[str] | None = None,
) -> list[Competition]:
    """Competitions with fixtures on the `days` days from `start` (today).

    The window is a whole number of local days, so `days=1` means "today" and
    events after midnight are dropped even though the feed volunteers them.
    """
    from playwright.async_api import async_playwright

    first = start or date.today()
    wanted = {(first + timedelta(days=i)).isoformat() for i in range(max(1, days))}
    # Ask for a little past the end of the window; the feed's clock is UTC and
    # ours may not be.
    timeline = min(72, max(24, 24 * max(1, days) + 12))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, args=browser_args or ["--no-sandbox"]
        )
        try:
            ctx = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 900},
            )
            page = await ctx.new_page()
            await page.goto(WARMUP_URL, wait_until="domcontentloaded", timeout=90_000)
            await page.wait_for_timeout(4_000)
            comps = await fetch_competitions(page, timeline_hours=timeline)
        finally:
            await browser.close()

    out: list[Competition] = []
    for comp in comps:
        events = [e for e in comp.events if e.kickoff_date in wanted]
        if require_odds:
            events = [e for e in events if e.has_odds]
        if not events:
            continue
        comp.events = sorted(events, key=lambda e: (e.kickoff, e.home))
        out.append(comp)

    out.sort(key=lambda c: (not c.is_mapped, -len(c.events), c.label))
    return out


# --- Cache ---------------------------------------------------------------

def to_cached_fixtures(comp: Competition) -> list:
    """A mapped competition as the CachedFixture rows the cache stores.

    Raises for an unmapped competition rather than inventing a league label --
    a cache file is keyed by league name, and a wrong key here is precisely the
    contamination the rest of this pipeline spends its effort catching.
    """
    from booking.rebuild_cache import CachedFixture

    league = comp.olp_name
    if league is None:
        raise ValueError(
            f"{comp.label} has no OLP league name; add it to SPORTYBET_LEAGUES "
            f"before caching it (HR35 -- do not guess a label)"
        )

    rows = []
    for e in comp.events:
        market: dict[str, Any] = {}
        if e.has_odds:
            market["1x2"] = dict(e.odds)
        # Betradar's match id is what joins this row to FlashScore and to the
        # other Betradar-fed sources, so it travels with the fixture.
        market["event_id"] = e.event_id
        market["source"] = "sportybet_api"
        rows.append(CachedFixture(
            id=e.game_id or e.event_id or f"{comp.tournament_id}:{len(rows)}",
            home=e.home,
            away=e.away,
            kickoff=e.kickoff,
            league=league,
            raw_market=market,
        ))
    return rows


def write_caches(comps: list[Competition], verbose: bool = True) -> dict[str, int]:
    """Write one cache file per mapped competition. Returns league -> count.

    Unmapped competitions are skipped and named, not silently dropped: the
    list of what we could see but could not file is the input to extending
    SPORTYBET_LEAGUES.
    """
    from booking.rebuild_cache import _write_cache

    written: dict[str, int] = {}
    skipped: list[str] = []
    for comp in comps:
        if not comp.is_mapped:
            skipped.append(comp.label)
            continue
        rows = to_cached_fixtures(comp)
        if not rows:
            continue
        _write_cache(comp.olp_name, comp.category, rows)
        written[comp.olp_name] = len(rows)

    if verbose and skipped:
        print(f"\n  [SKIP] {len(skipped)} competitions have no OLP league name:")
        for label in skipped[:15]:
            print(f"         {label}")
        if len(skipped) > 15:
            print(f"         ... and {len(skipped) - 15} more")
    return written


# --- Reporting -------------------------------------------------------------

def format_report(comps: list[Competition], show_fixtures: bool = False) -> str:
    lines: list[str] = []
    mapped = [c for c in comps if c.is_mapped]
    unmapped = [c for c in comps if not c.is_mapped]
    total = sum(len(c.events) for c in comps)
    priced = sum(len(c.priced_events) for c in comps)

    lines.append(
        f"{len(comps)} competitions, {total} fixtures, {priced} priced "
        f"({len(mapped)} competitions known to OLP, {len(unmapped)} unmapped)"
    )

    for heading, group in (("KNOWN TO OLP", mapped), ("UNMAPPED", unmapped)):
        if not group:
            continue
        lines.append("")
        lines.append(f"--- {heading} ---")
        for c in group:
            name = f" -> {c.olp_name}" if c.is_mapped else ""
            ids = c.numeric_ids
            id_txt = f"  [{ids[0]}, {ids[1]}]" if ids else ""
            lines.append(
                f"  {len(c.events):3d} ({len(c.priced_events)} priced)  "
                f"{c.label}{name}{id_txt}"
            )
            if show_fixtures:
                for e in c.events:
                    price = (
                        "  ".join(f"{k} {v:.2f}" for k, v in e.odds.items())
                        if e.has_odds else "NO PRICE"
                    )
                    lines.append(
                        f"        {e.kickoff[11:16]}  {e.home} v {e.away}   {price}"
                    )
    return "\n".join(lines)


# --- CLI -------------------------------------------------------------------

def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Ask SportyBet which competitions are actually on, "
                    "before deciding what to scrape."
    )
    ap.add_argument("--days", type=int, default=1,
                    help="window in whole days starting today (default 1)")
    ap.add_argument("--fixtures", action="store_true",
                    help="list every fixture, not just the competition counts")
    ap.add_argument("--mapped-only", action="store_true",
                    help="drop competitions OLP has no league name for")
    ap.add_argument("--require-odds", action="store_true",
                    help="drop fixtures with no open 1X2 market")
    ap.add_argument("--write-cache", action="store_true",
                    help="write the fixture cache for every mapped competition")
    ap.add_argument("--json", dest="as_json", metavar="PATH",
                    help="also write the result as JSON")
    args = ap.parse_args()

    comps = asyncio.run(discover(days=args.days, require_odds=args.require_odds))
    if args.mapped_only:
        comps = [c for c in comps if c.is_mapped]

    print(format_report(comps, show_fixtures=args.fixtures))

    if args.write_cache:
        written = write_caches(comps)
        total = sum(written.values())
        print(f"\n  wrote {len(written)} cache files, {total} fixtures")

    if args.as_json:
        from dataclasses import asdict
        payload = [
            {**{k: v for k, v in asdict(c).items() if k != "events"},
             "olp_name": c.olp_name,
             "events": [{k: v for k, v in asdict(e).items() if k != "markets"}
                        for e in c.events]}
            for c in comps
        ]
        with open(args.as_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"\nwrote {args.as_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
