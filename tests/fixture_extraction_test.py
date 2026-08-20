"""
Tests for HR58 Stage A — fixture_extraction.py

Covers:
- ID403 verification per fixture
- Multi-source failover behavior
- Kickoff time preservation
- NO DATA — PENDING rows are preserved (never silently dropped)
- Immutable output artifact
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

# Import the module under test
from pipeline.fixture_extraction import (
    VerifiedFixture,
    StageAOutput,
    _verify_fixture,
    _determine_status,
    _resolve_kickoff_date,
    extract_fixtures_for_league,
    run_stage_a,
)


class TestKickoffResolution:
    """Tests for _resolve_kickoff_date helper."""

    def test_resolves_iso_timestamp(self):
        """Extracts YYYY-MM-DD from ISO timestamp."""
        assert _resolve_kickoff_date("2026-08-25T19:45:00Z") == "2026-08-25"
        assert _resolve_kickoff_date("2026-12-01T15:00:00+00:00") == "2026-12-01"

    def test_returns_none_for_none(self):
        """Returns None when kickoff_utc is None."""
        assert _resolve_kickoff_date(None) is None

    def test_returns_none_for_empty_string(self):
        """Returns None for empty string."""
        assert _resolve_kickoff_date("") is None

    def test_returns_none_for_malformed(self):
        """Returns None for malformed timestamp."""
        assert _resolve_kickoff_date("not-a-date") is None


class TestVerificationHelpers:
    """Tests for _verify_fixture and _determine_status."""

    @patch("pipeline.fixture_extraction.verify")
    def test_verify_fixture_calls_id403(self, mock_verify):
        """_verify_fixture calls ID403 verify with correct params."""
        mock_result = MagicMock()
        mock_result.tier.value = "VERIFIED"
        mock_result.note = "All good"
        mock_result.factors = {"F1": True, "F2": True, "F4": True}
        mock_verify.return_value = mock_result

        tier, note, factors = _verify_fixture(
            "Premier League", "Arsenal", "Chelsea", "thesportsdb.com", "T2",
            "2026-08-25T19:45:00Z"
        )

        assert tier == "VERIFIED"
        assert note == "All good"
        assert "F1" in factors
        assert "kickoff_utc" in factors
        assert factors["kickoff_utc"] == "2026-08-25T19:45:00Z"
        mock_verify.assert_called_once()

    def test_determine_status_verified(self):
        """VERIFIED tier with kickoff -> verified."""
        assert _determine_status("VERIFIED", "2026-08-25T19:45:00Z") == "verified"
        assert _determine_status("VERIFIED", None) == "verified"

    def test_determine_status_single_source(self):
        """SINGLE-SOURCE tier -> verified."""
        assert _determine_status("SINGLE-SOURCE", "2026-08-25T19:45:00Z") == "verified"
        assert _determine_status("SINGLE-SOURCE", None) == "verified"

    def test_determine_status_conflict(self):
        """CONFLICT tier -> pending (Architect must adjudicate)."""
        assert _determine_status("CONFLICT", "2026-08-25T19:45:00Z") == "pending"
        assert _determine_status("CONFLICT", None) == "pending"

    def test_determine_status_no_data(self):
        """NO-DATA tier -> no_data."""
        assert _determine_status("NO-DATA", "2026-08-25T19:45:00Z") == "no_data"
        assert _determine_status("NO-DATA", None) == "no_data"

    def test_determine_status_derived(self):
        """DERIVED tier -> no_data."""
        assert _determine_status("DERIVED", None) == "no_data"


class TestVerifiedFixture:
    """Tests for VerifiedFixture dataclass."""

    def test_to_dict_roundtrip(self):
        """VerifiedFixture serializes and deserializes correctly."""
        vf = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z",
            kickoff_date="2026-08-25",
            verification_tier="VERIFIED",
            verification_note="Cross-source agreement",
            verification_factors={"F1": True, "F2": True},
            source="thesportsdb.com",
            source_tier="T2",
            status="verified",
            flags=["extra check"],
        )

        d = vf.to_dict()
        vf2 = VerifiedFixture.from_dict(d)

        assert vf2.league == "Premier League"
        assert vf2.home_team == "Arsenal"
        assert vf2.away_team == "Chelsea"
        assert vf2.kickoff_utc == "2026-08-25T19:45:00Z"
        assert vf2.kickoff_date == "2026-08-25"
        assert vf2.verification_tier == "VERIFIED"
        assert vf2.verification_note == "Cross-source agreement"
        assert vf2.verification_factors == {"F1": True, "F2": True}
        assert vf2.source == "thesportsdb.com"
        assert vf2.source_tier == "T2"
        assert vf2.status == "verified"
        assert vf2.flags == ["extra check"]


class TestStageAOutput:
    """Tests for StageAOutput serialization and persistence."""

    def test_stage_a_output_roundtrip(self):
        """StageAOutput saves and loads correctly."""
        vf = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z",
            kickoff_date="2026-08-25",
            verification_tier="VERIFIED",
            verification_note="OK",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="verified",
        )

        output = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League"],
            fixtures=[vf],
            flags=["test flag"],
            stats={"total_fixtures": 1, "verified": 1},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_stage_a.json"
            output.save(path)

            loaded = StageAOutput.load(path)

            assert loaded.run_date == "2026-08-20"
            assert loaded.fixtures_season == "2627"
            assert loaded.leagues_scanned == ["Premier League"]
            assert len(loaded.fixtures) == 1
            assert loaded.fixtures[0].league == "Premier League"
            assert loaded.fixtures[0].home_team == "Arsenal"
            assert loaded.flags == ["test flag"]
            assert loaded.stats == {"total_fixtures": 1, "verified": 1}

    def test_stage_a_output_json_structure(self):
        """JSON output has expected structure."""
        output = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League", "La Liga"],
            fixtures=[],
            flags=[],
            stats={},
        )

        json_str = output.to_json()
        data = json.loads(json_str)

        assert data["run_date"] == "2026-08-20"
        assert data["fixtures_season"] == "2627"
        assert data["leagues_scanned"] == ["Premier League", "La Liga"]
        assert "fixtures" in data
        assert "flags" in data
        assert "stats" in data


class TestExtractFixturesForLeague:
    """Tests for extract_fixtures_for_league with mocked multi-source."""

    @patch("pipeline.fixture_extraction.get_fixtures")
    def test_successful_extraction(self, mock_get_fixtures):
        """Happy path: fixtures extracted and verified."""
        mock_get_fixtures.return_value = {
            "fixtures": [("Arsenal", "Chelsea"), ("Liverpool", "Man City")],
            "dates": {
                ("Arsenal", "Chelsea"): "2026-08-25T19:45:00Z",
                ("Liverpool", "Man City"): "2026-08-26T15:00:00Z",
            },
            "source": "thesportsdb",
            "skipped": 0,
        }

        with patch("pipeline.fixture_extraction.verify") as mock_verify:
            mock_result = MagicMock()
            mock_result.tier.value = "SINGLE-SOURCE"
            mock_result.note = "Single source only"
            mock_result.factors = {"F1": True, "F2": False, "F4": True}
            mock_verify.return_value = mock_result

            fixtures, flags = extract_fixtures_for_league(
                "Premier League", "2627", days_ahead=14
            )

        assert len(fixtures) == 2
        assert fixtures[0].league == "Premier League"
        assert fixtures[0].home_team == "Arsenal"
        assert fixtures[0].away_team == "Chelsea"
        assert fixtures[0].kickoff_utc == "2026-08-25T19:45:00Z"
        assert fixtures[0].kickoff_date == "2026-08-25"
        assert fixtures[0].verification_tier == "SINGLE-SOURCE"
        assert fixtures[0].status == "verified"

        mock_get_fixtures.assert_called_once()

    @patch("pipeline.fixture_extraction.get_fixtures")
    def test_no_fixtures_returns_no_data_flag(self, mock_get_fixtures):
        """When multi-source returns no fixtures, flag says NO DATA — PENDING."""
        mock_get_fixtures.return_value = {
            "fixtures": [],
            "dates": {},
            "source": "thesportsdb",
            "skipped": 0,
        }

        fixtures, flags = extract_fixtures_for_league("Premier League", "2627")

        assert fixtures == []
        assert any("NO DATA — PENDING" in f for f in flags)

    @patch("pipeline.fixture_extraction.get_fixtures")
    def test_skipped_rows_flagged(self, mock_get_fixtures):
        """Skipped/malformed rows from source are flagged."""
        mock_get_fixtures.return_value = {
            "fixtures": [("Arsenal", "Chelsea")],
            "dates": {("Arsenal", "Chelsea"): "2026-08-25T19:45:00Z"},
            "source": "thesportsdb",
            "skipped": 3,
        }

        with patch("pipeline.fixture_extraction.verify") as mock_verify:
            mock_result = MagicMock()
            mock_result.tier.value = "VERIFIED"
            mock_result.note = "OK"
            mock_result.factors = {}
            mock_verify.return_value = mock_result

            fixtures, flags = extract_fixtures_for_league("Premier League", "2627")

        assert len(fixtures) == 1
        assert any("3 fixture rows skipped" in f for f in flags)

    @patch("pipeline.fixture_extraction.get_fixtures")
    def test_backup_source_flagged(self, mock_get_fixtures):
        """When backup source used, flag indicates which source."""
        mock_get_fixtures.return_value = {
            "fixtures": [("Arsenal", "Chelsea")],
            "dates": {("Arsenal", "Chelsea"): "2026-08-25T19:45:00Z"},
            "source": "espn",
            "skipped": 0,
        }

        with patch("pipeline.fixture_extraction.verify") as mock_verify:
            mock_result = MagicMock()
            mock_result.tier.value = "SINGLE-SOURCE"
            mock_result.note = "OK"
            mock_result.factors = {}
            mock_verify.return_value = mock_result

            fixtures, flags = extract_fixtures_for_league("Premier League", "2627")

        assert len(fixtures) == 1
        assert any("fixtures via espn" in f for f in flags)

    @patch("pipeline.fixture_extraction.get_fixtures")
    def test_exception_triggers_sportybet_merge(self, mock_get_fixtures):
        """On primary source failure, attempts SportyBet cache merge."""
        mock_get_fixtures.side_effect = Exception("thesportsdb down")

        with patch("booking.bridge.load_sportybet_fixtures") as mock_load_sb, \
             patch("booking.bridge.sportybet_fixtures_to_pairs") as mock_pairs, \
             patch("pipeline.fixture_extraction.verify") as mock_verify:

            mock_pairs.return_value = [("Arsenal", "Chelsea")]
            mock_load_sb.return_value = [
                MagicMock(home_team="Arsenal", away_team="Chelsea", kickoff_utc="2026-08-25T19:45:00Z")
            ]
            mock_result = MagicMock()
            mock_result.tier.value = "SINGLE-SOURCE"
            mock_result.note = "OK"
            mock_result.factors = {}
            mock_verify.return_value = mock_result

            fixtures, flags = extract_fixtures_for_league("Premier League", "2627")

        assert len(fixtures) == 1
        assert fixtures[0].source == "sportybet_cache"
        assert any("merged from SportyBet cache" in f for f in flags)


class TestRunStageA:
    """Tests for run_stage_a integration."""

    @patch("pipeline.fixture_extraction.extract_fixtures_for_league")
    def test_run_stage_a_multiple_leagues(self, mock_extract):
        """Run stage A for multiple leagues aggregates correctly."""
        # Mock returns for 2 leagues
        vf1 = VerifiedFixture(
            league="Premier League", home_team="Arsenal", away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z", kickoff_date="2026-08-25",
            verification_tier="VERIFIED", verification_note="OK",
            verification_factors={}, source="thesportsdb.com", source_tier="T2",
            status="verified"
        )
        vf2 = VerifiedFixture(
            league="La Liga", home_team="Real Madrid", away_team="Barcelona",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING",
            verification_factors={}, source="thesportsdb.com", source_tier="T2",
            status="no_data"
        )

        mock_extract.side_effect = [
            ([vf1], ["Premier League: OK"]),
            ([vf2], ["La Liga: NO DATA — PENDING"]),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pipeline.fixture_extraction.STAGE_A_OUTPUT_DIR", Path(tmpdir)):
                output = run_stage_a(
                    season="2526",
                    fixtures_season="2627",
                    leagues=["Premier League", "La Liga"],
                )

        assert output.run_date == date.today().isoformat()
        assert output.fixtures_season == "2627"
        assert output.leagues_scanned == ["Premier League", "La Liga"]
        assert len(output.fixtures) == 2
        assert output.stats["total_fixtures"] == 2
        assert output.stats["verified"] == 1
        assert output.stats["no_data"] == 1
        assert output.stats["leagues_scanned"] == 2
        assert output.stats["leagues_with_fixtures"] == 2

    @patch("pipeline.fixture_extraction.extract_fixtures_for_league")
    def test_run_stage_a_no_data_fixtures_preserved(self, mock_extract):
        """NO DATA fixtures are preserved in output (not dropped)."""
        # League with NO DATA still produces a fixture entry
        vf_no_data = VerifiedFixture(
            league="EFL Cup", home_team="Team A", away_team="Team B",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING: no history",
            verification_factors={}, source="thesportsdb.com", source_tier="T2",
            status="no_data"
        )

        mock_extract.return_value = ([vf_no_data], ["EFL Cup: NO DATA — PENDING"])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pipeline.fixture_extraction.STAGE_A_OUTPUT_DIR", Path(tmpdir)):
                output = run_stage_a(
                    season="2526",
                    fixtures_season="2627",
                    leagues=["EFL Cup"],
                )

        assert len(output.fixtures) == 1
        assert output.fixtures[0].league == "EFL Cup"
        assert output.fixtures[0].verification_tier == "NO-DATA"
        assert output.fixtures[0].status == "no_data"
        assert "NO DATA — PENDING" in output.fixtures[0].verification_note

    @patch("pipeline.fixture_extraction.extract_fixtures_for_league")
    def test_run_stage_a_saves_artifact(self, mock_extract):
        """Stage A saves immutable JSON artifact."""
        vf = VerifiedFixture(
            league="Premier League", home_team="Arsenal", away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z", kickoff_date="2026-08-25",
            verification_tier="VERIFIED", verification_note="OK",
            verification_factors={}, source="thesportsdb.com", source_tier="T2",
            status="verified"
        )
        mock_extract.return_value = ([vf], [])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pipeline.fixture_extraction.STAGE_A_OUTPUT_DIR", Path(tmpdir)):
                output = run_stage_a(
                    season="2526",
                    fixtures_season="2627",
                    leagues=["Premier League"],
                )

            # Check file was created
            files = list(Path(tmpdir).glob("fixtures_*.json"))
            assert len(files) == 1

            # Verify content
            loaded = StageAOutput.load(files[0])
            assert loaded.run_date == output.run_date
            assert loaded.fixtures_season == "2627"
            assert len(loaded.fixtures) == 1
            assert loaded.fixtures[0].home_team == "Arsenal"


class TestImmutableOutput:
    """Tests verifying the immutable output contract for Stage B."""

    def test_no_data_fixtures_not_dropped(self):
        """Contract: NO DATA fixtures appear in output, never silently dropped."""
        vf = VerifiedFixture(
            league="Test League", home_team="A", away_team="B",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING",
            verification_factors={}, source="test", source_tier="T2",
            status="no_data"
        )

        output = StageAOutput(
            run_date="2026-08-20", fixtures_season="2627",
            leagues_scanned=["Test League"], fixtures=[vf],
            flags=[], stats={"total_fixtures": 1, "no_data": 1}
        )

        # Every league scanned should have at least one fixture entry
        scanned_leagues = set(output.leagues_scanned)
        fixture_leagues = set(f.league for f in output.fixtures)
        assert scanned_leagues == fixture_leagues, "No league should be dropped"

    def test_verification_tiers_preserved(self):
        """All verification tiers preserved in output for Stage B."""
        tiers = ["VERIFIED", "SINGLE-SOURCE", "CONFLICT", "NO-DATA", "DERIVED"]
        fixtures = [
            VerifiedFixture(
                league="Test", home_team=f"H{i}", away_team=f"A{i}",
                kickoff_utc=None, kickoff_date=None,
                verification_tier=t, verification_note=t,
                verification_factors={}, source="test", source_tier="T2",
                status="verified" if t in ("VERIFIED", "SINGLE-SOURCE") else
                       "pending" if t == "CONFLICT" else "no_data"
            )
            for i, t in enumerate(tiers)
        ]

        output = StageAOutput(
            run_date="2026-08-20", fixtures_season="2627",
            leagues_scanned=["Test"], fixtures=fixtures,
            flags=[], stats={}
        )

        output_tiers = [f.verification_tier for f in output.fixtures]
        assert output_tiers == tiers

    def test_kickoff_times_preserved(self):
        """Kickoff times preserved for Stage B settlement."""
        vf = VerifiedFixture(
            league="Test", home_team="A", away_team="B",
            kickoff_utc="2026-08-25T19:45:00Z", kickoff_date="2026-08-25",
            verification_tier="VERIFIED", verification_note="OK",
            verification_factors={}, source="test", source_tier="T2",
            status="verified"
        )

        output = StageAOutput(
            run_date="2026-08-20", fixtures_season="2627",
            leagues_scanned=["Test"], fixtures=[vf],
            flags=[], stats={}
        )

        assert output.fixtures[0].kickoff_utc == "2026-08-25T19:45:00Z"
        assert output.fixtures[0].kickoff_date == "2026-08-25"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])