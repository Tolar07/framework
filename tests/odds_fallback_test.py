"""
Tests for the football-data odds fallback and the fetch_odds_chained coordinator.

Offline (network stubbed), plain-script style like the other tests. Guards:
  1. Extra-schema leagues (Ekstraklasa) return [] with an honest flag, not a guess.
  2. A covered league parses 1X2 + O/U with reachable-book provenance.
  3. The chain falls back to football-data when the-odds-api is quota-exhausted.
  4. The chain keeps the-odds-api result when it yields fixtures (fallback unused).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.odds as odds
import pipeline.odds_footballdata as fdo

# A minimal fixtures.csv slice: one Eredivisie (N1) row with Bet365 1X2 + O/U,
# plus a row from another division that must be filtered out.
SAMPLE_ROWS = [
    {"Div": "N1", "Date": "04/10/2026", "HomeTeam": "Ajax", "AwayTeam": "Feyenoord",
     "B365H": "1.80", "B365D": "3.80", "B365A": "4.20",
     "B365>2.5": "1.55", "B365<2.5": "2.45"},
    {"Div": "E0", "Date": "04/10/2026", "HomeTeam": "Arsenal", "AwayTeam": "Chelsea",
     "B365H": "2.10", "B365D": "3.40", "B365A": "3.60"},
]


def test_extra_league_returns_nothing() -> None:
    fx, flags = fdo.fetch_odds_footballdata("Ekstraklasa")
    assert fx == [], "Extra-schema league must yield no football-data fixtures"
    assert any("not in football-data fixtures.csv" in f for f in flags), flags


def test_covered_league_parses() -> None:
    fx, flags = fdo.fetch_odds_footballdata("Eredivisie")
    assert len(fx) == 1, "only the N1 row should match Eredivisie"
    q = fx[0]
    assert (q.home_team, q.away_team) == ("Ajax", "Feyenoord")
    assert q.home.price == 1.80 and q.home.bookmaker == "bet365"
    assert q.away.price == 4.20
    assert q.over25.price == 1.55 and q.under25.price == 2.45
    assert q.source == "football-data.co.uk (fixtures)" and q.source_tier == "T1"


def test_chain_falls_back_on_quota() -> None:
    def boom(_league):
        raise odds.QuotaExhausted("quota down to 0")

    odds.fetch_odds = boom  # primary exhausted
    fx, flags = odds.fetch_odds_chained("Eredivisie")
    assert len(fx) == 1 and fx[0].source.startswith("football-data"), \
        "chain must fall back to football-data when the odds API is exhausted"
    assert any("falling back to football-data" in f for f in flags), flags


def test_chain_prefers_primary() -> None:
    sentinel = odds.FixtureOdds(league="Eredivisie", home_team="X", away_team="Y",
                                kickoff_utc="2026-10-04", source="the-odds-api.com")

    def primary(_league):
        return [sentinel], ["primary ok"]

    called = {"fallback": False}

    def fallback(_league):
        called["fallback"] = True
        return [], []

    odds.fetch_odds = primary
    fdo.fetch_odds_footballdata = fallback
    fx, flags = odds.fetch_odds_chained("Eredivisie")
    assert fx == [sentinel], "primary result must win when it yields fixtures"
    assert called["fallback"] is False, "fallback must not run when primary succeeds"


def main() -> None:
    # Preserve and restore the module functions the chain tests monkeypatch.
    orig_fetch = odds.fetch_odds
    orig_fallback = fdo.fetch_odds_footballdata
    orig_loader = fdo._load_fixtures_rows
    try:
        fdo._load_fixtures_rows = lambda: (list(SAMPLE_ROWS), ["stubbed rows"])
        test_extra_league_returns_nothing()
        test_covered_league_parses()
        test_chain_falls_back_on_quota()
        # restore primary before the "prefers primary" case
        odds.fetch_odds = orig_fetch
        fdo.fetch_odds_footballdata = orig_fallback
        test_chain_prefers_primary()
    finally:
        odds.fetch_odds = orig_fetch
        fdo.fetch_odds_footballdata = orig_fallback
        fdo._load_fixtures_rows = orig_loader
    print("odds_fallback_test: OK")


if __name__ == "__main__":
    main()
