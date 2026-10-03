"""
Unit tests for the dynamic league registry (engine/league_registry.py).

Validates:
- Registry loads from config/leagues.json
- get_ids() returns correct per-source IDs
- is_eligible() matches deploy_eligible flag
- all_leagues() returns seeded leagues in order
- WHITELISTED_LEAGUES derived symbol matches deploy_eligible set
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.league_registry import registry, LeagueRegistry
from engine.leagues import WHITELISTED_LEAGUES, is_deploy_eligible


def test_registry_loads_seeded_leagues():
    """Registry loads all 61 European top-flight club leagues from config/leagues.json."""
    assert len(registry) == 61, f"Expected 61 leagues, got {len(registry)}"
    expected = {
        "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
        "Champions League", "Europa League", "Conference League", "UEFA Super Cup",
        "Scottish Premiership", "Belgian Pro League", "Eredivisie", "Championship",
        "Primeira Liga", "Danish Superliga", "Ekstraklasa", "HNL", "EFL Cup",
        "Austrian Bundesliga", "Turkish Super Lig", "Russian Premier League",
        "Swiss Super League", "Greek Super League", "Czech First League",
        "Romanian Liga I", "Ukrainian Premier League", "Serbian Super Liga",
        "Norwegian Eliteserien", "Swedish Allsvenskan", "Finnish Veikkausliiga",
        "Hungarian NB I", "Slovak Super Liga", "Slovenian PrvaLiga",
        "Bulgarian First League", "Israeli Premier League", "Cypriot First Division",
        "Albanian Superliga", "Armenian Premier League", "Azerbaijani Premyer Liqa",
        "Belarusian Premier League", "Kazakhstan Premier League", "Kosovan Superliga",
        "Latvian Virsliga", "Lithuanian A Lyga", "Luxembourg National Division",
        "Maltese Premier League", "Moldovan Super Liga", "Montenegrin First League",
        "Estonian Meistriliiga", "Georgian Erovnuli Liga", "Northern Irish Premiership",
        "Welsh Premier League", "Republic of Ireland Premier Division",
        "Icelandic Urvalsdeild", "Faroe Islands Premier League",
        "North Macedonian First League", "Bosnian Premier League",
        "Gibraltarian National League", "Andorran Primera Divisió",
        "Sanmarinese Campionato", "Liechtensteiner Cup"
    }
    assert set(registry.all_leagues()) == expected


def test_get_ids_returns_correct_mapping():
    """get_ids() returns the four source IDs for a known league."""
    ids = registry.get_ids("Premier League")
    assert ids is not None
    assert ids["thesportsdb"] == 4328
    assert ids["odds_api"] == "soccer_epl"
    assert ids["api_football"] == 39
    assert ids["football_data"] == "E0"

    # Continental comps have no football_data code
    ids = registry.get_ids("Champions League")
    assert ids["thesportsdb"] == 4480
    assert ids["odds_api"] == "soccer_uefa_champs_league_qualification"
    assert ids["api_football"] == 2
    assert ids["football_data"] is None


def test_is_eligible_matches_deploy_eligible():
    """is_eligible() True for all seeded leagues (all deploy_eligible: true)."""
    for name in registry.all_leagues():
        assert registry.is_eligible(name), f"{name} should be eligible"
    # Unknown league -> False
    assert not registry.is_eligible("Unknown League")


def test_all_leagues_returns_seeded_order():
    """all_leagues() returns leagues in JSON-seeded order."""
    leagues = registry.all_leagues()
    # First three are Premier League, La Liga, Serie A (JSON order)
    assert leagues[0] == "Premier League"
    assert leagues[1] == "La Liga"
    assert leagues[2] == "Serie A"


def test_whitelisted_leagues_derived_from_registry():
    """WHITELISTED_LEAGUES (engine/leagues) is sorted deploy_eligible set."""
    # All 59 seeded leagues are deploy_eligible
    assert set(WHITELISTED_LEAGUES) == set(registry.deploy_eligible_leagues())
    # WHITELISTED_LEAGUES is sorted alphabetically
    assert WHITELISTED_LEAGUES == sorted(WHITELISTED_LEAGUES)


def test_is_deploy_eligible_delegates_to_registry():
    """engine.leagues.is_deploy_eligible() delegates to registry.is_eligible()."""
    for name in registry.all_leagues():
        assert is_deploy_eligible(name)
    assert not is_deploy_eligible("Unknown League")


def test_source_convenience_functions():
    """Convenience functions (get_thesportsdb_id, get_odds_api_key, etc.) work."""
    from engine.league_registry import (
        get_thesportsdb_id, get_odds_api_key, get_api_football_id, get_football_data_code
    )
    assert get_thesportsdb_id("Premier League") == 4328
    assert get_odds_api_key("Premier League") == "soccer_epl"
    assert get_api_football_id("Premier League") == 39
    assert get_football_data_code("Premier League") == "E0"
    # Continental -> None for football_data
    assert get_football_data_code("Champions League") is None
    # Unknown -> None
    assert get_thesportsdb_id("Unknown") is None


def test_registry_singleton():
    """LeagueRegistry is a singleton — repeated instantiation returns same object."""
    r1 = LeagueRegistry()
    r2 = LeagueRegistry()
    assert r1 is r2


if __name__ == "__main__":
    test_registry_loads_seeded_leagues()
    test_get_ids_returns_correct_mapping()
    test_is_eligible_matches_deploy_eligible()
    test_all_leagues_returns_seeded_order()
    test_whitelisted_leagues_derived_from_registry()
    test_is_deploy_eligible_delegates_to_registry()
    test_source_convenience_functions()
    test_registry_singleton()
    print("All league registry tests passed.")