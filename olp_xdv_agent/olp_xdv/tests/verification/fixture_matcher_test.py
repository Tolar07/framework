"""Tests for fixture_matcher.py - cross-source fixture matching for ID403 verification."""


from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from verification.fixture_matcher import (
    normalize_team_name,
    normalize_kickoff,
    match_fixtures,
    unmatched_report,
    SourceFixture,
    MatchedFixture,
    VerificationTier,
)


def test_normalize_team_name_basic():
    """Test basic team name normalization."""
    assert normalize_team_name("Man Utd") == "manchester united"
    assert normalize_team_name("Man City") == "manchester city"
    assert normalize_team_name("Spurs") == "tottenham hotspur"
    assert normalize_team_name("Wolves") == "wolverhampton wanderers"


def test_normalize_team_name_suffixes():
    """Test removal of common suffixes."""
    assert normalize_team_name("Aston Villa FC") == "aston villa"
    assert normalize_team_name("Inter Milan CF") == "inter milan"
    assert normalize_team_name("Juventus SC") == "juventus"
    assert normalize_team_name("PSG AFC") == "paris saint-germain"  # PSG is in aliases


def test_normalize_team_name_punctuation_and_whitespace():
    """Test punctuation and whitespace normalization."""
    assert normalize_team_name("  Manchester  United  ") == "manchester united"
    assert normalize_team_name("Manchester-United!") == "manchester united"
    assert normalize_team_name("Manchester.United") == "manchester united"


def test_normalize_kickoff():
    """Test kickoff time normalization."""
    # Test various formats that should normalize to the same time
    # Note: Z is treated as UTC and converted to local time (BST = UTC+1)
    assert normalize_kickoff("2026-09-06T14:30:00Z") == "2026-09-06T15:30:00"
    assert normalize_kickoff("2026-09-06 14:30:00") == "2026-09-06T14:30:00"
    # For time-only strings, we expect today's date with the given time
    today = datetime.now().strftime("%Y-%m-%d")
    assert normalize_kickoff("14:30") == f"{today}T14:30:00"
    assert normalize_kickoff("2026-09-06T14:30:00") == "2026-09-06T14:30:00"


def test_match_fixtures_exact_match():
    """Test matching when fixtures are identical after normalization."""
    source_a = [
        SourceFixture("Man Utd", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "1"})
    ]
    source_b = [
        SourceFixture("Manchester United", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "A1"})
    ]

    result = match_fixtures({"source_a": source_a, "source_b": source_b})

    # Should have one matched fixture (VERIFIED)
    assert len(result) == 1
    assert result[0].tier == VerificationTier.VERIFIED
    assert result[0].source_count == 2
    assert result[0].home == "manchester united"
    assert result[0].away == "liverpool"
    assert "source_a" in result[0].sources
    assert "source_b" in result[0].sources


def test_match_fixtures_no_match_different_teams():
    """Test that different teams don't match."""
    source_a = [
        SourceFixture("Man Utd", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "1"})
    ]
    source_b = [
        SourceFixture("Arsenal", "Chelsea", "Premier League", "2026-09-06T14:30:00", {"id": "A1"})
    ]

    result = match_fixtures({"source_a": source_a, "source_b": source_b})

    # Should have two single-source fixtures
    assert len(result) == 2
    assert result[0].tier == VerificationTier.SINGLE_SOURCE
    assert result[1].tier == VerificationTier.SINGLE_SOURCE
    assert result[0].source_count == 1
    assert result[1].source_count == 1


def test_match_fixtures_no_match_different_time():
    """Test that different kickoff times beyond tolerance create CONFLICT."""
    source_a = [
        SourceFixture("Man Utd", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "1"})
    ]
    source_b = [
        SourceFixture("Manchester United", "Liverpool", "Premier League", "2026-09-06T16:30:00", {"id": "A1"})
    ]

    result = match_fixtures({"source_a": source_a, "source_b": source_b})

    # Should have one CONFLICT fixture (same teams, different times > 90 min tolerance)
    assert len(result) == 1
    assert result[0].tier == VerificationTier.CONFLICT
    assert result[0].source_count == 2
    assert result[0].kickoff_utc is None
    assert result[0].conflict_detail is not None
    assert len(result[0].conflict_detail) == 2


def test_match_fixtures_mixed():
    """Test matching with some matches and some unmatched."""
    source_a = [
        SourceFixture("Man Utd", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "1"}),
        SourceFixture("Arsenal", "Chelsea", "Premier League", "2026-09-06T15:00:00", {"id": "2"}),
        SourceFixture("Man City", "Tottenham", "Premier League", "2026-09-06T16:30:00", {"id": "3"}),
    ]
    source_b = [
        SourceFixture("Manchester United", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "A1"}),
        SourceFixture("Arsenal", "Chelsea", "Premier League", "2026-09-06T15:00:00", {"id": "A2"}),
        SourceFixture("Newcastle", "Brighton", "Premier League", "2026-09-06T17:00:00", {"id": "A3"}),
    ]

    result = match_fixtures({"source_a": source_a, "source_b": source_b})

    # Should have 4 MatchedFixture objects: 2 VERIFIED, 2 SINGLE_SOURCE
    verified = [mf for mf in result if mf.tier == VerificationTier.VERIFIED]
    singles = [mf for mf in result if mf.tier == VerificationTier.SINGLE_SOURCE]
    assert len(verified) == 2
    assert len(singles) == 2

    # Check the verified pairs
    verified_homes = {mf.home for mf in verified}
    assert "manchester united" in verified_homes
    assert "arsenal" in verified_homes

    # Check the single source
    single_homes = {mf.home for mf in singles}
    assert "manchester city" in single_homes
    # Normalised, not raw: TEAM_ALIASES maps "newcastle" -> "newcastle united",
    # and normalize_team_name applies the alias table, so the bucket key is the
    # canonical club name. This assertion previously expected the raw form and
    # could never have passed against this alias table.
    assert "newcastle united" in single_homes


def test_unmatched_report():
    """Test the unmatched report generation."""
    # Create mock MatchedFixture objects
    match_result = [
        MatchedFixture(
            home="manchester united",
            away="liverpool",
            league="Premier League",
            kickoff_utc=datetime(2026, 9, 6, 14, 30),
            sources={
                "source_a": SourceFixture("Man Utd", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "1"}),
                "source_b": SourceFixture("Manchester United", "Liverpool", "Premier League", "2026-09-06T14:30:00", {"id": "A1"}),
            },
            tier=VerificationTier.VERIFIED,
        ),
        MatchedFixture(
            home="arsenal",
            away="chelsea",
            league="Premier League",
            kickoff_utc=datetime(2026, 9, 6, 15, 0),
            sources={
                "source_a": SourceFixture("Arsenal", "Chelsea", "Premier League", "2026-09-06T15:00:00", {"id": "2"}),
            },
            tier=VerificationTier.SINGLE_SOURCE,
        ),
        MatchedFixture(
            home="manchester city",
            away="tottenham",
            league="Premier League",
            kickoff_utc=datetime(2026, 9, 6, 16, 30),
            sources={
                "source_a": SourceFixture("Man City", "Tottenham", "Premier League", "2026-09-06T16:30:00", {"id": "3"}),
            },
            tier=VerificationTier.SINGLE_SOURCE,
        ),
        MatchedFixture(
            home="newcastle",
            away="brighton",
            league="Premier League",
            kickoff_utc=datetime(2026, 9, 6, 17, 0),
            sources={
                "source_b": SourceFixture("Newcastle", "Brighton", "Premier League", "2026-09-06T17:00:00", {"id": "A2"}),
            },
            tier=VerificationTier.SINGLE_SOURCE,
        ),
    ]

    report = unmatched_report(match_result)

    # Check totals
    assert report["total_fixtures"] == 4
    assert report["verified_2plus"] == 1
    assert report["single_source"] == 3
    assert report["conflict"] == 0

    # Check unmatched lists
    assert len(report["single_source_detail"]) == 3
    assert len(report["conflict_detail"]) == 0


if __name__ == "__main__":
    # Run tests manually if needed
    test_normalize_team_name_basic()
    test_normalize_team_name_suffixes()
    test_normalize_team_name_punctuation_and_whitespace()
    test_normalize_kickoff()
    test_match_fixtures_exact_match()
    test_match_fixtures_no_match_different_teams()
    test_match_fixtures_no_match_different_time()
    test_match_fixtures_mixed()
    test_unmatched_report()
    print("All fixture matcher tests passed!")