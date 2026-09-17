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
            ))
    return out


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
