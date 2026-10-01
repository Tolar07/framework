"""
Tests for pipeline.odds_sportybet (offline, network stubbed).

Guards the HR35-critical behaviour: team names are mapped to model keys by the
verified alias list, unmapped names pass through (never fuzzy-matched), and the
full-market payload is parsed into 1X2 + O/U 2.5 correctly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.odds_sportybet as sb

# One synthetic SportyBet event with the full-market shape the API returns.
EVENT = {
    "homeTeamName": "Rakow Czestochowa", "awayTeamName": "LKP Motor Lublin",
    "estimateStartTime": 1791640800000,
    "markets": [
        {"id": "1", "desc": "1X2", "specifier": "", "outcomes": [
            {"desc": "Home", "odds": "1.72"}, {"desc": "Draw", "odds": "3.6"},
            {"desc": "Away", "odds": "4.1"}]},
        {"id": "18", "desc": "Over/Under", "specifier": "total=2.5", "outcomes": [
            {"desc": "Over 2.5", "odds": "1.90"}, {"desc": "Under 2.5", "odds": "1.85"}]},
        {"id": "18", "desc": "Over/Under", "specifier": "total=3.5", "outcomes": [
            {"desc": "Over 3.5", "odds": "3.10"}, {"desc": "Under 3.5", "odds": "1.35"}]},
        {"id": "29", "desc": "GG/NG", "specifier": "", "outcomes": [
            {"desc": "Yes", "odds": "1.95"}, {"desc": "No", "odds": "1.80"}]},
    ],
}


def test_alias_mapping_to_model_keys() -> None:
    # Verified pairs map; an exact model name passes through unchanged.
    assert sb.map_team("Ekstraklasa", "Rakow Czestochowa") == "Rakow"
    assert sb.map_team("Ekstraklasa", "LKP Motor Lublin") == "Motor Lublin"
    assert sb.map_team("Ekstraklasa", "Gornik Zabrze") == "Gornik Zabrze"  # exact, no alias
    # Unknown club is NOT guessed — passes through so it fails safe to NO DATA.
    assert sb.map_team("Ekstraklasa", "Some New FC") == "Some New FC"


def test_full_market_parsed() -> None:
    markets = sb.parse_markets(EVENT)
    assert len(markets) == 4, "every market kept, not just 1X2/O/U"
    assert sb._price(markets, "1X2", "Home") == 1.72
    assert sb._price(markets, "Over/Under", "Over 2.5", specifier="total=2.5") == 1.90
    # the 3.5 line must not be confused with the 2.5 line
    assert sb._price(markets, "Over/Under", "Under 2.5", specifier="total=2.5") == 1.85


def test_fetch_maps_names_and_prices() -> None:
    sb._load_all_events = lambda: ({"sr:tournament:202": [EVENT]}, ["stubbed"])
    fx, flags = sb.fetch_odds_sportybet("Ekstraklasa")
    assert len(fx) == 1
    q = fx[0]
    assert (q.home_team, q.away_team) == ("Rakow", "Motor Lublin"), "names -> model keys"
    assert q.home.price == 1.72 and q.home.bookmaker == "sportybet"
    assert q.over25.price == 1.90 and q.under25.price == 1.85
    assert q.source == "sportybet.com"


def test_unmapped_league_returns_nothing() -> None:
    fx, flags = sb.fetch_odds_sportybet("Faroe Islands Premier League")  # no tournament ID configured
    assert fx == []
    assert any("no verified SportyBet tournament ID" in f for f in flags)


def main() -> None:
    orig = sb._load_all_events
    try:
        test_alias_mapping_to_model_keys()
        test_full_market_parsed()
        test_fetch_maps_names_and_prices()
        test_unmapped_league_returns_nothing()
    finally:
        sb._load_all_events = orig
    print("sportybet_odds_test: OK")


if __name__ == "__main__":
    main()
