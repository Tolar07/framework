"""
SportyBet fixtures + FULL market prices via their factsCenter API (read-only).

WHY THIS EXISTS (2026-09-17)
Price coverage was the ceiling on production. The Playwright cache rebuild
could only reach competitions whose league PAGE loads, and for several it
resolves to the generic "Sports | SportyBet" landing page -- Estonian
Meistriliiga, Serbian Super Liga, Norwegian Eliteserien, Swedish Allsvenskan
all failed that way. Worse, the page scrape only ever yielded 1X2 plus a
SINGLE goals line, so a fixture whose 1X2 sat above the 1.50 cap had no other
market to fall back to and produced nothing.

The API has neither limit. Verified on 2026-09-17: every league that failed the
page scrape returns events here, with 15-27 markets each.

THE ACCESS DETAIL THAT MATTERS: the endpoint answers GET and returns 403 to
POST. booking/sportybet_client.py uses POST, which is why it could not be used
for this. Confirmed by control: POST -> 403 for Premier League too, so it was
never a per-league problem.

MARKETS RETURNED (ids passed in MARKET_IDS):
     1  1X2                 10  Double Chance     11  Draw No Bet
    18  Over/Under (EVERY line: 0.5 ... 5.5)      29  GG/NG (BTTS)
This supplies real QUOTED prices for double chance and draw no bet, which the
acca builder previously had to DERIVE from the 1X2 line and flag as optimistic.

PAPER-ONLY. This module only reads. It never places a bet.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import engine.markets as mkt

API_URL = "https://www.sportybet.com/api/ng/factsCenter/pcUpcomingEvents"

# Only the markets we can actually model. Handicap (14), Odd/Even (26),
# O/U+GG combo (36) and 1X2-2UP (60100) are deliberately NOT requested: the
# engine produces no probability for them, so a price we cannot compare an
# edge against is dead weight on every response.
MARKET_IDS = "1,10,11,18,29"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.sportybet.com/ng/sport/football",
}

REQUEST_TIMEOUT = 30
INTER_REQUEST_DELAY_S = 1.0


@dataclass
class ApiFixture:
    """One fixture with every market price we could map."""
    event_id: str
    home: str
    away: str
    league: str
    kickoff_utc: str                      # ISO, from estimateStartTime
    markets: dict = field(default_factory=dict)   # our mkt.* key -> price
    # SportyBet's short numeric id ("32838"). This is the value the fixture
    # cache stores as `id` and the booking driver resolves a slip against --
    # NOT eventId ("sr:match:72221274"). Carrying it is what lets the cache be
    # rebuilt from the API rather than from a page scrape.
    game_id: str = ""

    # Convenience accessors kept for the existing cache shape.
    @property
    def home_odds(self) -> Optional[float]:
        return self.markets.get(mkt.HOME)

    @property
    def draw_odds(self) -> Optional[float]:
        return self.markets.get(mkt.DRAW)

    @property
    def away_odds(self) -> Optional[float]:
        return self.markets.get(mkt.AWAY)


def _f(v) -> Optional[float]:
    """Price as float, or None. A zero/blank price is ABSENT, never 0.0."""
    try:
        f = float(v)
        return f if f > 1.0 else None
    except (TypeError, ValueError):
        return None


def _total_of(specifier: str) -> Optional[str]:
    """'total=2.5' -> '2.5'."""
    if not specifier:
        return None
    for part in str(specifier).split("|"):
        if part.startswith("total="):
            return part.split("=", 1)[1]
    return None


# Over/Under lines the engine has a probability for. SportyBet also quotes
# whole-number lines (1, 2, 3...) which are PUSH markets -- stake returned on
# exactly that score. They are a different bet from the half-lines and the
# model has no probability for them, so they are not mapped.
_OU_LINES = {
    "0.5": (mkt.OVER_05, mkt.UNDER_05),
    "1.5": (mkt.OVER_15, mkt.UNDER_15),
    "2.5": (mkt.OVER_25, mkt.UNDER_25),
    "3.5": (mkt.OVER_35, mkt.UNDER_35),
}


def _map_markets(raw_markets: list) -> dict:
    """SportyBet market payload -> {our market key: price}.

    Outcomes are matched on their `desc` text, which is stable and explicit
    ("Home or Draw", "Over 2.5", "Yes"). Matching on outcome ORDER would be a
    silent-corruption risk: a reordered payload would map prices onto the wrong
    selection with no error and no way to notice downstream.
    """
    out: dict = {}
    for m in raw_markets or []:
        mid = str(m.get("id"))
        outcomes = {str(o.get("desc") or "").strip().lower(): o.get("odds")
                    for o in (m.get("outcomes") or [])}

        if mid == "1":                                   # 1X2
            out[mkt.HOME] = _f(outcomes.get("home"))
            out[mkt.DRAW] = _f(outcomes.get("draw"))
            out[mkt.AWAY] = _f(outcomes.get("away"))

        elif mid == "10":                                # Double Chance
            out[mkt.DC_1X] = _f(outcomes.get("home or draw"))
            out[mkt.DC_12] = _f(outcomes.get("home or away"))
            out[mkt.DC_X2] = _f(outcomes.get("draw or away"))

        elif mid == "11":                                # Draw No Bet
            out[mkt.DNB_HOME] = _f(outcomes.get("home"))
            out[mkt.DNB_AWAY] = _f(outcomes.get("away"))

        elif mid == "29":                                # GG/NG == BTTS
            out[mkt.BTTS_YES] = _f(outcomes.get("yes"))
            out[mkt.BTTS_NO] = _f(outcomes.get("no"))

        elif mid == "18":                                # Over/Under, per line
            line = _total_of(m.get("specifier"))
            pair = _OU_LINES.get(line or "")
            if pair:
                over_key, under_key = pair
                out[over_key] = _f(outcomes.get(f"over {line}"))
                out[under_key] = _f(outcomes.get(f"under {line}"))

    # Drop unpriced entries so "key present" always means "price available".
    return {k: v for k, v in out.items() if v is not None}


def fetch_tournament(tournament_id: int | str, league: str,
                     session=None) -> list[ApiFixture]:
    """Upcoming fixtures + markets for one tournament. [] on any failure.

    Never raises: one competition's outage must not lose the rest of the slate.
    """
    import requests

    tid = str(tournament_id)
    if not tid.startswith("sr:tournament:"):
        tid = f"sr:tournament:{tid}"

    params = {
        "sportId": "sr:sport:1",
        "marketId": MARKET_IDS,
        "pageSize": "100",
        "pageNum": 1,
        "option": 1,
        "tournamentId": tid,
    }

    get = (session or requests).get
    try:
        # GET, not POST -- POST is rejected with 403 (see module docstring).
        r = get(API_URL, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return []
        payload = r.json()
    except Exception:
        return []

    out: list[ApiFixture] = []
    for t in ((payload.get("data") or {}).get("tournaments") or []):
        for ev in (t.get("events") or []):
            home = (ev.get("homeTeamName") or "").strip()
            away = (ev.get("awayTeamName") or "").strip()
            if not home or not away:
                continue  # HR35: incomplete record is skipped, never guessed

            # estimateStartTime is epoch MILLISECONDS. This is a real confirmed
            # kickoff -- a second independent source of the time the fetch layer
            # was previously missing entirely.
            kickoff = ""
            ts = ev.get("estimateStartTime")
            try:
                if ts:
                    kickoff = datetime.fromtimestamp(
                        int(ts) / 1000, tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                kickoff = ""

            markets = _map_markets(ev.get("markets") or [])
            if not markets:
                continue  # no priced market -> nothing bettable here

            out.append(ApiFixture(
                event_id=str(ev.get("eventId") or ev.get("gameId") or ""),
                home=home, away=away, league=league,
                kickoff_utc=kickoff, markets=markets,
                game_id=str(ev.get("gameId") or ""),
            ))
    return out


# ---------------------------------------------------------------------------
# Cache writing — so the booking driver can resolve what the board priced
# ---------------------------------------------------------------------------
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "sportybet" / "fixtures"


def _goals_line_and_prices(markets: dict) -> tuple:
    """Pick one representative goals line for the legacy cache fields.

    The cache schema predates the full market map and holds a SINGLE
    over/under line. 2.5 is preferred because it is the line most consumers
    assume; otherwise the first available half-line is used. The complete set
    still travels in `markets`, so nothing is lost -- this only fills the older
    fields that existing readers still look at.
    """
    for line, over_key, under_key in ((2.5, mkt.OVER_25, mkt.UNDER_25),
                                      (1.5, mkt.OVER_15, mkt.UNDER_15),
                                      (3.5, mkt.OVER_35, mkt.UNDER_35),
                                      (0.5, mkt.OVER_05, mkt.UNDER_05)):
        if over_key in markets or under_key in markets:
            return line, markets.get(over_key), markets.get(under_key)
    return None, None, None


def write_cache(league: str, fixtures: list, country: str = "") -> Optional[Path]:
    """Write API fixtures into the SportyBet fixture cache the booking driver reads.

    WHY: the board and the booking driver were reading DIFFERENT sources. Stage
    B priced fixtures from this API (in memory), while booking_codes resolved
    slips against the Playwright-scraped cache on disk. So the board could
    price a fixture the booking driver then reported as "fixture not found in
    SportyBet cache" -- which is exactly what happened on 2026-09-17: a board
    with ten priced legs produced ZERO booking codes.

    Writing the API result into the same cache closes that split. The full
    market map is stored alongside the legacy fields so both old and new
    readers work.

    Returns the path written, or None when there is nothing to write -- an
    empty cache file would look like "this league has no fixtures" rather than
    "we could not fetch it".
    """
    import json

    if not fixtures:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{league.replace(' ', '_').replace('/', '_')}.json"

    rows = []
    for fx in fixtures:
        line, over, under = _goals_line_and_prices(fx.markets)
        rows.append({
            # `id` must be the SHORT numeric gameId: that is what the booking
            # driver resolves against. eventId ("sr:match:...") is kept beside
            # it rather than in its place.
            "id": fx.game_id or fx.event_id,
            "event_id": fx.event_id,
            "home": fx.home,
            "away": fx.away,
            "kickoff": fx.kickoff_utc,
            "league": league,
            "home_odds": fx.markets.get(mkt.HOME),
            "draw_odds": fx.markets.get(mkt.DRAW),
            "away_odds": fx.markets.get(mkt.AWAY),
            "goals_line": line,
            "over_odds": over,
            "under_odds": under,
            # The complete market map, keyed by canonical market key.
            "markets": fx.markets,
            "raw_market": {},
        })

    path.write_text(json.dumps({
        # UNIX TIMESTAMP, not ISO. bridge.load_sportybet_fixtures computes
        # `time.time() - data["fetched_at"]` for the staleness check, so an ISO
        # string raises TypeError there. That exception is swallowed upstream
        # and surfaces as "fixture not found in SportyBet cache" -- a message
        # that points at missing data when the data is present and the cache
        # header is simply the wrong type. Cost an entire booking run to find.
        "fetched_at": time.time(),
        "fetched_at_iso": datetime.now(timezone.utc).isoformat(),  # humans
        "league": league,
        "country": country,
        "source": "factsCenter-api",
        "fixtures": rows,
    }, indent=2), encoding="utf-8")
    return path


def fetch_leagues(league_ids: dict[str, tuple], on_progress=None) -> dict:
    """Fetch many competitions. `league_ids` maps league -> (category, tournament).

    Returns {league: [ApiFixture, ...]} for competitions that returned anything.
    A competition with no id, or that errors, is simply absent -- reported by
    the caller, never substituted.
    """
    import requests

    session = requests.Session()
    session.headers.update(HEADERS)

    results: dict[str, list[ApiFixture]] = {}
    for league, ids in league_ids.items():
        if not ids or tuple(ids)[:2] == (0, 0):
            continue
        tournament_id = tuple(ids)[1]
        fixtures = fetch_tournament(tournament_id, league, session=session)
        if fixtures:
            results[league] = fixtures
        if on_progress:
            on_progress(league, len(fixtures))
        time.sleep(INTER_REQUEST_DELAY_S)
    return results
