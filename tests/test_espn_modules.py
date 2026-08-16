"""
Unit tests for ESPN data modules (espn_results, espn_lineups, espn_winprob).

Tests the data models, cache behavior, and basic fetch logic without
requiring network calls (uses mocked responses).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.espn_results import (
    MatchResult,
    fetch_results_for_date,
    fetch_results_range,
    _extract_closing_odds,
    _extract_team_stats,
    _is_season_completed,
    CACHE_DIR,
)
from data.espn_lineups import (
    MatchLineup,
    TeamLineup,
    LineupPlayer,
    fetch_lineups_for_date,
    fetch_lineup_for_event,
    _extract_team_lineup,
    _parse_formation,
    _position_abbrev,
    CACHE_DIR as LINEUPS_CACHE_DIR,
)
from data.espn_winprob import (
    WinProbability,
    fetch_winprob_for_date,
    fetch_winprob_for_event,
    _implied_probabilities_from_odds,
    _extract_live_winprob,
    CACHE_DIR as WINPROB_CACHE_DIR,
)
from data.espn_source import LEAGUE_MAP


class TestESPNResults:
    """Tests for espn_results.py"""

    def test_match_result_dataclass(self):
        """MatchResult dataclass can be instantiated with all fields."""
        result = MatchResult(
            event_id="12345",
            league="La Liga",
            home_team="Alavés",
            away_team="Getafe",
            home_score=3,
            away_score=0,
            status="completed",
            match_date="2025-08-16",
            home_odds=2.10,
            draw_odds=3.20,
            away_odds=3.80,
            odds_source="DraftKings",
            home_stats={"shots": 15, "possession": 55},
            away_stats={"shots": 8, "possession": 45},
            provenance={"source": "ESPN", "fetched_at": "2025-08-16T10:00:00Z"},
        )
        assert result.event_id == "12345"
        assert result.home_team == "Alavés"
        assert result.home_score == 3
        assert result.odds_source == "DraftKings"

    def test_extract_closing_odds_draftkings_priority(self):
        """DraftKings odds take priority over Bet365."""
        competition = {
            "odds": [
                {
                    "provider": {"name": "Bet365"},
                    "items": [{"price": "2.00"}, {"price": "3.00"}, {"price": "3.50"}]
                },
                {
                    "provider": {"name": "DraftKings"},
                    "items": [{"price": "2.10"}, {"price": "3.20"}, {"price": "3.80"}]
                },
            ]
        }
        home, draw, away, source = _extract_closing_odds(competition)
        assert home == 2.10
        assert draw == 3.20
        assert away == 3.80
        assert source == "DraftKings"

    def test_extract_closing_odds_bet365_fallback(self):
        """Bet365 odds used when DraftKings not available."""
        competition = {
            "odds": [
                {
                    "provider": {"name": "Bet365"},
                    "items": [{"price": "2.00"}, {"price": "3.00"}, {"price": "3.50"}]
                },
            ]
        }
        home, draw, away, source = _extract_closing_odds(competition)
        assert home == 2.00
        assert draw == 3.00
        assert away == 3.50
        assert source == "Bet365"

    def test_extract_closing_odds_no_odds(self):
        """Returns None when no odds available."""
        competition = {"odds": []}
        home, draw, away, source = _extract_closing_odds(competition)
        assert home is None
        assert draw is None
        assert away is None
        assert source == ""

    def test_extract_team_stats(self):
        """Team statistics extracted correctly from competitors."""
        competitors = [
            {
                "homeAway": "home",
                "team": {"id": "1", "shortDisplayName": "Alavés"},
                "statistics": [
                    {"name": "shots", "value": 15},
                    {"name": "possession", "displayValue": "55%"},
                    {"name": "corners", "value": 6},
                ]
            },
            {
                "homeAway": "away",
                "team": {"id": "2", "shortDisplayName": "Getafe"},
                "statistics": [
                    {"name": "shots", "value": 8},
                    {"name": "possession", "displayValue": "45%"},
                ]
            },
        ]
        home_stats, away_stats = _extract_team_stats(competitors)
        assert home_stats["shots"] == 15
        assert home_stats["possession"] == "55%"
        assert home_stats["corners"] == 6
        assert away_stats["shots"] == 8
        assert away_stats["possession"] == "45%"

    def test_is_season_completed_previous_year(self):
        """Season from previous year is completed."""
        assert _is_season_completed("La Liga", "2024-12-01") is True

    def test_is_season_completed_current_year_early(self):
        """Early months of current year could be previous season."""
        # This is a heuristic - just test it doesn't crash
        result = _is_season_completed("La Liga", "2025-01-15")
        assert isinstance(result, bool)

    @patch("data.espn_results.requests.get")
    def test_fetch_results_for_date_no_requests(self, mock_get):
        """Handles missing requests library gracefully."""
        # If requests is None, should return empty list
        import data.espn_results as er
        original_requests = er.requests
        er.requests = None
        try:
            results = fetch_results_for_date("2025-08-16", "La Liga")
            assert results == []
        finally:
            er.requests = original_requests

    @patch("data.espn_results.requests.get")
    def test_fetch_results_for_date_mocked(self, mock_get):
        """Fetch results parses mocked ESPN response correctly."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "events": [
                {
                    "id": "401882926",
                    "date": "2025-08-16T19:00:00Z",
                    "status": {"type": {"name": "STATUS_FINAL"}},
                    "competitions": [{
                        "competitors": [
                            {"homeAway": "home", "team": {"shortDisplayName": "Alavés"}, "score": "3"},
                            {"homeAway": "away", "team": {"shortDisplayName": "Getafe"}, "score": "0"},
                        ],
                        "odds": [{
                            "provider": {"name": "DraftKings"},
                            "items": [{"price": "2.10"}, {"price": "3.20"}, {"price": "3.80"}]
                        }]
                    }]
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = fetch_results_for_date("2025-08-16", "La Liga")
        assert len(results) == 1
        assert results[0].home_team == "Alavés"
        assert results[0].away_team == "Getafe"
        assert results[0].home_score == 3
        assert results[0].away_score == 0
        assert results[0].home_odds == 2.10
        assert results[0].odds_source == "DraftKings"


class TestESPNLineups:
    """Tests for espn_lineups.py"""

    def test_lineup_player_dataclass(self):
        """LineupPlayer dataclass works correctly."""
        player = LineupPlayer(
            player_id="123",
            name="John Smith",
            short_name="J. Smith",
            position="MID",
            jersey_number=10,
            is_starter=True,
            formation_position="CM",
        )
        assert player.player_id == "123"
        assert player.position == "MID"
        assert player.is_starter is True

    def test_team_lineup_dataclass(self):
        """TeamLineup dataclass works correctly."""
        starters = [
            LineupPlayer("1", "GK1", "GK1", "GK", 1, True, "GK"),
            LineupPlayer("2", "DEF1", "DEF1", "DEF", 2, True, "RCB"),
        ]
        subs = [LineupPlayer("12", "SUB1", "SUB1", "MID", 12, False)]
        team = TeamLineup("1", "Team A", "4-4-2", starters, subs, "Coach")
        assert team.formation == "4-4-2"
        assert len(team.starters) == 2
        assert len(team.substitutes) == 1

    def test_match_lineup_dataclass(self):
        """MatchLineup dataclass works correctly."""
        match = MatchLineup(
            event_id="123",
            league="La Liga",
            home_team="Alavés",
            away_team="Getafe",
            match_date="2025-08-16",
            status="completed",
        )
        assert match.event_id == "123"
        assert match.home_team == "Alavés"

    def test_parse_formation(self):
        """Formation parsing normalizes correctly."""
        assert _parse_formation("3-5-2") == "3-5-2"
        assert _parse_formation("4-3-3") == "4-3-3"
        assert _parse_formation("Unknown") == "Unknown"
        assert _parse_formation("") == "Unknown"

    def test_position_abbrev(self):
        """Position abbreviations map correctly."""
        assert _position_abbrev("GK") == "GK"
        assert _position_abbrev("CB") == "DEF"
        assert _position_abbrev("LWB") == "DEF"
        assert _position_abbrev("CM") == "MID"
        assert _position_abbrev("CAM") == "MID"
        assert _position_abbrev("LW") == "FWD"
        assert _position_abbrev("ST") == "FWD"
        assert _position_abbrev("UNKNOWN") == "UNKNOWN"

    def test_extract_team_lineup(self):
        """Extract team lineup from ESPN data."""
        lineup_data = {
            "team": {
                "id": "1",
                "displayName": "Alavés",
                "shortDisplayName": "ALA",
            },
            "formation": "3-5-2",
            "athletes": [
                {
                    "athlete": {"id": "1", "displayName": "GK1", "shortName": "GK1"},
                    "position": "GK",
                    "starter": True,
                    "jersey": 1,
                    "slot": "GK",
                },
                {
                    "athlete": {"id": "2", "displayName": "DEF1", "shortName": "DEF1"},
                    "position": "CB",
                    "starter": True,
                    "jersey": 4,
                    "slot": "RCB",
                },
                {
                    "athlete": {"id": "12", "displayName": "SUB1", "shortName": "SUB1"},
                    "position": "CM",
                    "starter": False,
                    "jersey": 12,
                },
            ],
            "coach": "Coach Name",
        }
        team = _extract_team_lineup(lineup_data, "home")
        assert team is not None
        assert team.team_name == "Alavés"
        assert team.formation == "3-5-2"
        assert len(team.starters) == 2
        assert len(team.substitutes) == 1
        assert team.coach == "Coach Name"
        assert team.starters[0].position == "GK"
        assert team.starters[1].position == "DEF"

    @patch("data.espn_lineups.requests.get")
    def test_fetch_lineup_for_event_mocked(self, mock_get):
        """Fetch lineup for event parses mocked response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "header": {
                "league": {"name": "La Liga"},
                "date": "2025-08-16T19:00:00Z",
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitions": [
                    {"team": {"shortDisplayName": "Alavés"}},
                    {"team": {"shortDisplayName": "Getafe"}},
                ],
            },
            "lineups": [
                {
                    "team": {"id": "1", "displayName": "Alavés"},
                    "formation": "3-5-2",
                    "athletes": [
                        {"athlete": {"id": "1", "displayName": "GK1"}, "position": "GK", "starter": True, "jersey": 1, "slot": "GK"},
                    ],
                },
                {
                    "team": {"id": "2", "displayName": "Getafe"},
                    "formation": "4-4-2",
                    "athletes": [
                        {"athlete": {"id": "2", "displayName": "GK2"}, "position": "GK", "starter": True, "jersey": 1, "slot": "GK"},
                    ],
                },
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        lineup = fetch_lineup_for_event("401882926")
        assert lineup is not None
        assert lineup.home_team == "Alavés"
        assert lineup.away_team == "Getafe"
        assert lineup.home_lineup is not None
        assert lineup.away_lineup is not None
        assert lineup.home_lineup.formation == "3-5-2"


class TestESPNWinProb:
    """Tests for espn_winprob.py"""

    def test_winprobability_dataclass(self):
        """WinProbability dataclass works correctly."""
        wp = WinProbability(
            event_id="123",
            league="La Liga",
            home_team="Alavés",
            away_team="Getafe",
            match_date="2025-08-16",
            status="completed",
            home_win_prob=45.0,
            draw_prob=30.0,
            away_win_prob=25.0,
            odds_source="DraftKings",
        )
        assert wp.event_id == "123"
        assert wp.home_win_prob == 45.0
        assert wp.odds_source == "DraftKings"

    def test_implied_probabilities_from_odds(self):
        """Implied probabilities calculated correctly with devig."""
        # Fair odds: 2.0, 3.0, 4.0 -> implied: 50%, 33.3%, 25% -> total 108.3%
        # Devigged: 46.15%, 30.77%, 23.08%
        h, d, a = _implied_probabilities_from_odds(2.0, 3.0, 4.0)
        assert abs(h - 46.15) < 0.1
        assert abs(d - 30.77) < 0.1
        assert abs(a - 23.08) < 0.1
        assert abs(h + d + a - 100) < 0.1

    def test_implied_probabilities_equal_odds(self):
        """Equal odds produce equal probabilities."""
        h, d, a = _implied_probabilities_from_odds(3.0, 3.0, 3.0)
        assert abs(h - 33.33) < 0.1
        assert abs(d - 33.33) < 0.1
        assert abs(a - 33.33) < 0.1

    def test_extract_live_winprob_from_competitions(self):
        """Live win probability extracted from competitions array."""
        data = {
            "competitions": [{
                "winprobability": {
                    "homeWinPercentage": 60.5,
                    "awayWinPercentage": 25.3,
                    "tiePercentage": 14.2,
                }
            }]
        }
        h, d, a = _extract_live_winprob(data)
        assert h == 60.5
        assert a == 25.3
        assert d == 14.2

    def test_extract_live_winprob_from_situation(self):
        """Live win probability extracted from situation object."""
        data = {
            "competitions": [{
                "situation": {
                    "winprobability": {
                        "homeWinPercentage": 55.0,
                        "awayWinPercentage": 30.0,
                        "tiePercentage": 15.0,
                    }
                }
            }]
        }
        h, d, a = _extract_live_winprob(data)
        assert h == 55.0
        assert a == 30.0
        assert d == 15.0

    def test_extract_live_winprob_not_available(self):
        """Returns None when no live winprob in data."""
        data = {"competitions": [{}]}
        h, d, a = _extract_live_winprob(data)
        assert h is None
        assert d is None
        assert a is None

    @patch("data.espn_winprob.requests.get")
    def test_fetch_winprob_for_event_mocked(self, mock_get):
        """Fetch winprob for event parses mocked response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "header": {
                "league": {"name": "La Liga"},
                "date": "2025-08-16T19:00:00Z",
                "status": {"type": {"name": "STATUS_FINAL"}},
                "competitions": [
                    {"team": {"shortDisplayName": "Alavés"}},
                    {"team": {"shortDisplayName": "Getafe"}},
                ],
            },
            "pickcenter": [{
                "providers": [{
                    "name": "DraftKings",
                    "outcomes": [
                        {"type": "home", "odds": {"decimal": "2.10"}},
                        {"type": "draw", "odds": {"decimal": "3.20"}},
                        {"type": "away", "odds": {"decimal": "3.80"}},
                    ],
                }],
            }],
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        wp = fetch_winprob_for_event("401882926")
        assert wp is not None
        assert wp.home_team == "Alavés"
        assert wp.away_team == "Getafe"
        assert wp.home_win_prob is not None
        assert wp.odds_source == "DraftKings"


class TestESPNMultiSource:
    """Tests for espn_multi_source.py integration."""

    def test_register_all_espn_sources(self):
        """Register all ESPN sources doesn't crash."""
        from data.espn_multi_source import register_all_espn_sources, get_espn_health_report
        # Just test it runs without error
        registered = register_all_espn_sources(["La Liga", "Premier League"])
        assert "La Liga" in registered
        assert "Premier League" in registered
        assert "results" in registered["La Liga"]
        assert "lineups" in registered["La Liga"]
        assert "winprob" in registered["La Liga"]

        health = get_espn_health_report()
        assert "espn_sources" in health
        assert "timestamp" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])