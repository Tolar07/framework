"""
SportyBet Nigeria client — Phase 2 (paper only, zero capital).

This module provides an API-based client for SportyBet's public endpoints.
It reads fixture lists and live odds from the Nigeria site (sportybet.com/ng)
using their internal API. All functions are idempotent and cache-friendly.

WHY THIS EXISTS
  The booking pipeline needs SportyBet fixture/odds data for the daily board
  and the paper-leg logger. SportyBet does not have a public API; this client
  uses their internal factsCenter API the same way the browser does, but without
  JavaScript execution (uses requests + direct API calls).

QUOTA / RATE LIMITS
  No official limits. This client defaults to 2s polite delay between requests.
  If SportyBet returns 429, the caller should back off exponentially.

USAGE
  from booking.sportybet_client import SportyBetClient
  client = SportyBetClient()
  fixtures = client.get_fixtures("England", "Premier League")
  odds = client.get_odds(fixture_id)

DEPLOY GATE
  Phase 2 = paper only. This module NEVER places bets. It only reads.
"""

from __future__ import annotations

import time
import re
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import requests
except ImportError:
    requests = None

# --- Constants ---
BASE_URL = "https://sportybet.com"
API_BASE = "https://www.sportybet.com/api/ng/factsCenter"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.sportybet.com/ng/sport/football",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "no-cache",
}

# Polite delay between requests (seconds)
DEFAULT_DELAY = 2.0

# Cache TTL for fixture lists (6 hours)
FIXTURES_CACHE_TTL = 6 * 3600
# Cache TTL for odds (1 minute - odds change rapidly)
ODDS_CACHE_TTL = 60

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet"


@dataclass
class Fixture:
    """A fixture as SportyBet lists it."""
    fixture_id: str
    home_team: str
    away_team: str
    kickoff_utc: str  # ISO format
    league: str
    country: str
    # Raw SportyBet data for debugging
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketOdds:
    """Odds for a single market on a fixture."""
    fixture_id: str
    market: str  # e.g. "1X2", "OVER_UNDER_2.5"
    outcomes: Dict[str, float]  # outcome_name -> decimal odds
    captured_at: str  # ISO format
    source: str = "sportybet.com/ng"


class SportyBetError(Exception):
    """Base exception for SportyBet client errors."""
    pass


class SportyBetRateLimited(SportyBetError):
    """Raised when SportyBet returns 429 Too Many Requests."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        msg = "SportyBet rate limited (429)"
        if retry_after:
            msg += f" — retry after {retry_after}s"
        super().__init__(msg)


class SportyBetClient:
    """Client for reading fixtures and odds from SportyBet Nigeria via API."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ):
        if requests is None:
            raise RuntimeError("requests not installed — pip install requests")

        self.delay = delay
        self.cache_dir = cache_dir or CACHE_DIR
        self.timeout = timeout
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        # Cache for tournament mapping (country -> tournament name -> id)
        self._tournament_cache: Optional[Dict] = None

    def _wait(self) -> None:
        """Enforce polite delay between requests."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _get(self, url: str, use_cache: bool = True, cache_ttl: int = FIXTURES_CACHE_TTL) -> str:
        """GET a URL with caching and polite delay."""
        self._wait()

        # Check cache first
        cache_key = self._cache_key(url)
        cache_path = self.cache_dir / cache_key
        if use_cache and cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < cache_ttl:
                return cache_path.read_text(encoding="utf-8")

        # Fetch live
        resp = self.session.get(url, timeout=self.timeout)
        self._last_request = time.time()

        if resp.status_code == 429:
            retry_after = None
            if "Retry-After" in resp.headers:
                try:
                    retry_after = int(resp.headers["Retry-After"])
                except ValueError:
                    pass
            raise SportyBetRateLimited(retry_after)

        resp.raise_for_status()
        html = resp.text

        # Write cache
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")

        return html

    def _cache_key(self, url: str) -> str:
        """Generate a filesystem-safe cache key from a URL."""
        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", "_") or "index"
        query = parsed.query.replace("&", "_").replace("=", "-")
        return f"{path}_{query}.json" if query else f"{path}.json"

    def _get_api(self, endpoint: str, params: Dict = None, cache_ttl: int = FIXTURES_CACHE_TTL) -> Dict:
        """Call SportyBet API endpoint with caching."""
        # Build URL with timestamp parameter
        import urllib.parse
        ts = int(time.time() * 1000)
        base_params = {"_t": ts}
        if params:
            base_params.update(params)
        query = urllib.parse.urlencode(base_params)
        url = f"{API_BASE}/{endpoint}?{query}"
        response_text = self._get(url, cache_ttl=cache_ttl)
        return json.loads(response_text)

    def _load_tournament_map(self) -> Dict:
        """Load the tournament mapping from the API (cached)."""
        if self._tournament_cache is not None:
            return self._tournament_cache

        # Get the popularAndSportList which has full country/tournament hierarchy
        data = self._get_api("popularAndSportList", {
            "sportId": "sr:sport:1",
            "timeline": "",
            "productId": "3"
        })

        sport_list = data.get("data", {}).get("sportList", [])
        tournament_map = {}

        if sport_list:
            for country in sport_list[0].get("categories", []):
                country_name = country["name"]
                tournament_map[country_name] = {}
                for tournament in country.get("tournaments", []):
                    tournament_map[country_name][tournament["name"]] = {
                        "id": tournament["id"],
                        "eventSize": tournament["eventSize"]
                    }

        self._tournament_cache = tournament_map
        return tournament_map

    def get_countries(self) -> List[Dict[str, str]]:
        """Get list of countries from SportyBet API."""
        tournament_map = self._load_tournament_map()
        countries = []
        for country_name, tournaments in tournament_map.items():
            if tournaments:
                countries.append({
                    "name": country_name,
                    "url": f"{BASE_URL}/ng/sport/football/{country_name.replace(' ', '-').lower()}"
                })
        return countries

    def get_leagues(self, country: str) -> List[Dict[str, str]]:
        """Get leagues for a given country."""
        tournament_map = self._load_tournament_map()
        leagues = []
        if country in tournament_map:
            for league_name, info in tournament_map[country].items():
                leagues.append({
                    "name": league_name,
                    "id": info["id"],
                    "eventSize": info["eventSize"],
                    "url": f"{BASE_URL}/ng/sport/football/{country.replace(' ', '-').lower()}/{league_name.replace(' ', '-').lower()}"
                })
        return leagues

    def get_fixtures(self, country: str, league: str, days_ahead: int = 3) -> List[Fixture]:
        """Get fixtures for a league within days_ahead using the upcoming events API."""
        tournament_map = self._load_tournament_map()

        # Find tournament ID
        tournament_id = None
        if country in tournament_map and league in tournament_map[country]:
            tournament_id = tournament_map[country][league]["id"]

        if not tournament_id:
            # Try to find by searching all tournaments
            for c, leagues in tournament_map.items():
                if league in leagues:
                    tournament_id = leagues[league]["id"]
                    country = c
                    break

        if not tournament_id:
            return []

        # Call the upcoming events API with tournamentId filter
        data = self._get_api("pcUpcomingEvents", {
            "sportId": "sr:sport:1",
            "marketId": "1,18,10,29,11,26,36,14,60100",
            "pageSize": "100",
            "pageNum": "1",
            "option": "1",
            "tournamentId": tournament_id
        })

        fixtures = []
        for tournament_data in data.get("data", {}).get("tournaments", []):
            if tournament_data.get("id") == tournament_id:
                for event in tournament_data.get("events", []):
                    fixture = self._parse_api_event(event, country, league, tournament_id)
                    if fixture:
                        # Filter by days_ahead
                        from datetime import datetime, timezone
                        kickoff = datetime.fromisoformat(fixture.kickoff_utc.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        days_diff = (kickoff - now).days
                        if 0 <= days_diff <= days_ahead:
                            fixtures.append(fixture)
                break

        return fixtures

    def _parse_api_event(self, event: Dict, country: str, league: str, tournament_id: str) -> Optional[Fixture]:
        """Parse a fixture from the API event structure."""
        try:
            fixture_id = event.get("gameId") or event.get("eventId")
            if not fixture_id:
                return None

            home_team = event.get("homeTeamName", "")
            away_team = event.get("awayTeamName", "")

            if not home_team or not away_team:
                return None

            # Convert timestamp to ISO format
            estimate_start = event.get("estimateStartTime")
            if estimate_start:
                kickoff_utc = datetime.fromtimestamp(estimate_start / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            else:
                kickoff_utc = ""

            return Fixture(
                fixture_id=str(fixture_id),
                home_team=home_team,
                away_team=away_team,
                kickoff_utc=kickoff_utc,
                league=league,
                country=country,
                raw={
                    "eventId": event.get("eventId"),
                    "tournamentId": tournament_id,
                    "matchStatus": event.get("matchStatus"),
                    "totalMarketSize": event.get("totalMarketSize"),
                }
            )
        except Exception:
            return None

    def get_odds(self, fixture_id: str) -> List[MarketOdds]:
        """Get odds for a specific fixture from the API."""
        # The pcUpcomingEvents API already includes odds in the markets array
        # We need to find the event in the API response
        # pageSize=200 returns 422, so use 100
        data = self._get_api("pcUpcomingEvents", {
            "sportId": "sr:sport:1",
            "marketId": "1,18,10,29,11,26,36,14,60100",
            "pageSize": "100",
            "pageNum": "1",
            "option": "1"
        }, cache_ttl=ODDS_CACHE_TTL)

        markets = []
        for tournament_data in data.get("data", {}).get("tournaments", []):
            for event in tournament_data.get("events", []):
                if str(event.get("gameId")) == str(fixture_id) or str(event.get("eventId")) == str(fixture_id):
                    for market in event.get("markets", []):
                        outcomes = {}
                        for outcome in market.get("outcomes", []):
                            name = outcome.get("desc", "")
                            odds_str = outcome.get("odds", "")
                            if name and odds_str:
                                try:
                                    outcomes[name] = float(odds_str)
                                except ValueError:
                                    pass

                        if outcomes:
                            canonical_key = self._normalize_market_key(market.get("name", ""), market.get("desc", ""))
                            markets.append(MarketOdds(
                                fixture_id=fixture_id,
                                market=canonical_key,
                                outcomes=outcomes,
                                captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            ))
                    break
            if markets:
                break

        return markets

    def _normalize_market_key(self, market_name: str, market_desc: str = "") -> str:
        """Map SportyBet market key to OLP XDV canonical key."""
        combined = (market_name + " " + market_desc).lower().replace(" ", "_")

        mapping = {
            # 1X2
            "1x2": "1X2_HOME",
            "match_winner": "1X2_HOME",
            "full_time_result": "1X2_HOME",
            # Double Chance
            "double_chance": "DC_1X",
            "dc": "DC_1X",
            "1x": "DC_1X",
            "x2": "DC_1X",
            "12": "DC_1X",
            # Totals
            "over_under_1_5": "OVER_1_5",
            "over_under_2_5": "OVER_2_5",
            "over_under_3_5": "OVER_3_5",
            "over_under_0_5": "OVER_0_5",
            "totals": "OVER_2_5",
            "over_1_5": "OVER_1_5",
            "under_1_5": "OVER_1_5",
            "over_2_5": "OVER_2_5",
            "under_2_5": "OVER_2_5",
            "over_3_5": "OVER_3_5",
            "under_3_5": "OVER_3_5",
            "over_0_5": "OVER_0_5",
            "under_0_5": "OVER_0_5",
            # BTTS
            "both_teams_to_score": "BTTS_YES",
            "btts": "BTTS_YES",
            "gg_ng": "BTTS_YES",
            "gg": "BTTS_YES",
            "ng": "BTTS_YES",
            # Draw No Bet
            "draw_no_bet": "DNB_HOME",
            "dnb": "DNB_HOME",
            "dnb_home": "DNB_HOME",
            "dnb_away": "DNB_HOME",
            # HT/FT
            "half_time_full_time": "HT_FT_11",
            "ht_ft": "HT_FT_11",
            "htft": "HT_FT_11",
            "1/1": "HT_FT_11",
            "1/x": "HT_FT_11",
            "1/2": "HT_FT_11",
            "x/1": "HT_FT_11",
            "x/x": "HT_FT_11",
            "x/2": "HT_FT_11",
            "2/1": "HT_FT_11",
            "2/x": "HT_FT_11",
            "2/2": "HT_FT_11",
            # Correct Score
            "correct_score": "CS_10",
            "exact_score": "CS_10",
            "1:0": "CS_10",
            "0:1": "CS_10",
            "1:1": "CS_10",
            "2:0": "CS_10",
            "0:2": "CS_10",
            "2:1": "CS_10",
            "1:2": "CS_10",
            "2:2": "CS_10",
            "0:0": "CS_10",
            "3:0": "CS_10",
            "0:3": "CS_10",
            "3:1": "CS_10",
            "1:3": "CS_10",
        }
        return mapping.get(combined, market_name.upper())

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "SportyBetClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# Need to import datetime/timezone for the fixture parsing
from datetime import datetime, timezone