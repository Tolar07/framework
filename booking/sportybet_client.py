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
  No official limits. This client implements exponential backoff with circuit breaker
  to handle 429/5xx gracefully. Retries are capped to avoid quota exhaustion.

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
import random
import threading
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

# Cache TTL for fixture lists (6 hours)
FIXTURES_CACHE_TTL = 6 * 3600
# Cache TTL for odds (1 minute - odds change rapidly)
ODDS_CACHE_TTL = 60

# Default delay between requests (seconds) - polite rate limiting
DEFAULT_DELAY = 1.0

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet"

# --- Circuit Breaker & Retry Configuration ---
# Circuit breaker: opens after 5 consecutive failures, cooldown 60s
CB_FAILURE_THRESHOLD = 5
CB_COOLDOWN_SECONDS = 60.0

# Retry: max 3 retries, exponential backoff starting at 2s, max 30s
MAX_RETRIES = 3
BASE_BACKOFF = 2.0
MAX_BACKOFF = 30.0

# Per-endpoint circuit breakers
_BREAKERS: dict[str, "CircuitBreaker"] = {}
_BREAKER_LOCK = threading.Lock()

# --- Failure Rate Tracking ---
# Track failure rates per endpoint for monitoring/alerting
_FAILURE_STATS: dict[str, dict] = {}
_FAILURE_STATS_LOCK = threading.Lock()

# Alert threshold: if failure rate exceeds this in the last hour, trigger alert
FAILURE_RATE_ALERT_THRESHOLD = 0.20  # 20% failure rate
FAILURE_COUNT_ALERT_THRESHOLD = 10   # At least 10 attempts before alerting


def _record_failure_stat(endpoint: str, success: bool) -> None:
    """Record a request outcome for failure rate tracking."""
    with _FAILURE_STATS_LOCK:
        if endpoint not in _FAILURE_STATS:
            _FAILURE_STATS[endpoint] = {
                "total": 0,
                "failures": 0,
                "successes": 0,
                "window_start": time.time(),
                "last_failure": None,
                "consecutive_failures": 0,
            }
        stats = _FAILURE_STATS[endpoint]
        stats["total"] += 1
        if success:
            stats["successes"] += 1
            stats["consecutive_failures"] = 0
        else:
            stats["failures"] += 1
            stats["last_failure"] = time.time()
            stats["consecutive_failures"] += 1
        # Reset window after 1 hour
        if time.time() - stats["window_start"] > 3600:
            stats["total"] = 1
            stats["failures"] = 0 if success else 1
            stats["successes"] = 1 if success else 0
            stats["window_start"] = time.time()
            stats["consecutive_failures"] = 0 if success else 1


def get_failure_stats(endpoint: str = None) -> dict:
    """Get failure statistics for monitoring/alerting.

    Args:
        endpoint: Specific endpoint to get stats for, or None for all.

    Returns:
        Dict with failure statistics including rate, counts, and alert status.
    """
    with _FAILURE_STATS_LOCK:
        if endpoint:
            stats = _FAILURE_STATS.get(endpoint, {})
            if not stats:
                return {"endpoint": endpoint, "total": 0, "failures": 0, "rate": 0.0, "alert": False}
            rate = stats["failures"] / stats["total"] if stats["total"] > 0 else 0.0
            alert = (
                stats["total"] >= FAILURE_COUNT_ALERT_THRESHOLD and
                rate >= FAILURE_RATE_ALERT_THRESHOLD
            )
            return {
                "endpoint": endpoint,
                "total": stats["total"],
                "failures": stats["failures"],
                "successes": stats["successes"],
                "rate": rate,
                "consecutive_failures": stats.get("consecutive_failures", 0),
                "last_failure": stats.get("last_failure"),
                "alert": alert,
            }
        # Return all endpoints
        result = {}
        for ep, stats in _FAILURE_STATS.items():
            rate = stats["failures"] / stats["total"] if stats["total"] > 0 else 0.0
            alert = (
                stats["total"] >= FAILURE_COUNT_ALERT_THRESHOLD and
                rate >= FAILURE_RATE_ALERT_THRESHOLD
            )
            result[ep] = {
                "total": stats["total"],
                "failures": stats["failures"],
                "successes": stats["successes"],
                "rate": rate,
                "consecutive_failures": stats.get("consecutive_failures", 0),
                "last_failure": stats.get("last_failure"),
                "alert": alert,
            }
        return result


def reset_failure_stats(endpoint: str = None) -> None:
    """Reset failure statistics (for testing or after remediation)."""
    with _FAILURE_STATS_LOCK:
        if endpoint:
            if endpoint in _FAILURE_STATS:
                del _FAILURE_STATS[endpoint]
        else:
            _FAILURE_STATS.clear()


class CircuitBreaker:
    """Simple per-endpoint circuit breaker.

    States: CLOSED (normal) -> OPEN (refusing, after failures) -> HALF_OPEN
    (probing) -> CLOSED (recovered) or OPEN again.
    """

    def __init__(self, failure_threshold: int = CB_FAILURE_THRESHOLD,
                 cooldown_seconds: float = CB_COOLDOWN_SECONDS):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._state = "CLOSED"          # CLOSED | OPEN | HALF_OPEN
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "OPEN" and self._opened_at is not None and \
                    time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._state = "HALF_OPEN"
            return self._state

    def allow_request(self) -> bool:
        return self.state != "OPEN"

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state in ("OPEN", "HALF_OPEN"):
                self._state = "CLOSED"
                self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            if self._state == "HALF_OPEN":
                # Probe failed — straight back to OPEN for a full cooldown.
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                self._failures = 0
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = "OPEN"
                self._opened_at = time.monotonic()
                self._failures = 0

    def __repr__(self) -> str:
        return f"<CircuitBreaker state={self.state} failures={self._failures}>"


def _get_breaker(name: str) -> CircuitBreaker:
    with _BREAKER_LOCK:
        if name not in _BREAKERS:
            _BREAKERS[name] = CircuitBreaker()
        return _BREAKERS[name]


def _is_transient(status_code: Optional[int]) -> bool:
    if status_code is None:
        return True  # network-level exception
    return status_code == 429 or status_code >= 500


def _sleep_backoff(attempt: int, base: float = BASE_BACKOFF, cap: float = MAX_BACKOFF) -> None:
    backoff = min(base * (2 ** (attempt - 1)), cap)
    time.sleep(backoff + random.uniform(0, 0.5))  # jitter: avoid thundering herd


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
        """GET a URL with caching, circuit breaker, and exponential backoff."""
        self._wait()

        # Check cache first
        cache_key = self._cache_key(url)
        cache_path = self.cache_dir / cache_key
        if use_cache and cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < cache_ttl:
                return cache_path.read_text(encoding="utf-8")

        # Fetch live with circuit breaker and retries
        breaker = _get_breaker("sportybet_api")
        attempts = 0
        while True:
            if not breaker.allow_request():
                raise RuntimeError(
                    f"Circuit breaker 'sportybet_api' OPEN — refusing request to {url} "
                    f"(degrade to NO DATA — PENDING)")

            attempts += 1
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except (requests.RequestException, OSError) as e:
                # Network-level failure (no HTTP response at all) -> transient.
                breaker.record_failure()
                _record_failure_stat(url, success=False)
                if attempts >= MAX_RETRIES:
                    raise
                _sleep_backoff(attempts)
                continue

            self._last_request = time.time()

            if _is_transient(resp.status_code):
                breaker.record_failure()
                _record_failure_stat(url, success=False)
                if resp.status_code == 429:
                    retry_after = None
                    if "Retry-After" in resp.headers:
                        try:
                            retry_after = int(resp.headers["Retry-After"])
                        except ValueError:
                            pass
                    if attempts >= MAX_RETRIES:
                        raise SportyBetRateLimited(retry_after)
                if attempts >= MAX_RETRIES:
                    resp.raise_for_status()  # raise the last 429/5xx
                _sleep_backoff(attempts)
                continue

            # Deterministic 4xx -> record + raise NOW, never retry (wastes quota).
            if resp.status_code >= 400:
                breaker.record_failure()
                _record_failure_stat(url, success=False)
                resp.raise_for_status()

            breaker.record_success()
            _record_failure_stat(url, success=True)
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
        """Call SportyBet API endpoint with caching and circuit breaker."""
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

    def get_odds(self, fixture_id: str, tournament_id: str = None) -> List[MarketOdds]:
        """Get odds for a specific fixture from the API.

        Args:
            fixture_id: The SportyBet fixture ID
            tournament_id: Optional tournament ID (e.g., "sr:tournament:17" for Premier League).
                           If not provided, queries all tournaments (may miss fixtures on later pages).
        """
        params = {
            "sportId": "sr:sport:1",
            "marketId": "1,18,10,29,11,26,36,14,60100",
            "pageSize": "100",
            "pageNum": "1",
            "option": "1"
        }
        if tournament_id:
            params["tournamentId"] = tournament_id

        data = self._get_api("pcUpcomingEvents", params, cache_ttl=ODDS_CACHE_TTL)

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