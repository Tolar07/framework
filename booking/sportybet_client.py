"""
SportyBet Nigeria client — Phase 2 (paper only, zero capital).

This module provides a requests-based client for SportyBet's public website.
It reads fixture lists and live odds from the Nigeria site (sportybet.com/ng)
without authentication. All functions are idempotent and cache-friendly.

WHY THIS EXISTS
  The booking pipeline needs SportyBet fixture/odds data for the daily board
  and the paper-leg logger. SportyBet does not have a public API; this client
  scrapes the public web pages the same way a browser would, but without
  JavaScript execution (uses requests + BeautifulSoup).

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
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

# --- Constants ---
BASE_URL = "https://www.sportybet.com"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
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
    """Client for reading fixtures and odds from SportyBet Nigeria."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        cache_dir: Optional[Path] = None,
        timeout: int = 30,
    ):
        if requests is None:
            raise RuntimeError("requests not installed — pip install requests")
        if BeautifulSoup is None:
            raise RuntimeError("beautifulsoup4 not installed — pip install beautifulsoup4")

        self.delay = delay
        self.cache_dir = cache_dir or CACHE_DIR
        self.timeout = timeout
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

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
        return f"{path}_{query}.html" if query else f"{path}.html"

    def get_countries(self) -> List[Dict[str, str]]:
        """Get list of countries from the SportyBet sidebar (Nigeria site)."""
        html = self._get(f"{BASE_URL}/ng/sport/football")
        soup = BeautifulSoup(html, "html.parser")

        countries = []
        # SportyBet sidebar: country links have data-country attribute
        for link in soup.select("a[data-country]"):
            country_name = link.get("data-country") or link.get_text(strip=True)
            href = link.get("href", "")
            if href:
                countries.append({"name": country_name, "url": urljoin(BASE_URL, href)})
        return countries

    def get_leagues(self, country_url: str) -> List[Dict[str, str]]:
        """Get leagues for a given country page."""
        html = self._get(country_url)
        soup = BeautifulSoup(html, "html.parser")

        leagues = []
        # League links typically in a sub-menu or accordion
        for link in soup.select("a[data-league], a[href*='/sport/football/']"):
            league_name = link.get("data-league") or link.get_text(strip=True)
            href = link.get("href", "")
            if href and "/sport/football/" in href:
                leagues.append({"name": league_name, "url": urljoin(BASE_URL, href)})
        return leagues

    def get_fixtures(self, league_url: str, days_ahead: int = 3) -> List[Fixture]:
        """Get fixtures for a league page within days_ahead."""
        html = self._get(league_url)
        soup = BeautifulSoup(html, "html.parser")

        fixtures = []
        # Fixture rows — SportyBet uses various structures, try multiple selectors
        for row in soup.select(".match-row, .fixture-row, [data-match-id], .event-row"):
            fixture = self._parse_fixture_row(row, league_url)
            if fixture:
                fixtures.append(fixture)

        # Fallback: look for JSON data embedded in the page
        if not fixtures:
            fixtures = self._extract_fixtures_from_json(html, league_url)

        return fixtures

    def _parse_fixture_row(self, row: BeautifulSoup, league_url: str) -> Optional[Fixture]:
        """Parse a fixture from a DOM row element."""
        try:
            # Match ID
            fixture_id = (
                row.get("data-match-id")
                or row.get("data-fixture-id")
                or row.get("data-event-id")
            )
            if not fixture_id:
                # Try to extract from a link
                link = row.select_one("a[href*='/match/'], a[href*='/event/']")
                if link:
                    href = link.get("href", "")
                    match = re.search(r"/(match|event)/(\d+)", href)
                    if match:
                        fixture_id = match.group(2)

            if not fixture_id:
                return None

            # Team names
            home_elem = row.select_one(".home-team, .team-home, [data-home-team], .team-name:first-child")
            away_elem = row.select_one(".away-team, .team-away, [data-away-team], .team-name:last-child")
            home_team = home_elem.get_text(strip=True) if home_elem else ""
            away_team = away_elem.get_text(strip=True) if away_elem else ""

            if not home_team or not away_team:
                # Try alternative: both teams in one element
                teams_elem = row.select_one(".teams, .match-teams, .event-teams")
                if teams_elem:
                    text = teams_elem.get_text(strip=True)
                    parts = re.split(r"\s+[–v]\s+", text, maxsplit=1)
                    if len(parts) == 2:
                        home_team, away_team = parts

            # Kickoff time
            kickoff_utc = ""
            time_elem = row.select_one(".match-time, .kickoff-time, [data-kickoff], .time")
            if time_elem:
                # Could be data attribute or text
                kickoff_utc = time_elem.get("data-kickoff") or time_elem.get_text(strip=True)

            # League/Country from URL
            parsed = urlparse(league_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            country = path_parts[1] if len(path_parts) > 1 else ""
            league = path_parts[2] if len(path_parts) > 2 else ""

            return Fixture(
                fixture_id=fixture_id,
                home_team=home_team,
                away_team=away_team,
                kickoff_utc=kickoff_utc,
                league=league,
                country=country,
                raw={"html": str(row)[:500]},
            )
        except Exception:
            return None

    def _extract_fixtures_from_json(self, html: str, league_url: str) -> List[Fixture]:
        """Extract fixtures from embedded JSON in the page."""
        fixtures = []
        # Look for __NEXT_DATA__ or similar
        for script in BeautifulSoup(html, "html.parser").select("script[type='application/json'], script#__NEXT_DATA__"):
            try:
                data = json.loads(script.string)
                fixtures.extend(self._parse_next_data(data, league_url))
            except (json.JSONDecodeError, AttributeError):
                continue
        return fixtures

    def _parse_next_data(self, data: Dict, league_url: str) -> List[Fixture]:
        """Parse fixtures from Next.js __NEXT_DATA__."""
        fixtures = []
        # Navigate to pageProps -> initialState -> matches or similar
        try:
            page_props = data.get("props", {}).get("pageProps", {})
            initial_state = page_props.get("initialState", {})
            matches = initial_state.get("matches", {}).get("data", {}) or initial_state.get("fixtures", {})

            for match_id, match in matches.items():
                if isinstance(match, dict):
                    fixtures.append(Fixture(
                        fixture_id=str(match_id),
                        home_team=match.get("homeTeam", {}).get("name", ""),
                        away_team=match.get("awayTeam", {}).get("name", ""),
                        kickoff_utc=match.get("startTime", ""),
                        league=match.get("tournament", {}).get("name", ""),
                        country=match.get("tournament", {}).get("category", {}).get("name", ""),
                        raw=match,
                    ))
        except Exception:
            pass
        return fixtures

    def get_odds(self, fixture_id: str) -> List[MarketOdds]:
        """Get odds for a specific fixture."""
        # Fixture detail page
        url = f"{BASE_URL}/match/{fixture_id}"
        html = self._get(url, cache_ttl=ODDS_CACHE_TTL)
        soup = BeautifulSoup(html, "html.parser")

        markets = []

        # Try to extract from embedded JSON first
        for script in soup.select("script[type='application/json'], script#__NEXT_DATA__"):
            try:
                data = json.loads(script.string)
                markets.extend(self._parse_odds_from_json(data, fixture_id))
            except (json.JSONDecodeError, AttributeError):
                continue

        # Fallback: parse from DOM
        if not markets:
            markets = self._parse_odds_from_dom(soup, fixture_id)

        return markets

    def _parse_odds_from_json(self, data: Dict, fixture_id: str) -> List[MarketOdds]:
        """Parse odds from embedded JSON."""
        markets = []
        try:
            page_props = data.get("props", {}).get("pageProps", {})
            initial_state = page_props.get("initialState", {})
            match_odds = initial_state.get("matchOdds", {}).get("data", {}).get(fixture_id, {})

            for market_key, market_data in match_odds.items():
                outcomes = {}
                for outcome in market_data.get("outcomes", []):
                    name = outcome.get("name", "")
                    price = outcome.get("price")
                    if price:
                        outcomes[name] = float(price)
                if outcomes:
                    # Normalize market key to OLP XDV canonical keys
                    canonical_key = self._normalize_market_key(market_key)
                    markets.append(MarketOdds(
                        fixture_id=fixture_id,
                        market=canonical_key,
                        outcomes=outcomes,
                        captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    ))
        except Exception:
            pass
        return markets

    def _parse_odds_from_dom(self, soup: BeautifulSoup, fixture_id: str) -> List[MarketOdds]:
        """Parse odds from DOM elements."""
        markets = []
        # Market tabs/sections
        for market_section in soup.select(".market-group, .odds-market, [data-market]"):
            market_name_elem = market_section.get("data-market") or market_section.select_one(".market-name, .tab-title")
            market_name = market_name_elem.get_text(strip=True) if market_name_elem else "unknown"

            outcomes = {}
            for outcome_elem in market_section.select(".outcome, .odds-item, [data-outcome]"):
                name = outcome_elem.get("data-outcome") or outcome_elem.select_one(".outcome-name, .name")
                price_elem = outcome_elem.select_one(".odds-value, .price, [data-price]")
                if name and price_elem:
                    name = name.get_text(strip=True) if hasattr(name, "get_text") else str(name)
                    price_text = price_elem.get("data-price") or price_elem.get_text(strip=True)
                    try:
                        price = float(price_text)
                        outcomes[name] = price
                    except ValueError:
                        continue

            if outcomes:
                # Normalize market key
                canonical_key = self._normalize_market_key(market_name)
                markets.append(MarketOdds(
                    fixture_id=fixture_id,
                    market=canonical_key,
                    outcomes=outcomes,
                    captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ))
        return markets

    def _normalize_market_key(self, sportybet_key: str) -> str:
        """Map SportyBet market key to OLP XDV canonical key."""
        mapping = {
            # 1X2
            "1X2": "1X2_HOME",  # will be distinguished by outcome names
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
        return mapping.get(sportybet_key.lower().replace(" ", "_"), sportybet_key)

    def _parse_odds_from_dom(self, soup: BeautifulSoup, fixture_id: str) -> List[MarketOdds]:
        """Parse odds from DOM elements."""
        markets = []
        # Market tabs/sections
        for market_section in soup.select(".market-group, .odds-market, [data-market]"):
            market_name_elem = market_section.get("data-market") or market_section.select_one(".market-name, .tab-title")
            market_name = market_name_elem.get_text(strip=True) if market_name_elem else "unknown"

            outcomes = {}
            for outcome_elem in market_section.select(".outcome, .odds-item, [data-outcome]"):
                name = outcome_elem.get("data-outcome") or outcome_elem.select_one(".outcome-name, .name")
                price_elem = outcome_elem.select_one(".odds-value, .price, [data-price]")
                if name and price_elem:
                    name = name.get_text(strip=True) if hasattr(name, "get_text") else str(name)
                    price_text = price_elem.get("data-price") or price_elem.get_text(strip=True)
                    try:
                        price = float(price_text)
                        outcomes[name] = price
                    except ValueError:
                        continue

            if outcomes:
                # Normalize market key
                canonical_key = self._normalize_market_key(market_name)
                markets.append(MarketOdds(
                    fixture_id=fixture_id,
                    market=canonical_key,
                    outcomes=outcomes,
                    captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ))
        return markets

    def close(self) -> None:
        """Close the session."""
        self.session.close()

    def __enter__(self) -> "SportyBetClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()