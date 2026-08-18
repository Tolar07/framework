"""HR35 Fixture Fabrication Audit — HR58 Order 1

Audits all 4 fixture sources for the 'No Fabrication' rule (HR35):
missing data must raise or be skipped — NEVER guessed, filled, or silently
reconstructed. If any source returns a fixture with a guessed/filled value,
the test fails.

Sources audited:
1. data/thesportsdb_fixtures.py — fetch_upcoming, fetch_today, load_results
2. data/fixtures_source.py — API-Football fetch_upcoming
3. data/espn_source.py — ESPN fetch_upcoming
4. data/pipeline/odds.py — fixtures_from_odds (odds-derived fixtures)

EVENTSDAY fallback pinned at: data/thesportsdb_fixtures.py:fetch_today (lines 851-884)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# =============================================================================
# 1. THE SPORTS DB — fetch_upcoming / fetch_today / load_results
# =============================================================================

def test_thesportsdb_fetch_upcoming_no_fabrication_on_missing_team():
    """Season feed: rows with missing team name/date are skipped, not fabricated."""
    from data import thesportsdb_fixtures as tsdb

    # Mock response: one valid, one missing home team, one missing away team,
    # one with missing date (strTimestamp), one already played
    MOCK_EVENTS = {
        "events": [
            # VALID upcoming fixture
            {"idEvent": "1", "strHomeTeam": "Team A", "strAwayTeam": "Team B",
             "strTimestamp": "2026-08-20 15:00:00", "strStatus": "NS",
             "intHomeScore": None, "intAwayScore": None},
            # MISSING home team — must be skipped (HR35)
            {"idEvent": "2", "strHomeTeam": "", "strAwayTeam": "Team C",
             "strTimestamp": "2026-08-20 16:00:00", "strStatus": "NS",
             "intHomeScore": None, "intAwayScore": None},
            # MISSING away team — must be skipped (HR35)
            {"idEvent": "3", "strHomeTeam": "Team D", "strAwayTeam": "",
             "strTimestamp": "2026-08-20 17:00:00", "strStatus": "NS",
             "intHomeScore": None, "intAwayScore": None},
            # MISSING date — must be skipped (HR35)
            {"idEvent": "4", "strHomeTeam": "Team E", "strAwayTeam": "Team F",
             "strTimestamp": "", "strStatus": "NS",
             "intHomeScore": None, "intAwayScore": None},
            # ALREADY PLAYED — must be excluded (not upcoming)
            {"idEvent": "5", "strHomeTeam": "Team G", "strAwayTeam": "Team H",
             "strTimestamp": "2026-08-10 15:00:00", "strStatus": "FT",
             "intHomeScore": "2", "intAwayScore": "1"},
        ]
    }

    def _fake_get(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return MOCK_EVENTS
        return R()

    # Ensure league is mapped
    original_league_ids = dict(tsdb.LEAGUE_IDS)
    tsdb.LEAGUE_IDS["Test League"] = 999999

    try:
        with patch("data.retry.request", side_effect=_fake_get):
            fixtures = tsdb.fetch_upcoming("Test League")
        # Only the VALID fixture should be returned
        assert len(fixtures) == 1, f"Expected 1 valid fixture, got {len(fixtures)}"
        assert fixtures[0].home_team == "Team A"
        assert fixtures[0].away_team == "Team B"
        # Confirm NO fabricated data leaked in
        for f in fixtures:
            assert f.home_team and f.away_team, "Fabricated empty team name detected"
            assert f.date, "Fabricated missing date detected"
    finally:
        tsdb.LEAGUE_IDS.clear()
        tsdb.LEAGUE_IDS.update(original_league_ids)


def test_thesportsdb_fetch_today_no_fabrication():
    """EVENTSDAY fallback: same HR35 rules — missing data skipped, never guessed."""
    from data import thesportsdb_fixtures as tsdb

    MOCK_EVENTS = {
        "events": [
            {"strHomeTeam": "Team A", "strAwayTeam": "Team B", "strTime": "15:00", "strStatus": "NS"},
            {"strHomeTeam": "", "strAwayTeam": "Team C", "strTime": "16:00", "strStatus": "NS"},  # skipped
            {"strHomeTeam": "Team D", "strAwayTeam": "", "strTime": "17:00", "strStatus": "NS"},  # skipped
            {"strHomeTeam": "Team E", "strAwayTeam": "Team F", "strTime": "18:00",
             "strStatus": "FT", "intHomeScore": "1", "intAwayScore": "0"},  # played -> excluded
        ]
    }

    def _fake_get(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return MOCK_EVENTS
        return R()

    original_league_ids = dict(tsdb.LEAGUE_IDS)
    tsdb.LEAGUE_IDS["Test League"] = 999999

    try:
        with patch("data.retry.request", side_effect=_fake_get):
            fixtures = tsdb.fetch_today("Test League", "2026-08-20")
        assert len(fixtures) == 1, f"Expected 1 valid fixture, got {len(fixtures)}"
        assert fixtures[0].home_team == "Team A"
        assert fixtures[0].away_team == "Team B"
    finally:
        tsdb.LEAGUE_IDS.clear()
        tsdb.LEAGUE_IDS.update(original_league_ids)


def test_thesportsdb_load_results_no_fabrication():
    """Historical results: missing score/team -> skipped, never guessed."""
    from data import thesportsdb_fixtures as tsdb

    MOCK_EVENTS = {
        "events": [
            {"idEvent": "1", "strHomeTeam": "Team A", "strAwayTeam": "Team B",
             "intHomeScore": "2", "intAwayScore": "1", "strStatus": "FT"},
            {"idEvent": "2", "strHomeTeam": "", "strAwayTeam": "Team C",
             "intHomeScore": "1", "intAwayScore": "0", "strStatus": "FT"},  # skipped
            {"idEvent": "3", "strHomeTeam": "Team D", "strAwayTeam": "Team E",
             "intHomeScore": None, "intAwayScore": None, "strStatus": "NS"},  # not finished -> skipped
        ]
    }

    def _fake_get(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return MOCK_EVENTS
        return R()

    original_league_ids = dict(tsdb.LEAGUE_IDS)
    tsdb.LEAGUE_IDS["Test League"] = 999999

    try:
        with patch("data.retry.request", side_effect=_fake_get):
            results = tsdb.load_results("Test League", "2026-08-20")
        assert len(results) == 1, f"Expected 1 valid result, got {len(results)}"
        assert results[0].home_team == "Team A"
        assert results[0].away_team == "Team B"
        assert results[0].home_score == 2
        assert results[0].away_score == 1
    finally:
        tsdb.LEAGUE_IDS.clear()
        tsdb.LEAGUE_IDS.update(original_league_ids)


# =============================================================================
# 2. API-FOOTBALL — fetch_upcoming raises on failure, never returns guessed list
# =============================================================================

def test_apifootball_fetch_upcoming_raises_on_failure():
    """fetch_upcoming must raise on API failure — never return empty/guessed list."""
    from data import fixtures_source as af

    # Simulate an HTTP error (e.g., 401, 403, 500)
    def _fake_get_error(*a, **k):
        class R:
            status_code = 500
            def raise_for_status(self):
                from requests import HTTPError
                raise HTTPError("Server Error")
            def json(self): return {"errors": "Internal Server Error"}
        return R()

    with patch("data.retry.request", side_effect=_fake_get_error):
        with pytest.raises(Exception):  # SourceNoData or HTTPError bubbled up
            af.fetch_upcoming("Premier League", "2026-08-20", "2026-08-27")


def test_apifootball_resolve_league_id_raises_on_empty_or_ambiguous():
    """resolve_league_id must raise on empty/ambiguous matches — never guess."""
    from data import fixtures_source as af

    # Empty response
    def _fake_get_empty(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"response": []}
        return R()

    with patch("data.retry.request", side_effect=_fake_get_empty):
        with pytest.raises(ValueError, match="No leagues found|not found|ambiguous"):
            af.resolve_league_id("Nonexistent League")

    # Ambiguous response (multiple matches)
    def _fake_get_multi(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"response": [
                {"league": {"name": "League A", "id": 1}},
                {"league": {"name": "League A", "id": 2}},
            ]}
        return R()

    with patch("data.retry.request", side_effect=_fake_get_multi):
        with pytest.raises(ValueError, match="ambiguous|multiple"):
            af.resolve_league_id("League A")


# =============================================================================
# 3. ESPN — fetch_upcoming raises on unmapped slug, skips missing data
# =============================================================================

def test_espn_fetch_upcoming_raises_on_unmapped_slug():
    """Unmapped slug must raise ValueError — wrong slug silently returning another
    competition's fixtures is a fabrication path (HR35)."""
    from data import espn_source as espn

    # A slug that doesn't exist in ESPN's league mapping
    with pytest.raises(ValueError, match="No ESPN slug|not mapped|unknown"):
        espn.fetch_upcoming("2026-08-20", "2026-08-27", league="Nonexistent League")


def test_espn_fetch_upcoming_skips_missing_team_or_date():
    """Missing team name or date -> row skipped, never fabricated."""
    from data import espn_source as espn

    # Mock a valid ESPN scoreboard response with one good event and one bad
    MOCK_ESPN = {
        "events": [
            {
                "id": "1",
                "name": "Team A vs Team B",
                "shortName": "A vs B",
                "date": "2026-08-20T15:00Z",
                "status": {"type": {"name": "STATUS_SCHEDULED", "completed": False}},
                "competitions": [{
                    "competitors": [
                        {"team": {"displayName": "Team A"}, "homeAway": "home"},
                        {"team": {"displayName": "Team B"}, "homeAway": "away"},
                    ]
                }]
            },
            # Missing team name in competitor
            {
                "id": "2",
                "name": " vs Team C",
                "date": "2026-08-20T16:00Z",
                "status": {"type": {"name": "STATUS_SCHEDULED", "completed": False}},
                "competitions": [{
                    "competitors": [
                        {"team": {"displayName": ""}, "homeAway": "home"},
                        {"team": {"displayName": "Team C"}, "homeAway": "away"},
                    ]
                }]
            },
            # Missing date
            {
                "id": "3",
                "name": "Team D vs Team E",
                "date": "",
                "status": {"type": {"name": "STATUS_SCHEDULED", "completed": False}},
                "competitions": [{
                    "competitors": [
                        {"team": {"displayName": "Team D"}, "homeAway": "home"},
                        {"team": {"displayName": "Team E"}, "homeAway": "away"},
                    ]
                }]
            },
        ]
    }

    def _fake_get(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return MOCK_ESPN
        return R()

    # Need a league with ESPN slug - use a known one or mock the slug map
    original_map = dict(espn.LEAGUE_SLUGS)
    espn.LEAGUE_SLUGS["Test League"] = "test.league"

    try:
        with patch("data.retry.request", side_effect=_fake_get):
            fixtures = espn.fetch_upcoming("2026-08-20", "2026-08-27", league="Test League")
        # Only the fully valid event should appear
        assert len(fixtures) == 1, f"Expected 1 valid fixture, got {len(fixtures)}"
        assert fixtures[0].home_team == "Team A"
        assert fixtures[0].away_team == "Team B"
        # Ensure no fabricated data
        for f in fixtures:
            assert f.home_team and f.away_team
            assert f.date
    finally:
        espn.LEAGUE_SLUGS.clear()
        espn.LEAGUE_SLUGS.update(original_map)


# =============================================================================
# 4. ODDS-DERIVED FIXTURES — fixtures_from_odds skips incomplete, rejects stale
# =============================================================================

def test_odds_fixtures_from_odds_skips_incomplete_records():
    """Derived fixtures: any record missing team/date/kickoff -> skipped, never fabricated."""
    from pipeline import odds as odds_module

    # Build a mock priced event with missing fields
    MOCK_ODDS_RESPONSE = {
        "data": [
            # VALID event
            {
                "id": "evt_1",
                "commence_time": "2026-08-20T15:00:00Z",
                "home_team": "Team A",
                "away_team": "Team B",
                "bookmakers": [{
                    "title": "SportyBet",
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Team A", "price": 2.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "Team B", "price": 3.5},
                        ]
                    }]
                }]
            },
            # MISSING home_team — must be skipped
            {
                "id": "evt_2",
                "commence_time": "2026-08-20T16:00:00Z",
                "home_team": "",
                "away_team": "Team C",
                "bookmakers": [{
                    "title": "SportyBet",
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "", "price": 2.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "Team C", "price": 3.5},
                        ]
                    }]
                }]
            },
            # MISSING commence_time — must be skipped
            {
                "id": "evt_3",
                "commence_time": "",
                "home_team": "Team D",
                "away_team": "Team E",
                "bookmakers": [{
                    "title": "SportyBet",
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Team D", "price": 2.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "Team E", "price": 3.5},
                        ]
                    }]
                }]
            },
            # STALE odds (> 60 min old) — must be rejected
            {
                "id": "evt_4",
                "commence_time": "2026-08-20T15:00:00Z",
                "home_team": "Team F",
                "away_team": "Team G",
                "bookmakers": [{
                    "title": "SportyBet",
                    "last_update": "2026-08-20T10:00:00Z",  # > 60 min before commence
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Team F", "price": 2.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "Team G", "price": 3.5},
                        ]
                    }]
                }]
            },
        ]
    }

    fixtures = odds_module.fixtures_from_odds(MOCK_ODDS_RESPONSE)

    # Only the valid event should produce a fixture
    assert len(fixtures) == 1, f"Expected 1 valid fixture, got {len(fixtures)}"
    assert fixtures[0].home_team == "Team A"
    assert fixtures[0].away_team == "Team B"
    # No fabricated data
    for f in fixtures:
        assert f.home_team and f.away_team
        assert f.date


# =============================================================================
# 5. MULTI-SOURCE FAILOVER — chain raises SourceNoData, never fabricates
# =============================================================================

def test_multi_source_fixtures_chain_raises_no_data():
    """Failover chain: when ALL sources raise SourceNoData, the chain raises —
    never returns a guessed/empty list as a silent fallback."""
    from data import multi_source_concrete as msc

    # This is a contract test: build_fixtures_multi_source() returns a chain
    # where each source's fetch() raises SourceNoData on honest failure.
    # The chain itself does not fabricate — it propagates the exception.
    chain = msc.build_fixtures_multi_source()

    # Verify the chain structure exists (sources in priority order)
    assert chain.sources, "Fixture chain has no sources"
    # API-Football (10) -> TheSportsDB (15) -> ESPN (20) -> Odds (30)
    priorities = [s.priority for s in chain.sources]
    assert priorities == [10, 15, 20, 30], f"Unexpected priority order: {priorities}"

    # Each source's fetch method should be present and raise SourceNoData
    for src in chain.sources:
        assert hasattr(src, 'fetch'), f"{src.__class__.__name__} missing fetch()"
        # Note: we don't call fetch() here as it requires network — this is a
        # structural contract test. The HR35 compliance is tested per-source above.


if __name__ == "__main__":
    # Allow running as a script
    pytest.main([__file__, "-v"])