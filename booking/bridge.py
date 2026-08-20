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
  Phase 3 live — capital authority is the Architect's. This module NEVER
  places bets. It only reads and verifies.
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
    over15_odds: Optional[float] = None
    under15_odds: Optional[float] = None
    over35_odds: Optional[float] = None
    under35_odds: Optional[float] = None
    over05_odds: Optional[float] = None
    under05_odds: Optional[float] = None
    # BTTS
    btts_yes_odds: Optional[float] = None
    btts_no_odds: Optional[float] = None
    # Double Chance
    dc_1x_odds: Optional[float] = None
    dc_x2_odds: Optional[float] = None
    dc_12_odds: Optional[float] = None
    # Draw No Bet
    dnb_home_odds: Optional[float] = None
    dnb_away_odds: Optional[float] = None
    # HT/FT
    htft_11_odds: Optional[float] = None
    htft_1x_odds: Optional[float] = None
    htft_12_odds: Optional[float] = None
    htft_x1_odds: Optional[float] = None
    htft_xx_odds: Optional[float] = None
    htft_x2_odds: Optional[float] = None
    htft_21_odds: Optional[float] = None
    htft_2x_odds: Optional[float] = None
    htft_22_odds: Optional[float] = None
    # Correct Score
    cs_10_odds: Optional[float] = None
    cs_01_odds: Optional[float] = None
    cs_11_odds: Optional[float] = None
    cs_20_odds: Optional[float] = None
    cs_02_odds: Optional[float] = None
    cs_21_odds: Optional[float] = None
    cs_12_odds: Optional[float] = None
    cs_22_odds: Optional[float] = None
    cs_00_odds: Optional[float] = None
    cs_30_odds: Optional[float] = None
    cs_03_odds: Optional[float] = None
    cs_31_odds: Optional[float] = None
    cs_13_odds: Optional[float] = None
    # Metadata
    source: str = "sportybet"
    captured_at: Optional[str] = None
    bookmaker: str = "SportyBet Nigeria"


# OLP XDV name -> SportyBet cache key aliases.
# The cache was built under SportyBet sidebar names (e.g., "Eliteserien.json"),
# but the orchestrator calls with OLP names (e.g., "Norwegian Eliteserien").
# This map resolves the OLP name to the actual cache filename.
SPORTYBET_CACHE_ALIASES: dict[str, str] = {
    "Norwegian Eliteserien": "Eliteserien",
    "Turkish Super Lig":     "Süper Lig",
    "Greek Super League":    "Super League Greece",
    "Swedish Allsvenskan":   "Allsvenskan",
}


def _league_key(league: str) -> str:
    # Resolve OLP name -> cache key via alias map, then filesystem-safe
    cache_key = SPORTYBET_CACHE_ALIASES.get(league, league)
    return cache_key.replace(" ", "_").replace("/", "_")


def _cache_path(league: str) -> Path:
    return CACHE_DIR / f"{_league_key(league)}.json"


def _odds_cache_path(fixture_id: str) -> Path:
    return ODDS_CACHE_DIR / f"{fixture_id}.json"


def load_sportybet_fixtures(
    olp_league: str,
    days_ahead: int = 3,
    max_age_hours: int = 24,
) -> List[PipelineFixture]:
    """Load fixtures from SportyBet cache for an OLP XDV league.

    Args:
        olp_league: OLP XDV league name (e.g., "Premier League")
        days_ahead: How many days ahead to include
        max_age_hours: Maximum cache age in hours.

    Default is 24h, NOT 6h (was 6h until 2026-08-11): a 6h window meant any
    daily run more than ~6h after the last cache build lost EVERY league's
    prices at once — the board showed the fixtures (the orchestrator's fixture
    fallback already read 48h) but the price join (`get_sportybet_odds_for_leg`)
    and the booking-code driver both used this default and silently returned
    "fixture not found in SportyBet cache". The cached 1X2 snapshot is a
    same-day reference: the booking driver re-reads the LIVE price at booking
    time and CLV grades on the closing line, so a 24h window is honest and
    keeps today's fixtures priceable all day (HR35 — a real snapshot, just
    not a live one).

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
        mk = market.market
        outcomes = market.outcomes

        # 1X2
        if mk in ("1X2", "match_winner", "full_time_result", "1X2_HOME"):
            odds.home_odds = outcomes.get("1") or outcomes.get("Home") or outcomes.get("Home Win")
            odds.draw_odds = outcomes.get("X") or outcomes.get("Draw")
            odds.away_odds = outcomes.get("2") or outcomes.get("Away") or outcomes.get("Away Win")
        # Totals 1.5
        elif mk in ("OVER_1_5", "over_under_1_5", "OVER_UNDER_1.5"):
            odds.over15_odds = outcomes.get("Over") or outcomes.get("Over 1.5")
            odds.under15_odds = outcomes.get("Under") or outcomes.get("Under 1.5")
        # Totals 2.5
        elif mk in ("OVER_2_5", "over_under_2_5", "OVER_UNDER_2.5", "totals_2.5"):
            odds.over25_odds = outcomes.get("Over") or outcomes.get("Over 2.5")
            odds.under25_odds = outcomes.get("Under") or outcomes.get("Under 2.5")
        # Totals 3.5
        elif mk in ("OVER_3_5", "over_under_3_5", "OVER_UNDER_3.5"):
            odds.over35_odds = outcomes.get("Over") or outcomes.get("Over 3.5")
            odds.under35_odds = outcomes.get("Under") or outcomes.get("Under 3.5")
        # Totals 0.5
        elif mk in ("OVER_0_5", "over_under_0_5", "OVER_UNDER_0.5"):
            odds.over05_odds = outcomes.get("Over") or outcomes.get("Over 0.5")
            odds.under05_odds = outcomes.get("Under") or outcomes.get("Under 0.5")
        # BTTS
        elif mk in ("BTTS_YES", "both_teams_to_score", "btts", "gg_ng"):
            odds.btts_yes_odds = outcomes.get("Yes") or outcomes.get("GG") or outcomes.get("Both Teams To Score")
            odds.btts_no_odds = outcomes.get("No") or outcomes.get("NG") or outcomes.get("No Goal")
        # Double Chance
        elif mk in ("DC_1X", "double_chance"):
            odds.dc_1x_odds = outcomes.get("1X") or outcomes.get("Home or Draw")
            odds.dc_x2_odds = outcomes.get("X2") or outcomes.get("Draw or Away")
            odds.dc_12_odds = outcomes.get("12") or outcomes.get("Home or Away")
        # Draw No Bet
        elif mk in ("DNB_HOME", "draw_no_bet", "dnb"):
            odds.dnb_home_odds = outcomes.get("1") or outcomes.get("Home") or outcomes.get("Home DNB")
            odds.dnb_away_odds = outcomes.get("2") or outcomes.get("Away") or outcomes.get("Away DNB")
        # HT/FT
        elif mk in ("HT_FT_11", "half_time_full_time", "ht_ft"):
            odds.htft_11_odds = outcomes.get("1/1") or outcomes.get("Home/Home")
            odds.htft_1x_odds = outcomes.get("1/X") or outcomes.get("Home/Draw")
            odds.htft_12_odds = outcomes.get("1/2") or outcomes.get("Home/Away")
            odds.htft_x1_odds = outcomes.get("X/1") or outcomes.get("Draw/Home")
            odds.htft_xx_odds = outcomes.get("X/X") or outcomes.get("Draw/Draw")
            odds.htft_x2_odds = outcomes.get("X/2") or outcomes.get("Draw/Away")
            odds.htft_21_odds = outcomes.get("2/1") or outcomes.get("Away/Home")
            odds.htft_2x_odds = outcomes.get("2/X") or outcomes.get("Away/Draw")
            odds.htft_22_odds = outcomes.get("2/2") or outcomes.get("Away/Away")
        # Correct Score
        elif mk in ("CS_10", "correct_score", "exact_score"):
            odds.cs_10_odds = outcomes.get("1:0") or outcomes.get("1-0")
            odds.cs_01_odds = outcomes.get("0:1") or outcomes.get("0-1")
            odds.cs_11_odds = outcomes.get("1:1") or outcomes.get("1-1")
            odds.cs_20_odds = outcomes.get("2:0") or outcomes.get("2-0")
            odds.cs_02_odds = outcomes.get("0:2") or outcomes.get("0-2")
            odds.cs_21_odds = outcomes.get("2:1") or outcomes.get("2-1")
            odds.cs_12_odds = outcomes.get("1:2") or outcomes.get("1-2")
            odds.cs_22_odds = outcomes.get("2:2") or outcomes.get("2-2")
            odds.cs_00_odds = outcomes.get("0:0") or outcomes.get("0-0")
            odds.cs_30_odds = outcomes.get("3:0") or outcomes.get("3-0")
            odds.cs_03_odds = outcomes.get("0:3") or outcomes.get("0-3")
            odds.cs_31_odds = outcomes.get("3:1") or outcomes.get("3-1")
            odds.cs_13_odds = outcomes.get("1:3") or outcomes.get("1-3")

    # Write cache
    ODDS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "home_odds": odds.home_odds,
        "draw_odds": odds.draw_odds,
        "away_odds": odds.away_odds,
        "over15_odds": odds.over15_odds,
        "under15_odds": odds.under15_odds,
        "over25_odds": odds.over25_odds,
        "under25_odds": odds.under25_odds,
        "over35_odds": odds.over35_odds,
        "under35_odds": odds.under35_odds,
        "over05_odds": odds.over05_odds,
        "under05_odds": odds.under05_odds,
        "btts_yes_odds": odds.btts_yes_odds,
        "btts_no_odds": odds.btts_no_odds,
        "dc_1x_odds": odds.dc_1x_odds,
        "dc_x2_odds": odds.dc_x2_odds,
        "dc_12_odds": odds.dc_12_odds,
        "dnb_home_odds": odds.dnb_home_odds,
        "dnb_away_odds": odds.dnb_away_odds,
        "htft_11_odds": odds.htft_11_odds,
        "htft_1x_odds": odds.htft_1x_odds,
        "htft_12_odds": odds.htft_12_odds,
        "htft_x1_odds": odds.htft_x1_odds,
        "htft_xx_odds": odds.htft_xx_odds,
        "htft_x2_odds": odds.htft_x2_odds,
        "htft_21_odds": odds.htft_21_odds,
        "htft_2x_odds": odds.htft_2x_odds,
        "htft_22_odds": odds.htft_22_odds,
        "cs_10_odds": odds.cs_10_odds,
        "cs_01_odds": odds.cs_01_odds,
        "cs_11_odds": odds.cs_11_odds,
        "cs_20_odds": odds.cs_20_odds,
        "cs_02_odds": odds.cs_02_odds,
        "cs_21_odds": odds.cs_21_odds,
        "cs_12_odds": odds.cs_12_odds,
        "cs_22_odds": odds.cs_22_odds,
        "cs_00_odds": odds.cs_00_odds,
        "cs_30_odds": odds.cs_30_odds,
        "cs_03_odds": odds.cs_03_odds,
        "cs_31_odds": odds.cs_31_odds,
        "cs_13_odds": odds.cs_13_odds,
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
    market: str,  # "1X2_HOME", "1X2_DRAW", "1X2_AWAY", "OVER_2_5", "UNDER_2_5", etc.
    client: Optional[SportyBetClient] = None,
) -> Optional[float]:
    """Get SportyBet odds for a specific leg/market.

    Returns the decimal odds if available, None otherwise. This reads the
    cached fixture list (no live call), so `client` is accepted for call
    compatibility but never used — no session is opened.

    Matching (all EXACT / normalized-exact only — HR35, never a fuzzy guess
    across clubs):
      1. Exact model-key match — PipelineFixture.home_team/away_team are the
         cache's model keys, the same football-data names the orchestrator
         passes in.
      2. Normalized model-key match — case/diacritics/prefix stripped via
         team_map._normalize. A cached model key can still differ from the
         board key by a diacritic or prefix ("Fenerbahce" vs "Fenerbahçe",
         "SK Sturm Graz" vs "Sturm Graz"); this pass is what prices the leg
         instead of silently no-matching.
      3. SportyBet-name match — the board key resolved to its SportyBet
         spelling (resolve_team) compared against the cache's RAW
         sportybet_home/away, the most trustworthy name in the cache.
    """
    fixtures = load_sportybet_fixtures(olp_league, days_ahead=45)

    def _price(fx) -> Optional[float]:
        # 1X2
        if market == "1X2_HOME":
            return fx.home_odds
        if market == "1X2_DRAW":
            return fx.draw_odds
        if market == "1X2_AWAY":
            return fx.away_odds
        # Totals
        if market == "OVER_1_5":
            return fx.over15_odds
        if market == "UNDER_1_5":
            return fx.under15_odds
        if market == "OVER_2_5":
            return fx.over25_odds
        if market == "UNDER_2_5":
            return fx.under25_odds
        if market == "OVER_3_5":
            return fx.over35_odds
        if market == "UNDER_3_5":
            return fx.under35_odds
        if market == "OVER_0_5":
            return fx.over05_odds
        if market == "UNDER_0_5":
            return fx.under05_odds
        # BTTS
        if market == "BTTS_YES":
            return fx.btts_yes_odds
        if market == "BTTS_NO":
            return fx.btts_no_odds
        # Double Chance
        if market == "DC_1X":
            return fx.dc_1x_odds
        if market == "DC_X2":
            return fx.dc_x2_odds
        if market == "DC_12":
            return fx.dc_12_odds
        # Draw No Bet
        if market == "DNB_HOME":
            return fx.dnb_home_odds
        if market == "DNB_AWAY":
            return fx.dnb_away_odds
        # HT/FT
        if market == "HT_FT_11":
            return fx.htft_11_odds
        if market == "HT_FT_1X":
            return fx.htft_1x_odds
        if market == "HT_FT_12":
            return fx.htft_12_odds
        if market == "HT_FT_X1":
            return fx.htft_x1_odds
        if market == "HT_FT_XX":
            return fx.htft_xx_odds
        if market == "HT_FT_X2":
            return fx.htft_x2_odds
        if market == "HT_FT_21":
            return fx.htft_21_odds
        if market == "HT_FT_2X":
            return fx.htft_2x_odds
        if market == "HT_FT_22":
            return fx.htft_22_odds
        # Correct Score
        if market == "CS_10":
            return fx.cs_10_odds
        if market == "CS_01":
            return fx.cs_01_odds
        if market == "CS_11":
            return fx.cs_11_odds
        if market == "CS_20":
            return fx.cs_20_odds
        if market == "CS_02":
            return fx.cs_02_odds
        if market == "CS_21":
            return fx.cs_21_odds
        if market == "CS_12":
            return fx.cs_12_odds
        if market == "CS_22":
            return fx.cs_22_odds
        if market == "CS_00":
            return fx.cs_00_odds
        if market == "CS_30":
            return fx.cs_30_odds
        if market == "CS_03":
            return fx.cs_03_odds
        if market == "CS_31":
            return fx.cs_31_odds
        if market == "CS_13":
            return fx.cs_13_odds
        # Unknown market
        return None

    # 1. Exact model-key match.
    for fx in fixtures:
        if fx.home_team == home_team and fx.away_team == away_team:
            return _price(fx)

    # 2. Normalized model-key match.
    try:
        from booking.team_map import _normalize
        nh, na = _normalize(home_team), _normalize(away_team)
        for fx in fixtures:
            if (_normalize(fx.home_team) == nh
                    and _normalize(fx.away_team) == na):
                return _price(fx)
    except Exception:
        pass

    # 3. SportyBet-name match (raw cache names).
    try:
        from booking.team_map import resolve_team, _normalize
        sh = _normalize(resolve_team(home_team, "sportybet"))
        sa = _normalize(resolve_team(away_team, "sportybet"))
        for fx in fixtures:
            if (_normalize(fx.sportybet_home or "") == sh
                    and _normalize(fx.sportybet_away or "") == sa):
                return _price(fx)
    except Exception:
        pass

    return None


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