"""
Booking bridge — connects SportyBet cache to OLP XDV pipeline.

This module bridges the booking system (SportyBet client + cache builder)
with the OLP XDV daily pipeline. It provides functions to:

1. Load fixtures from the SportyBet cache into the pipeline's fixture format
2. Attach SportyBet odds to board fixtures for EV calculation
3. Verify fixture availability on SportyBet before logging paper legs

WHY THIS EXISTS
  The OLP XDV pipeline uses TheSportsDB and The Odds API for fixtures/odds.
  SportyBet is where the Architect actually places bets (Nigeria). This bridge
  ensures the paper log uses SportyBet prices for CLV calculation, and that
  fixtures logged as paper legs actually exist on SportyBet.

USAGE
  from booking.bridge import load_sportybet_fixtures, attach_sportybet_odds, verify_fixture_on_sportybet

  # In run_daily.py scan_one_league:
  fixtures = load_sportybet_fixtures("Premier League", days_ahead=3)

  # In odds attach loop:
  board = attach_sportybet_odds(board, client)

  # Before logging a leg:
  if not verify_fixture_on_sportybet(home, away, league):
      log.warning("Fixture not on SportyBet — skipping paper leg")

DEPLOY GATE
  Phase 2 = paper only. This module NEVER places bets. It only reads and verifies.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import date, timedelta

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.league_map import SPORTYBET_LEAGUES, BookmakerLeague, resolve_bookmaker
from booking.team_map import resolve_team
from booking.sportybet_client import SportyBetClient, Fixture as SBFixture, MarketOdds


# --- Cache paths ---
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"
ODDS_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "odds"


@dataclass
class PipelineFixture:
    """A fixture in the pipeline's internal format."""
    home_team: str          # Model key (football-data.co.uk short name)
    away_team: str          # Model key
    kickoff_utc: str        # ISO format
    league: str             # OLP XDV league name
    sportybet_fixture_id: Optional[str] = None  # SportyBet's match ID
    sportybet_home: Optional[str] = None        # SportyBet official home name
    sportybet_away: Optional[str] = None        # SportyBet official away name
    country: Optional[str] = None               # SportyBet country
    # 1X2 odds captured with the cache (None = not readable — HR35).
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None


@dataclass
class FixtureOdds:
    """Odds attached to a pipeline fixture."""
    home_team: str
    away_team: str
    league: str
    kickoff_utc: str
    # 1X2
    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    # Totals
    over25_odds: Optional[float] = None
    under25_odds: Optional[float] = None
    # Metadata
    source: str = "sportybet"
    captured_at: Optional[str] = None
    bookmaker: str = "SportyBet Nigeria"


def _league_key(league: str) -> str:
    return league.replace(" ", "_").replace("/", "_")


def _cache_path(league: str) -> Path:
    return CACHE_DIR / f"{_league_key(league)}.json"


def _odds_cache_path(fixture_id: str) -> Path:
    return ODDS_CACHE_DIR / f"{fixture_id}.json"


def load_sportybet_fixtures(
    olp_league: str,
    days_ahead: int = 3,
    max_age_hours: int = 6,
) -> List[PipelineFixture]:
    """Load fixtures from SportyBet cache for an OLP XDV league.

    Args:
        olp_league: OLP XDV league name (e.g., "Premier League")
        days_ahead: How many days ahead to include
        max_age_hours: Maximum cache age in hours

    Returns:
        List of PipelineFixture objects ready for the pipeline.
    """
    # Check if league is mapped
    mapping = SPORTYBET_LEAGUES.get(olp_league)
    if not mapping:
        return []

    # Read cache
    path = _cache_path(olp_league)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    # Check cache age
    age_hours = (time.time() - data.get("fetched_at", 0)) / 3600
    if age_hours > max_age_hours:
        return []

    # Filter by date
    cutoff = date.today() + timedelta(days=days_ahead)
    fixtures = []

    for fx_data in data.get("fixtures", []):
        kickoff = fx_data.get("kickoff_utc", "")
        if kickoff:
            try:
                kickoff_date = date.fromisoformat(kickoff[:10])
                if kickoff_date > cutoff:
                    continue
            except ValueError:
                pass  # Include if date unparseable

        fixtures.append(PipelineFixture(
            home_team=fx_data.get("model_home", ""),
            away_team=fx_data.get("model_away", ""),
            kickoff_utc=kickoff,
            league=olp_league,
            sportybet_fixture_id=fx_data.get("fixture_id"),
            sportybet_home=fx_data.get("sportybet_home"),
            sportybet_away=fx_data.get("sportybet_away"),
            country=mapping.country,
            home_odds=fx_data.get("home_odds"),
            draw_odds=fx_data.get("draw_odds"),
            away_odds=fx_data.get("away_odds"),
        ))

    return fixtures


def load_all_sportybet_fixtures(
    days_ahead: int = 3,
    leagues: Optional[List[str]] = None,
) -> Dict[str, List[PipelineFixture]]:
    """Load fixtures for all mapped leagues (or specified subset)."""
    target_leagues = leagues or list(SPORTYBET_LEAGUES.keys())
    result = {}
    for league in target_leagues:
        fixtures = load_sportybet_fixtures(league, days_ahead)
        if fixtures:
            result[league] = fixtures
    return result


def attach_sportybet_odds(
    board_fixtures: List[Any],  # BoardFixture from orchestrator
    client: Optional[SportyBetClient] = None,
    use_cache: bool = True,
    cache_ttl_seconds: int = 60,
) -> List[Any]:
    """Attach SportyBet odds to board fixtures for EV calculation.

    Modifies board fixtures in place by adding .sportybet_odds attribute.
    Returns the same list for chaining.

    Args:
        board_fixtures: List of BoardFixture objects from orchestrator
        client: SportyBetClient instance (created if not provided)
        use_cache: Whether to use cached odds
        cache_ttl_seconds: Cache TTL for odds (default 60s)

    Returns:
        The same board_fixtures list with odds attached.
    """
    if client is None:
        client = SportyBetClient()

    try:
        for bf in board_fixtures:
            if not hasattr(bf, 'sportybet_fixture_id') or not bf.sportybet_fixture_id:
                # Try to find fixture ID by matching teams
                fixture_id = _find_fixture_id(bf, client)
                if fixture_id:
                    bf.sportybet_fixture_id = fixture_id

            if bf.sportybet_fixture_id:
                odds = _get_fixture_odds(bf.sportybet_fixture_id, client, use_cache, cache_ttl_seconds)
                if odds:
                    bf.sportybet_odds = odds
    finally:
        if client:
            client.close()

    return board_fixtures


def _find_fixture_id(bf: Any, client: SportyBetClient) -> Optional[str]:
    """Find SportyBet fixture ID by matching team names."""
    # This would require searching SportyBet - for now return None
    # The fixture ID should be set during fixture loading
    return None


def _get_fixture_odds(
    fixture_id: str,
    client: SportyBetClient,
    use_cache: bool,
    cache_ttl: int,
) -> Optional[FixtureOdds]:
    """Get odds for a fixture, with caching."""
    # Check cache first
    cache_path = _odds_cache_path(fixture_id)
    if use_cache and cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < cache_ttl:
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                return FixtureOdds(**data)
            except Exception:
                pass

    # Fetch live
    markets = client.get_odds(fixture_id)
    if not markets:
        return None

    # Parse markets into FixtureOdds
    odds = FixtureOdds(
        home_team="",  # Will be filled by caller
        away_team="",
        league="",
        kickoff_utc="",
        captured_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    for market in markets:
        if market.market in ("1X2", "match_winner", "full_time_result"):
            odds.home_odds = market.outcomes.get("1") or market.outcomes.get("Home")
            odds.draw_odds = market.outcomes.get("X") or market.outcomes.get("Draw")
            odds.away_odds = market.outcomes.get("2") or market.outcomes.get("Away")
        elif market.market in ("OVER_UNDER_2.5", "totals_2.5", "over_under_2.5"):
            odds.over25_odds = market.outcomes.get("Over") or market.outcomes.get("Over 2.5")
            odds.under25_odds = market.outcomes.get("Under") or market.outcomes.get("Under 2.5")

    # Write cache
    ODDS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "home_odds": odds.home_odds,
        "draw_odds": odds.draw_odds,
        "away_odds": odds.away_odds,
        "over25_odds": odds.over25_odds,
        "under25_odds": odds.under25_odds,
        "source": odds.source,
        "captured_at": odds.captured_at,
        "bookmaker": odds.bookmaker,
    }
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    return odds


def verify_fixture_on_sportybet(
    home_team: str,
    away_team: str,
    olp_league: str,
    client: Optional[SportyBetClient] = None,
) -> bool:
    """Verify that a fixture exists on SportyBet for the given league.

    Used before logging a paper leg to ensure the leg can actually be placed.

    Args:
        home_team: Model key home team name
        away_team: Model key away team name
        olp_league: OLP XDV league name
        client: SportyBetClient instance (created if not provided)

    Returns:
        True if fixture found on SportyBet, False otherwise.
    """
    if client is None:
        client = SportyBetClient()

    try:
        fixtures = load_sportybet_fixtures(olp_league, days_ahead=7)
        # Map model names to SportyBet names for comparison
        sb_home = resolve_team(home_team, "sportybet")
        sb_away = resolve_team(away_team, "sportybet")

        for fx in fixtures:
            if (fx.model_home == home_team and fx.model_away == away_team) or \
               (fx.sportybet_home == sb_home and fx.sportybet_away == sb_away):
                return True
        return False
    finally:
        if client:
            client.close()


def get_sportybet_odds_for_leg(
    home_team: str,
    away_team: str,
    olp_league: str,
    market: str,  # "1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_2_5", "UNDER_2_5"
    client: Optional[SportyBetClient] = None,
) -> Optional[float]:
    """Get SportyBet odds for a specific leg/market.

    Returns the decimal odds if available, None otherwise.
    """
    if client is None:
        client = SportyBetClient()

    try:
        fixtures = load_sportybet_fixtures(olp_league, days_ahead=45)

        # Match on MODEL keys — PipelineFixture.home_team/away_team are the
        # football-data short names, the same keys the orchestrator passes in.
        for fx in fixtures:
            if fx.home_team == home_team and fx.away_team == away_team:
                if market == "1X2_HOME":
                    return fx.home_odds
                elif market == "1X2_DRAW":
                    return fx.draw_odds
                elif market == "1X2_AWAY":
                    return fx.away_odds
                # Totals markets are NOT captured from the league page (the
                # line is a variable selector, not fixed 2.5) — honest None.
                return None
        return None
    finally:
        if client:
            client.close()


def sportybet_fixtures_to_pairs(
    olp_league: str,
    days_ahead: int = 3,
    max_age_hours: int = 6,
) -> List[Tuple[str, str]]:
    """Convert SportyBet fixtures to (home, away) pairs for the pipeline.

    Returns pairs in model key format, ready for scan_one_league.
    """
    fixtures = load_sportybet_fixtures(olp_league, days_ahead, max_age_hours)
    return [(fx.home_team, fx.away_team) for fx in fixtures if fx.home_team and fx.away_team]


def refresh_sportybet_cache(
    leagues: Optional[List[str]] = None,
    days_ahead: int = 7,
) -> Dict[str, int]:
    """Trigger a cache refresh using the Playwright cache builder.

    This is a convenience wrapper that calls the cache builder module.
    """
    from booking.sportybet_fixtures import build_cache
    return build_cache(leagues=leagues, days_ahead=days_ahead)


# --- Integration helpers for run_daily.py ---

def get_deploy_leagues_fixtures(days_ahead: int = 3) -> Dict[str, List[PipelineFixture]]:
    """Get fixtures for all deploy-eligible leagues (the unified pool)."""
    from engine.leagues import WHITELISTED_LEAGUES
    return load_all_sportybet_fixtures(days_ahead, WHITELISTED_LEAGUES)


def get_scan_leagues_fixtures(days_ahead: int = 3) -> Dict[str, List[PipelineFixture]]:
    """Get fixtures for all scan leagues."""
    from run_daily import SCAN_LEAGUES
    return load_all_sportybet_fixtures(days_ahead, SCAN_LEAGUES)