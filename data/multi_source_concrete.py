"""
Concrete multi-source implementations for all pipeline data types.

Each data type gets multiple redundant providers with automatic failover.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from data.multi_source import (
    DataSource, MultiSource, build_multi_source, registry, as_source,
    SourceNoData,
)
from data.football_data_source import load_league as fd_load_league
from data import thesportsdb_fixtures as tsdb
from data import espn_source
from data import api_football_results as apif
from data import football_data_org_source as fdo
from data import xg_source
from data import live_scores as ls
from pipeline.odds import fetch_odds as odds_fetch_odds, fixtures_from_odds as odds_fixtures_from_odds

# SportyBet imports for odds source
try:
    from booking.sportybet_client import SportyBetClient
    from booking.bridge import get_sportybet_odds_for_leg, load_sportybet_fixtures
    SPORTYBET_AVAILABLE = True
except ImportError:
    SPORTYBET_AVAILABLE = False

log = logging.getLogger("multi_source.concrete")

# =============================================================================
# FIXTURES MULTI-SOURCE
# =============================================================================

class TheSportsDBFixturesSource(DataSource):
    """TheSportsDB fixtures (season feed + eventsday fallback)."""

    def __init__(self):
        super().__init__("thesportsdb", priority=10, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        fixtures_season = kwargs.get("fixtures_season") or kwargs.get("season")
        days_ahead = kwargs.get("days_ahead", 14)
        from datetime import date
        # Try season feed first
        fixtures, skipped = tsdb.fetch_upcoming(league, fixtures_season, days_ahead=days_ahead)
        if fixtures:
            pairs = tsdb.as_pairs(fixtures)
            dates = {(f.home_team, f.away_team): f.date for f in fixtures}
            return {"fixtures": pairs, "dates": dates, "skipped": skipped, "source": "thesportsdb_season"}

        # If today is within the window and season feed is empty/lagging,
        # try eventsday for continental qualifiers (season feed lags weeks behind).
        # This catches CL/EL/ConfL qualifiers that the season feed hasn't indexed yet.
        from datetime import date
        today = str(date.today())
        day_fixtures = tsdb.fetch_today(league, today)
        if day_fixtures:
            pairs = tsdb.as_pairs(day_fixtures)
            dates = {(f.home_team, f.away_team): f.date for f in day_fixtures}
            return {"fixtures": pairs, "dates": dates, "skipped": 0, "source": "thesportsdb_eventsday"}

        # A legitimately-empty window is a valid answer for this league — fall
        # through to the next source WITHOUT tripping the shared circuit breaker.
        raise SourceNoData(f"thesportsdb: no fixtures for {league} (season={fixtures_season}, days={days_ahead})")


class OddsAPIFixturesSource(DataSource):
    """Fixtures derived from odds feed (last resort)."""

    def __init__(self):
        super().__init__("odds_api_fixtures", priority=20, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        days_ahead = kwargs.get("days_ahead", 14)
        pairs, dates, flags = odds_fixtures_from_odds(league, days_ahead=days_ahead)
        if not pairs:
            raise SourceNoData(f"odds_api: no fixtures for {league}")
        return {"fixtures": pairs, "dates": dates, "flags": flags, "source": "odds_api"}


class APIFootballFixturesSource(DataSource):
    """API-Football fixtures (paid plan only; free tier can't see current season)."""

    def __init__(self):
        super().__init__("api_football_fixtures", priority=15, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        # API-Football fixtures. The free tier CANNOT see the current season
        # (deterministic {'plan': ...} error, cached 7 days by the caller), so
        # this source honestly raises — it only becomes a real provider on a
        # paid plan. Wiring it here means the failover chain is complete: when
        # thesportsdb and the odds feed both fail, the paid-plan fallback is
        # already in place instead of a dead stub.
        league = kwargs["league"]
        season = kwargs.get("season") or kwargs.get("fixtures_season")
        season_year = kwargs.get("season_year") or kwargs.get("api_football_season")
        from data.fixtures_source import fetch_upcoming, as_pairs
        if season_year is None:
            try:
                season_year = (int(season[:2]) + 2000
                               if isinstance(season, str) and season.isdigit() else season)
            except Exception:
                season_year = None
        if season_year is None:
            raise SourceNoData(f"api_football: cannot resolve season {season!r} for {league}")
        fixtures = fetch_upcoming(league, season_year, days_ahead=kwargs.get("days_ahead", 14))
        if not fixtures:
            raise SourceNoData(f"api_football: no fixtures for {league} season {season_year}")
        pairs = as_pairs(fixtures)
        dates = {(f.home_team, f.away_team): f.date for f in fixtures}
        return {"fixtures": pairs, "dates": dates, "skipped": 0, "source": "api_football"}


class ESPNFixturesSource(DataSource):
    """ESPN scoreboard fixtures — key-free, covers continental comps + the
    no-TSDB-ID leagues (Austrian Bundesliga, HNL). Slice 1 of the ESPN
    redundancy layer (Architect order 2026-08-07)."""

    def __init__(self):
        super().__init__("espn", priority=15, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        fixtures_season = kwargs.get("fixtures_season") or kwargs.get("season")
        days_ahead = kwargs.get("days_ahead", 14)
        fixtures, skipped = espn_source.fetch_upcoming(
            league, fixtures_season, days_ahead=days_ahead)
        if not fixtures:
            raise SourceNoData(
                f"espn: no fixtures for {league} "
                f"(days={days_ahead}, skipped={len(skipped)})")
        pairs = espn_source.as_pairs(fixtures)
        dates = {(f.home_team, f.away_team): f.date for f in fixtures}
        return {"fixtures": pairs, "dates": dates, "skipped": skipped,
                "source": "espn"}


def build_fixtures_multi_source() -> MultiSource:
    """Build the fixtures multi-source with automatic failover.

    Order: API-Football (paid Pro primary; current season, widest window) ->
    TheSportsDB (season feed + eventsday fallback) -> ESPN scoreboard
    (key-free; covers continental + no-ID leagues) -> odds-derived fixtures.
    Each source's fetch is kwargs-tolerant so the shared MultiSource.fetch
    kwargs (league, season/fixtures_season, days_ahead) work for all of them.
    """
    return build_multi_source(
        "fixtures",
        [
            (APIFootballFixturesSource().fetch, "api_football_fixtures", 10),
            (TheSportsDBFixturesSource().fetch, "thesportsdb", 15),
            (ESPNFixturesSource().fetch, "espn", 20),
            (OddsAPIFixturesSource().fetch, "odds_api_fixtures", 30),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# HISTORICAL RESULTS MULTI-SOURCE
# =============================================================================

class FootballDataResultsSource(DataSource):
    """football-data.co.uk historical results (primary)."""

    def __init__(self):
        super().__init__("football_data", priority=10, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        season = kwargs.get("season") or kwargs.get("fixtures_season")
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise SourceNoData(f"football_data: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data"}


class FootballDataOrgResultsSource(DataSource):
    """football-data.org CURRENT-SEASON results — the P0 fix for promoted clubs.

    football-data.co.uk CSVs are end-of-season only; football-data.org serves
    live current-season results (updated daily). A promoted club (Cambuur,
    Beveren, Lommel, Horsens, etc.) becomes rateable through the existing DC
    machinery once it has ≥4 current-season matches — WITHOUT waiting for
    api-football paid activation. This source is keyless-ish (free registration),
    10 req/min, 100 req/day. Added 2026-08-12 as P0 gap fix."""

    def __init__(self):
        super().__init__("football_data_org", priority=12, timeout=30.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        # football-data.org provides CURRENT-SEASON results. The fit season
        # (e.g. '2526') is last season's data; the fixtures season ('2627')
        # is the current season with promoted clubs. Prefer fixtures_season.
        fixtures_season = kwargs.get("fixtures_season")
        season = kwargs.get("season")
        if fixtures_season and isinstance(fixtures_season, str) and len(fixtures_season) == 4 and fixtures_season.isdigit():
            # '2627' -> 2026 (football-data.org uses the start year)
            season_year = int(fixtures_season[:2]) + 2000
        elif isinstance(season, str) and len(season) == 4 and season.isdigit():
            # fallback: fit season '2526' -> 2025
            season_year = int(season[:2]) + 2000
        elif isinstance(season, int):
            season_year = season
        else:
            raise SourceNoData(f"football_data_org: cannot resolve season {season!r} for {league}")
        results, flags = fdo.fetch_current_season_results(league, season_year)
        if not results:
            raise SourceNoData(f"football_data_org: no results for {league} {season_year}")
        return {"results": results, "flags": flags, "source": "football_data_org"}


class APIFootballResultsSource(DataSource):
    """API-Football historical results (fallback for uncovered leagues)."""

    def __init__(self):
        super().__init__("api_football_results", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise SourceNoData(f"api_football_results: no results for {league} {season}")
        return {"results": results, "flags": flags, "source": "api_football_results"}


class TheSportsDBResultsSource(DataSource):
    """TheSportsDB historical results — last-resort history for leagues neither
    football-data nor API-Football can serve (HNL, Champions League, Europa
    League). Real current-season scores from the same feed that supplies the
    fixtures, so a rated fixture and its fit always agree on club names.

    Trust: this is SINGLE-SOURCE T2 reference data (ID404), never an
    F2-quorum VERIFIED second source — a model fitted here is usable for the
    board's reference scan, not calibration-grade."""

    def __init__(self):
        super().__init__("thesportsdb_results", priority=20, timeout=25.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        season = str(kwargs.get("season") or "")
        # The framework's season code is a two-year span ('2526' = 2025/26).
        # A bare year like '2025' would pass a length check but query the WRONG
        # TheSportsDB season (football-data and API-Football conventions differ),
        # so it is a contract error here, not something to guess — the caller
        # passes the framework code ('2526') explicitly.
        if len(season) != 4 or not season.isdigit():
            raise SourceNoData(
                f"thesportsdb_results: season {season!r} is not a '2526' code")
        if int(season[2:4]) != (int(season[:2]) + 1) % 100:
            raise SourceNoData(
                f"thesportsdb_results: season {season!r} is not a two-year span "
                f"code like '2526'")
        from data import thesportsdb_fixtures as tsdb
        results, skipped = tsdb.load_results(league, season)
        if not results:
            raise SourceNoData(f"thesportsdb_results: no results for {league} {season}")
        return {"results": results, "skipped": skipped,
                "source": "thesportsdb_results"}


def build_results_multi_source() -> MultiSource:
    """Build the historical results multi-source."""
    return build_multi_source(
        "historical_results",
        [
            (FootballDataResultsSource().fetch, "football_data", 10),
            (FootballDataOrgResultsSource().fetch, "football_data_org", 12),
            (APIFootballResultsSource().fetch, "api_football_results", 15),
            (TheSportsDBResultsSource().fetch, "thesportsdb_results", 20),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# CURRENT-SEASON RESULTS MULTI-SOURCE (T3 fallback for lower tiers)
# =============================================================================

class FlashScoreResultsSource(DataSource):
    """FlashScore completed match results — current-season coverage for 92 leagues.

    Scrapes FlashScore league results pages for completed matches.
    Provides T2 redundancy for current-season fixtures where T1/T2 sources
    (football-data.co.uk, ESPN) lack coverage. Priority 18 — runs after
    historical sources but before manual T3.
    """

    def __init__(self):
        super().__init__("flashscore_results", priority=18, timeout=45.0)

    def fetch(self, **kwargs) -> list:
        league = kwargs["league"]
        target_date = kwargs.get("target_date") or kwargs.get("date")
        if not target_date:
            raise SourceNoData(f"flashscore_results: target_date required for {league}")

        # Import the sync wrapper
        from data.flashscore_results import fetch_flashscore_results_sync

        results = fetch_flashscore_results_sync(league, target_date)
        if not results:
            raise SourceNoData(f"flashscore_results: no results for {league} {target_date}")

        return {"results": results, "source": "flashscore_results", "source_tier": "T2"}


# =============================================================================
# ODDS MULTI-SOURCE (multi-region, multi-market)
# =============================================================================

class OddsAPISource(DataSource):
    """The-Odds-API live prices."""

    def __init__(self, regions: str = "uk", markets: str = "h2h,totals"):
        super().__init__(f"odds_api_{regions}_{markets}", priority=10, timeout=30.0)
        self.regions = regions
        self.markets = markets

    def fetch(self, league: str) -> list:
        fixtures, flags = odds_fetch_odds(league, regions=self.regions, markets=self.markets)
        if not fixtures:
            raise SourceNoData(f"odds_api({self.regions}): no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": f"odds_api_{self.regions}"}


class APIFootballOddsSource(DataSource):
    """API-Football free-plan odds — the fallback when The Odds API quota is
    spent (same bookmakers, 1X2 + totals, 100 req/day)."""

    def __init__(self):
        super().__init__("api_football_odds", priority=20, timeout=60.0)

    def fetch(self, league: str) -> list:
        from data.api_football_odds import fetch_odds as af_fetch
        fixtures, flags = af_fetch(league)
        if not fixtures:
            raise SourceNoData(f"api_football_odds: no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": "api_football_odds"}


class SportyBetOddsSource(DataSource):
    """SportyBet Nigeria odds via internal factsCenter API.

    This is the Architect's primary betting venue (Nigeria). SportyBet provides
    1X2, Over/Under 0.5/1.5/2.5/3.5, BTTS, Double Chance, Draw No Bet,
    HT/FT, and Correct Score markets. Odds are cached for 60 seconds
    (configurable) to respect rate limits while maintaining freshness.

    The SportyBet client uses their internal API (factsCenter) the same way
    the browser does, without JavaScript execution. It provides direct access
    to the odds the Architect actually bets into.

    Markets supported (mapped to OLP XDV canonical keys):
    - 1X2: Home/Draw/Away
    - Over/Under: 0.5, 1.5, 2.5, 3.5
    - BTTS: Yes/No
    - Double Chance: 1X, X2, 12
    - Draw No Bet: Home, Away
    - HT/FT: 1/1, 1/X, 1/2, X/1, X/X, X/2, 2/1, 2/X, 2/2
    - Correct Score: 1:0, 0:1, 1:1, 2:0, 0:2, 2:1, 1:2, 2:2, 0:0, 3:0, 0:3, 3:1, 1:3

    Architecture: SportyBet is the PRIMARY odds source per Architect directive
    2026-08-31 — it's where the Architect actually places bets, so its prices
    are the ground truth for CLV calculation. The Odds API and API-Football
    are fallbacks for leagues/markets SportyBet doesn't cover.
    """

    def __init__(self):
        super().__init__("sportybet_odds", priority=10, timeout=30.0)

    def _normalize_str(self, s: str) -> str:
        """Normalize string for mapping: lower case, replace spaces/hyphens with underscores."""
        if not s:
            return ""
        return s.lower().replace(" ", "_").replace("-", "_")

    def _map_market_outcome_to_attribute(self, market_name: str, market_desc: str, outcome_name: str) -> Optional[str]:
        """
        Map SportyBet market name/desc and outcome name to OLP XDV FixtureOdds attribute.
        Returns attribute name (e.g., 'home', 'over15') or None if not mapped.
        """
        m_norm = self._normalize_str(market_name)
        d_norm = self._normalize_str(market_desc)
        o_norm = self._normalize_str(outcome_name)

        # Combine market and desc for lookup; some markets have info in desc
        market_key = f"{m_norm}_{d_norm}" if d_norm else m_norm
        # Also try without underscore if desc empty
        lookup_key = (market_key, o_norm)

        # Mapping: (market_key, outcome_name) -> attribute
        MAP = {
            # 1X2
            ("1x2", "home"): "home",
            ("1x2", "draw"): "draw",
            ("1x2", "away"): "away",
            ("match_winner", "home"): "home",
            ("match_winner", "draw"): "draw",
            ("match_winner", "away"): "away",
            ("full_time_result", "home"): "home",
            ("full_time_result", "draw"): "draw",
            ("full_time_result", "away"): "away",
            # Over/Under
            ("over_under_0_5", "over"): "over05",
            ("over_under_0_5", "under"): "under05",
            ("over_under_1_5", "over"): "over15",
            ("over_under_1_5", "under"): "under15",
            ("over_under_2_5", "over"): "over25",
            ("over_under_2_5", "under"): "under25",
            ("over_under_3_5", "over"): "over35",
            ("over_under_3_5", "under"): "under35",
            ("over_0_5", "over"): "over05",
            ("over_0_5", "under"): "under05",
            ("over_1_5", "over"): "over15",
            ("over_1_5", "under"): "under15",
            ("over_2_5", "over"): "over25",
            ("over_2_5", "under"): "under25",
            ("over_3_5", "over"): "over35",
            ("over_3_5", "under"): "under35",
            ("under_0_5", "over"): "over05",  # inverse
            ("under_0_5", "under"): "under05",
            ("under_1_5", "over"): "over15",
            ("under_1_5", "under"): "under15",
            ("under_2_5", "over"): "over25",
            ("under_2_5", "under"): "under25",
            ("under_3_5", "over"): "over35",
            ("under_3_5", "under"): "under35",
            # BTTS
            ("both_teams_to_score", "yes"): "btts_yes",
            ("both_teams_to_score", "no"): "btts_no",
            ("btts", "yes"): "btts_yes",
            ("btts", "no"): "btts_no",
            ("gg_ng", "gg"): "btts_yes",  # GG = Both Teams To Score Yes
            ("gg_ng", "ng"): "btts_no",    # NG = Both Teams To Score No
            ("gg", "gg"): "btts_yes",
            ("ng", "ng"): "btts_no",
            # Double Chance
            ("double_chance", "1x"): "dc_1x",
            ("double_chance", "x2"): "dc_x2",
            ("double_chance", "12"): "dc_12",
            ("dc", "1x"): "dc_1x",
            ("dc", "x2"): "dc_x2",
            ("dc", "12"): "dc_12",
            ("1x", "1x"): "dc_1x",  # fallback
            ("x2", "x2"): "dc_x2",
            ("12", "12"): "dc_12",
            # Draw No Bet
            ("draw_no_bet", "home"): "dnb_home",
            ("draw_no_bet", "away"): "dnb_away",
            ("dnb", "home"): "dnb_home",
            ("dnb", "away"): "dnb_away",
            ("dnb_home", "home"): "dnb_home",
            ("dnb_away", "away"): "dnb_away",
            # HT/FT
            ("half_time_full_time", "11"): "htft_11",
            ("half_time_full_time", "1x"): "htft_1x",
            ("half_time_full_time", "12"): "htft_12",
            ("half_time_full_time", "x1"): "htft_x1",
            ("half_time_full_time", "xx"): "htft_xx",
            ("half_time_full_time", "x2"): "htft_x2",
            ("half_time_full_time", "21"): "htft_21",
            ("half_time_full_time", "2x"): "htft_2x",
            ("half_time_full_time", "22"): "htft_22",
            ("ht_ft", "11"): "htft_11",
            ("ht_ft", "1x"): "htft_1x",
            ("ht_ft", "12"): "htft_12",
            ("ht_ft", "x1"): "htft_x1",
            ("ht_ft", "xx"): "htft_xx",
            ("ht_ft", "x2"): "htft_x2",
            ("ht_ft", "21"): "htft_21",
            ("ht_ft", "2x"): "htft_2x",
            ("ht_ft", "22"): "htft_22",
            ("htft", "11"): "htft_11",
            ("htft", "1x"): "htft_1x",
            ("htft", "12"): "htft_12",
            ("htft", "x1"): "htft_x1",
            ("htft", "xx"): "htft_xx",
            ("htft", "x2"): "htft_x2",
            ("htft", "21"): "htft_21",
            ("htft", "2x"): "htft_2x",
            ("htft", "22"): "htft_22",
            # Correct Score - we'll handle generically below
        }

        if lookup_key in MAP:
            return MAP[lookup_key]

        # Try market_key alone (if outcome name is empty or generic)
        lookup_key2 = (market_key, "")
        if lookup_key2 in MAP:
            return MAP[lookup_key2]

        # Try without desc
        lookup_key3 = (m_norm, o_norm)
        if lookup_key3 in MAP:
            return MAP[lookup_key3]

        # Handle Correct Score generically: outcome_name like "1:0", market_name might be "Correct Score"
        if m_norm in ("correct_score", "exact_score") and re.match(r'^\d+:\d+$', outcome_name):
            # Convert "1:0" to "cs_10"
            return f"cs_{outcome_name.replace(':', '_')}"

        # Also try if market_desc contains the score
        if d_norm and re.match(r'^\d+:\d+$', d_norm):
            return f"cs_{d_norm.replace(':', '_')}"

        return None

    def fetch(self, league: str) -> list:
        if not SPORTYBET_AVAILABLE:
            raise SourceNoData("sportybet: client not available (booking module not importable)")

        # Load SportyBet fixtures for this league
        fixtures = load_sportybet_fixtures(league, days_ahead=3)
        if not fixtures:
            raise SourceNoData(f"sportybet: no fixtures for {league}")

        # Build FixtureOdds from SportyBet live API
        from pipeline.odds import MarketQuote, FixtureOdds
        from datetime import datetime, timezone
        import re

        client = SportyBetClient()
        out = []

        try:
            for fx in fixtures:
                fixture_id = fx.sportybet_fixture_id
                if not fixture_id:
                    continue

                # Get odds for all markets from live API
                # Get tournament ID for this league
                from booking.league_map import SPORTYBET_LEAGUES
                mapping = SPORTYBET_LEAGUES.get(league)
                tournament_id = getattr(mapping, 'id', None) if mapping else None

                try:
                    live_markets = client.get_odds(fixture_id, tournament_id=tournament_id)
                except Exception as e:
                    log.warning(f"Failed to get live odds for fixture {fixture_id}: {e}")
                    continue

                odds = FixtureOdds(
                    league=league,
                    home_team=fx.home_team,
                    away_team=fx.away_team,
                    kickoff_utc=fx.kickoff_utc,
                    source="sportybet.com/ng",
                    source_tier="T1",
                )

                # Process each market from SportyBet API
                # The client.get_odds() returns MarketOdds with:
                # - market: normalized canonical key (e.g., "1X2_HOME", "OVER_1_5", "BTTS_YES")
                # - outcomes: dict of outcome_name -> price (e.g., {"Home": 1.5, "Draw": 3.5, "Away": 6.0})
                for market in live_markets:
                    market_key = market.market  # normalized canonical key from client
                    outcomes = market.outcomes   # dict: outcome_name -> price

                    # Map the SportyBet normalized market + outcome to FixtureOdds attributes
                    for outcome_name, price in outcomes.items():
                        if not outcome_name or not price:
                            continue
                        attr = self._map_sportybet_normalized_market(market_key, outcome_name)
                        if attr:
                            quote = MarketQuote(
                                price=price,
                                bookmaker="SportyBet Nigeria",
                                n_books=1,
                                captured_at=datetime.now(timezone.utc).isoformat()
                            )
                            setattr(odds, attr, quote)

                out.append(odds)

            if not out:
                raise SourceNoData(f"sportybet: no priced fixtures for {league}")

            return {"fixtures": out, "flags": [f"{league}: {len(out)} fixtures priced from SportyBet Nigeria"], "source": "sportybet_odds"}

        finally:
            client.close()

    def _map_sportybet_normalized_market(self, market_key: str, outcome_name: str) -> Optional[str]:
        """
        Map SportyBet's normalized market key + outcome name to FixtureOdds attribute.

        The SportyBetClient._normalize_market_key() produces keys like:
        - "1X2_HOME", "1X2_DRAW", "1X2_AWAY"
        - "OVER_0_5", "OVER_1_5", "OVER_2_5", "OVER_3_5", "OVER_0_5" (for under too, mapped to OVER)
        - "BTTS_YES", "BTTS_NO"
        - "DC_1X", "DC_X2", "DC_12"
        - "DNB_HOME", "DNB_AWAY"
        - "HT_FT_11", "HT_FT_1X", etc.
        - "CS_10", "CS_01", etc.

        The outcome_name from the API is the raw display name (e.g., "Home", "Draw", "Away",
        "Over", "Under", "Yes", "No", "1X", "X2", "12", "1/1", "1/X", etc.)
        """
        o_norm = outcome_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")

        # Mapping: (market_key_lower, outcome_normalized) -> attribute
        # All keys are lowercase for consistent lookup
        MAP = {
            # 1X2 markets - client normalizes "1x2", "match_winner", "full_time_result" to "1X2_HOME"
            # The outcomes dict will have keys like "Home", "Draw", "Away"
            ("1x2_home", "home"): "home",
            ("1x2_home", "draw"): "draw",
            ("1x2_home", "away"): "away",
            ("1x2_draw", "home"): "home",
            ("1x2_draw", "draw"): "draw",
            ("1x2_draw", "away"): "away",
            ("1x2_away", "home"): "home",
            ("1x2_away", "draw"): "draw",
            ("1x2_away", "away"): "away",
            # Generic 1X2 fallbacks
            ("1x2", "home"): "home",
            ("1x2", "draw"): "draw",
            ("1x2", "away"): "away",
            ("match_winner", "home"): "home",
            ("match_winner", "draw"): "draw",
            ("match_winner", "away"): "away",
            ("full_time_result", "home"): "home",
            ("full_time_result", "draw"): "draw",
            ("full_time_result", "away"): "away",

            # Over/Under - client normalizes to OVER_X_X keys
            ("over_0_5", "over"): "over05",
            ("over_0_5", "under"): "under05",
            ("over_1_5", "over"): "over15",
            ("over_1_5", "under"): "under15",
            ("over_2_5", "over"): "over25",
            ("over_2_5", "under"): "under25",
            ("over_3_5", "over"): "over35",
            ("over_3_5", "under"): "under35",
            # Handle inverse naming
            ("under_0_5", "over"): "over05",
            ("under_0_5", "under"): "under05",
            ("under_1_5", "over"): "over15",
            ("under_1_5", "under"): "under15",
            ("under_2_5", "over"): "over25",
            ("under_2_5", "under"): "under25",
            ("under_3_5", "over"): "over35",
            ("under_3_5", "under"): "under35",

            # BTTS
            ("btts_yes", "yes"): "btts_yes",
            ("btts_no", "no"): "btts_no",
            ("both_teams_to_score", "yes"): "btts_yes",
            ("both_teams_to_score", "no"): "btts_no",
            ("btts", "yes"): "btts_yes",
            ("btts", "no"): "btts_no",
            ("gg_ng", "gg"): "btts_yes",
            ("gg_ng", "ng"): "btts_no",
            ("gg", "gg"): "btts_yes",
            ("ng", "ng"): "btts_no",

            # Double Chance - client normalizes to DC_1X, DC_X2, DC_12
            ("dc_1x", "1x"): "dc_1x",
            ("dc_x2", "x2"): "dc_x2",
            ("dc_12", "12"): "dc_12",
            ("double_chance", "1x"): "dc_1x",
            ("double_chance", "x2"): "dc_x2",
            ("double_chance", "12"): "dc_12",
            ("1x", "1x"): "dc_1x",
            ("x2", "x2"): "dc_x2",
            ("12", "12"): "dc_12",

            # Draw No Bet
            ("dnb_home", "home"): "dnb_home",
            ("dnb_away", "away"): "dnb_away",
            ("draw_no_bet", "home"): "dnb_home",
            ("draw_no_bet", "away"): "dnb_away",
            ("dnb", "home"): "dnb_home",
            ("dnb", "away"): "dnb_away",
            ("dnb_home", "home"): "dnb_home",
            ("dnb_away", "away"): "dnb_away",

            # HT/FT
            ("ht_ft_11", "11"): "htft_11",
            ("ht_ft_1x", "1x"): "htft_1x",
            ("ht_ft_12", "12"): "htft_12",
            ("ht_ft_x1", "x1"): "htft_x1",
            ("ht_ft_xx", "xx"): "htft_xx",
            ("ht_ft_x2", "x2"): "htft_x2",
            ("ht_ft_21", "21"): "htft_21",
            ("ht_ft_2x", "2x"): "htft_2x",
            ("ht_ft_22", "22"): "htft_22",
            ("half_time_full_time", "11"): "htft_11",
            ("half_time_full_time", "1x"): "htft_1x",
            ("half_time_full_time", "12"): "htft_12",
            ("half_time_full_time", "x1"): "htft_x1",
            ("half_time_full_time", "xx"): "htft_xx",
            ("half_time_full_time", "x2"): "htft_x2",
            ("half_time_full_time", "21"): "htft_21",
            ("half_time_full_time", "2x"): "htft_2x",
            ("half_time_full_time", "22"): "htft_22",
            ("htft", "11"): "htft_11",
            ("htft", "1x"): "htft_1x",
            ("htft", "12"): "htft_12",
            ("htft", "x1"): "htft_x1",
            ("htft", "xx"): "htft_xx",
            ("htft", "x2"): "htft_x2",
            ("htft", "21"): "htft_21",
            ("htft", "2x"): "htft_2x",
            ("htft", "22"): "htft_22",
        }

        # Direct lookup with market_key and outcome (both lowercase)
        key = (market_key.lower(), o_norm)
        if key in MAP:
            return MAP[key]

        # Try with just the market_key (since some are already outcome-specific)
        # e.g., "1X2_HOME" already implies home
        if market_key.endswith("_HOME") or market_key.endswith("_home"):
            return "home"
        if market_key.endswith("_DRAW") or market_key.endswith("_draw"):
            return "draw"
        if market_key.endswith("_AWAY") or market_key.endswith("_away"):
            return "away"
        if market_key.endswith("_YES") or market_key.endswith("_yes"):
            return "btts_yes"
        if market_key.endswith("_NO") or market_key.endswith("_no"):
            return "btts_no"
        if market_key.endswith("_1X") or market_key.endswith("_1x"):
            return "dc_1x"
        if market_key.endswith("_X2") or market_key.endswith("_x2"):
            return "dc_x2"
        if market_key.endswith("_12"):
            return "dc_12"
        if market_key.endswith("_HOME") and "dnb" in market_key.lower():
            return "dnb_home"
        if market_key.endswith("_AWAY") and "dnb" in market_key.lower():
            return "dnb_away"

        # Handle HT/FT patterns like "HT_FT_11", "HT_FT_1X"
        if market_key.startswith("ht_ft_") or market_key.startswith("HT_FT_"):
            suffix = market_key.split("_")[-1].lower()
            if suffix in ["11", "1x", "12", "x1", "xx", "x2", "21", "2x", "22"]:
                return f"htft_{suffix}"

        # Handle Correct Score: market_key like "CS_10", "CS_01", etc.
        if market_key.startswith("cs_") or market_key.startswith("CS_"):
            # Extract the score part
            score_part = market_key[3:].replace("_", ":")
            return f"cs_{score_part.replace(':', '_')}"

        return None


class Bet365CachedOddsSource(DataSource):
    """Bet365 odds from daily cached JSONL feed (bet365_odds_*.jsonl).

    The daily scraper writes bet365_odds_YYYYMMDD_HHMMSS.jsonl to data/live_odds/
    with ALL canonical markets (1X2, O/U 0.5/1.5/2.5/3.5, BTTS, DC, DNB, HT/FT, CS).
    This source reads the latest cached file — zero quota cost, zero latency.

    Priority: 12 (between SportyBet and API-Football). This is the Architect's
    primary bookmaker (Bet365), so its cached prices are ground truth alongside
    SportyBet. The Odds API is removed from the default chain entirely.
    """

    def __init__(self):
        super().__init__("bet365_cached", priority=12, timeout=10.0)

    def fetch(self, league: str) -> list:
        from pathlib import Path
        import json
        from pipeline.odds import FixtureOdds, MarketQuote

        live_odds_dir = Path(__file__).parent.parent / "data" / "live_odds"
        bet365_odds_files = sorted(live_odds_dir.glob("bet365_odds_*.jsonl"), reverse=True)
        if not bet365_odds_files:
            raise SourceNoData("bet365_cached: no bet365_odds_*.jsonl files found")

        latest = bet365_odds_files[0]
        out = []

        for line in latest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "match_odds":
                continue
            if entry.get("league") != league:
                continue
            home_team = entry.get("home_team", "")
            away_team = entry.get("away_team", "")
            if not home_team or not away_team:
                continue

            markets = entry.get("markets", {})
            if not markets:
                continue

            # Parse kickoff
            raw_dt = entry.get("match_datetime", "")
            kickoff_utc = self._parse_bet365_datetime(raw_dt)

            fx = FixtureOdds(
                league=league,
                home_team=home_team,
                away_team=away_team,
                kickoff_utc=kickoff_utc,
                source="bet365-cached",
                source_tier="T1"
            )

            # Map all available markets from the cached feed
            for mkt_key, mkt_data in markets.items():
                price = mkt_data.get("price")
                if price is None:
                    continue
                # Map canonical keys to FixtureOdds attributes
                if mkt_key == "1X2_HOME":
                    fx.home = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "1X2_DRAW":
                    fx.draw = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "1X2_AWAY":
                    fx.away = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "OVER_0_5":
                    fx.over05 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "UNDER_0_5":
                    fx.under05 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "OVER_1_5":
                    fx.over15 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "UNDER_1_5":
                    fx.under15 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "OVER_2_5":
                    fx.over25 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "UNDER_2_5":
                    fx.under25 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "OVER_3_5":
                    fx.over35 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "UNDER_3_5":
                    fx.under35 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "BTTS_YES":
                    fx.btts_yes = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "BTTS_NO":
                    fx.btts_no = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "DC_1X":
                    fx.dc_1x = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "DC_X2":
                    fx.dc_x2 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "DC_12":
                    fx.dc_12 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "DNB_HOME":
                    fx.dnb_home = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "DNB_AWAY":
                    fx.dnb_away = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_11":
                    fx.htft_11 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_1X":
                    fx.htft_1x = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_12":
                    fx.htft_12 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_X1":
                    fx.htft_x1 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_XX":
                    fx.htft_xx = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_X2":
                    fx.htft_x2 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_21":
                    fx.htft_21 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_2X":
                    fx.htft_2x = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "HT_FT_22":
                    fx.htft_22 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_1_0":
                    fx.cs_10 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_0_1":
                    fx.cs_01 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_1_1":
                    fx.cs_11 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_2_0":
                    fx.cs_20 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_0_2":
                    fx.cs_02 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_2_1":
                    fx.cs_21 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_1_2":
                    fx.cs_12 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_2_2":
                    fx.cs_22 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_0_0":
                    fx.cs_00 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_3_0":
                    fx.cs_30 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_0_3":
                    fx.cs_03 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_3_1":
                    fx.cs_31 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))
                elif mkt_key == "CS_1_3":
                    fx.cs_13 = MarketQuote(price=price, bookmaker="Bet365", n_books=1, captured_at=entry.get("timestamp", ""))

            out.append(fx)

        if not out:
            raise SourceNoData(f"bet365_cached: no fixtures for {league} in {latest.name}")

        return {"fixtures": out, "flags": [f"{league}: {len(out)} fixtures from Bet365 cached feed ({latest.name})"], "source": "bet365_cached"}

    def _parse_bet365_datetime(self, raw_dt: str) -> str:
        """Parse Bet365 datetime string to UTC ISO format."""
        if not raw_dt:
            return ""
        try:
            from datetime import datetime, timezone
            # Bet365 format: "2026-08-31T14:30:00Z" or similar
            if raw_dt.endswith("Z"):
                return raw_dt
            # Try parsing as ISO with timezone
            dt = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return raw_dt


class OddsAPISource(DataSource):
    """The-Odds-API live prices — LAST RESORT ONLY (quota-limited).

    This source is kept available but REMOVED from the default fallback chain.
    The Odds API has a hard monthly quota (500 free credits) that exhausts
    mid-month. It should only be invoked explicitly (e.g., for specific leagues
    or manual validation), never as an automatic fallback.
    """

    def __init__(self, regions: str = "uk", markets: str = "h2h,totals"):
        super().__init__(f"odds_api_{regions}_{markets}", priority=50, timeout=30.0)
        self.regions = regions
        self.markets = markets

    def fetch(self, league: str) -> list:
        fixtures, flags = odds_fetch_odds(league, regions=self.regions, markets=self.markets)
        if not fixtures:
            raise SourceNoData(f"odds_api({self.regions}): no odds for {league}")
        return {"fixtures": fixtures, "flags": flags, "source": f"odds_api_{self.regions}"}


def build_odds_multi_source(league: str) -> MultiSource:
    """Build odds multi-source for a specific league.

    LIVE ODDS 3-SOURCE FALLBACK CHAIN (2026-08-31 Architect directive — updated):
    - SportyBet Nigeria (priority 10) — PRIMARY. The Architect's betting venue,
      so its prices are ground truth for CLV. Full market coverage (1X2, O/U
      0.5/1.5/2.5/3.5, BTTS, DC, DNB, HT/FT, CS).
    - Bet365 cached feed (priority 12) — SECONDARY. The Architect's primary
      bookmaker; cached JSONL has ALL markets, zero quota, zero latency.
    - API-Football free (priority 15) — FALLBACK. Same bookmakers, wider market
      coverage on free tier (includes O/U 1.5, BTTS, DC). 100 req/day.

    The Odds API (The-Odds-API.com) is REMOVED from the default chain. Its
    monthly quota (500 credits) exhausts predictably and kills the chain. It
    remains available as OddsAPISource for explicit/opt-in use only.
    """
    # SportyBet is PRIMARY (priority 10) — ground truth for CLV
    # Bet365 cached is SECONDARY (priority 12) — full markets, zero quota
    # API-Football is FALLBACK (priority 15) — wider free-tier coverage
    sources = [
        (SportyBetOddsSource().fetch, "sportybet_odds", 10),
        (Bet365CachedOddsSource().fetch, "bet365_cached", 12),
        (APIFootballOddsSource().fetch, "api_football_odds", 15),
    ]

    return build_multi_source(
        f"odds_{league}",
        sources,
        max_retries_per_source=1,
    )


# =============================================================================
# xG MULTI-SOURCE
# =============================================================================

class UnderstatXGSource(DataSource):
    """Understat expected goals data."""

    def __init__(self):
        super().__init__("understat", priority=10, timeout=30.0)

    def fetch(self, league: str, season: str) -> dict:
        if not xg_source.is_covered(league):
            raise SourceNoData(f"understat: league {league} not covered")
        ratings = xg_source.fit_xg(league, season)
        if not ratings:
            raise SourceNoData(f"understat: no xG ratings for {league} {season}")
        return {"ratings": ratings, "source": "understat"}


# Alternative xG sources could be added here (e.g., StatsBomb open data, etc.)


def build_xg_multi_source() -> MultiSource:
    return build_multi_source(
        "xg",
        [
            (UnderstatXGSource().fetch, "understat", 10),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# CURRENT SEASON RESULTS (for settling legs)
# =============================================================================

class FootballDataLiveSource(DataSource):
    """football-data.co.uk current season (updated ~daily during season)."""

    def __init__(self):
        super().__init__("football_data_live", priority=10, timeout=30.0)

    def fetch(self, league: str, season: str | int) -> list:
        # The current_results MultiSource is shared by the web live-scores feed
        # (server.py passes season as int) and the daily pipeline (str like
        # "2626"). load_league subscripts season[:2]/season[2:], so coerce here
        # rather than letting an int crash the whole source.
        season = str(season)
        from data.football_data_source import load_league
        results, skipped = load_league(league, season)
        if not results:
            raise SourceNoData(f"football_data_live: no results for {league} {season}")
        return {"results": results, "skipped": skipped, "source": "football_data_live"}


class APIFootballLiveSource(DataSource):
    """API-Football current season results."""

    def __init__(self):
        super().__init__("api_football_live", priority=15, timeout=30.0)

    def fetch(self, league: str, season: int) -> list:
        results, flags = apif.load_results(league, season=season)
        if not results:
            raise SourceNoData(f"api_football_live: no results for {league} {season}")
        return {"results": results, "flags": flags, "source": "api_football_live"}


def build_current_results_multi_source() -> MultiSource:
    return build_multi_source(
        "current_results",
        [
            (FootballDataLiveSource().fetch, "football_data_live", 10),
            (APIFootballLiveSource().fetch, "api_football_live", 15),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# LIVE SCORES MULTI-SOURCE (in-play real-time scores for client dashboard)
# =============================================================================

class ESPNLiveScoresSource(DataSource):
    """ESPN scoreboard live scores (key-free, covers all WHITELISTED_LEAGUES)."""

    def __init__(self):
        super().__init__("espn_live_scores", priority=10, timeout=15.0)

    def fetch(self, league: str, day: str | None = None) -> dict:
        scores = ls.fetch_espn_live_scores(league, day)
        if not scores:
            raise SourceNoData(f"espn_live_scores: no scores for {league}")
        return {
            "scores": scores,
            "source": "espn",
        }


class APIFootballLiveScoresSource(DataSource):
    """API-Football live scores (paid plan fallback)."""

    def __init__(self):
        super().__init__("api_football_live_scores", priority=15, timeout=30.0)

    def fetch(self, league: str, day: str | None = None) -> dict:
        scores = ls.fetch_apif_live_scores(league, day)
        if not scores:
            raise SourceNoData(f"api_football_live_scores: no scores for {league}")
        return {
            "scores": scores,
            "source": "api_football",
        }


def build_live_scores_multi_source() -> MultiSource:
    return build_multi_source(
        "live_scores",
        [
            (ESPNLiveScoresSource().fetch, "espn_live_scores", 10),
            (APIFootballLiveScoresSource().fetch, "api_football_live_scores", 15),
        ],
        max_retries_per_source=1,
    )


# =============================================================================
# INITIALIZATION - register all multi-sources with global registry
# =============================================================================

def initialize_multi_sources():
    """Initialize and register all multi-sources with the global registry."""
    registry.register(build_fixtures_multi_source())
    registry.register(build_results_multi_source())
    registry.register(build_xg_multi_source())
    registry.register(build_current_results_multi_source())
    registry.register(build_live_scores_multi_source())
    # Odds sources are per-league, created on demand
    log.info("Multi-source registry initialized")


# Convenience accessors for orchestrator integration

def get_fixtures(league: str, fixtures_season: str, days_ahead: int = 14,
                 api_football_season: int | None = None) -> dict:
    """Fetch fixtures with automatic failover."""
    ms = registry.get_source("fixtures")
    if ms is None:
        ms = build_fixtures_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, fixtures_season=fixtures_season,
                      days_ahead=days_ahead, api_football_season=api_football_season)
    return result.data


def get_historical_results(league: str, season: str) -> list:
    """Fetch historical results with automatic failover."""
    ms = registry.get_source("historical_results")
    if ms is None:
        ms = build_results_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["results"]


def get_current_results(league: str, season: str) -> list:
    """Fetch current season results with automatic failover."""
    ms = registry.get_source("current_results")
    if ms is None:
        ms = build_current_results_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["results"]


def get_xg_ratings(league: str, season: str) -> dict:
    """Fetch xG ratings with automatic failover."""
    ms = registry.get_source("xg")
    if ms is None:
        ms = build_xg_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, season=season)
    return result.data["ratings"]


def get_odds(league: str) -> list:
    """Fetch odds with automatic failover (per-league multi-source)."""
    # Build per-league odds source on demand
    return build_odds_multi_source(league).fetch(league=league).data["fixtures"]


def get_live_scores(league: str, day: str | None = None) -> dict:
    """Fetch live scores with automatic failover."""
    ms = registry.get_source("live_scores")
    if ms is None:
        ms = build_live_scores_multi_source()
        registry.register(ms)
    result = ms.fetch(league=league, day=day)
    return result.data


def get_all_health() -> dict:
    """Get health report for all registered sources."""
    return registry.get_health_report()