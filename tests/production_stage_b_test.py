"""
Tests for HR58 Stage B — production_stage_b.py

Covers:
- Stage A output loading
- VerifiedFixture to BoardFixture conversion
- 4-layer output generation (Layer 2 → Layer 1 → Acca Route → THE PICK)
- Vehicle constraint: 2 accas + 1 SLV
- ID420 watchlist preservation
- NO DATA — PENDING rows preserved (never silently dropped)
- Immutable output artifact
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

from pipeline.production_stage_b import (
    _verified_fixture_to_board_fixture,
    _load_stage_a_output,
    _build_acca_route,
    _select_the_pick,
    run_stage_b,
    render_stage_b_output,
    ProductionLayer2,
    ProductionLayer1,
    ProductionAccaRoute,
    ProductionThePick,
    StageBOutput,
)
from pipeline.fixture_extraction import VerifiedFixture, StageAOutput
from engine.acca import Acca, AccaLeg, ProductionBets
from output.produce_bet import BoardFixture
from verification.id403 import VerificationResult, Tier


class TestStageALoading:
    """Tests for loading Stage A output."""

    def test_load_stage_a_output(self):
        """Stage A output loads correctly from JSON."""
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
        stage_a = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League"],
            fixtures=[vf],
            flags=[],
            stats={"total_fixtures": 1},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stage_a.json"
            stage_a.save(path)
            loaded = _load_stage_a_output(path)

            assert loaded.run_date == "2026-08-20"
            assert loaded.fixtures_season == "2627"
            assert len(loaded.fixtures) == 1
            assert loaded.fixtures[0].home_team == "Arsenal"


class TestVerifiedFixtureToBoardFixture:
    """Tests for converting VerifiedFixture to BoardFixture."""

    def test_verified_fixture_conversion(self):
        """Verified fixture converts to BoardFixture with correct fields."""
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
        )

        bf = _verified_fixture_to_board_fixture(vf, today="2026-08-25")

        assert bf.fixture == "Arsenal v Chelsea (Premier League)"
        assert bf.kickoff_date == "2026-08-25"
        assert bf.verification.tier == Tier.VERIFIED
        assert bf.verification.note == "Cross-source agreement"
        assert bf.on_deploy_shortlist is True  # verified + today + deploy eligible league
        assert bf.rejection_reason is None
        assert bf.model_engine == "T2"

    def test_no_data_fixture_conversion(self):
        """NO DATA fixture converts with rejection reason and no shortlist."""
        vf = VerifiedFixture(
            league="EFL Cup",
            home_team="Team A",
            away_team="Team B",
            kickoff_utc=None,
            kickoff_date=None,
            verification_tier="NO-DATA",
            verification_note="NO DATA — PENDING: no history",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="no_data",
        )

        bf = _verified_fixture_to_board_fixture(vf, today="2026-08-25")

        assert bf.fixture == "Team A v Team B (EFL Cup)"
        assert bf.kickoff_date is None
        assert bf.verification.tier == Tier.NO_DATA
        assert bf.on_deploy_shortlist is False
        assert bf.rejection_reason is not None
        assert "NO DATA — PENDING" in bf.rejection_reason

    def test_conflict_fixture_conversion(self):
        """CONFLICT fixture converts with pending status and rejection reason."""
        vf = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z",
            kickoff_date="2026-08-25",
            verification_tier="CONFLICT",
            verification_note="Sources disagree",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="pending",
        )

        bf = _verified_fixture_to_board_fixture(vf, today="2026-08-25")

        assert bf.verification.tier == Tier.CONFLICT
        assert bf.on_deploy_shortlist is False
        assert bf.rejection_reason is not None
        assert "CONFLICT" in bf.rejection_reason
        assert "Architect must adjudicate" in bf.rejection_reason

    def test_not_today_fixture_not_shortlisted(self):
        """Fixture not kicking off today is not on deploy shortlist."""
        vf = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-26T19:45:00Z",
            kickoff_date="2026-08-26",
            verification_tier="VERIFIED",
            verification_note="OK",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="verified",
        )

        bf = _verified_fixture_to_board_fixture(vf, today="2026-08-25")

        assert bf.on_deploy_shortlist is False  # Not today


class TestAccaRouteBuilding:
    """Tests for building the Acca Route with vehicle constraint."""

    def _make_leg(self, fixture: str, league: str, market: str, price: float,
                   prob: float, edge: float, ev: float, status: str = "capital") -> AccaLeg:
        return AccaLeg(
            fixture=fixture,
            league=league,
            market_key=market,
            market_name=market,
            price=price,
            prob=prob,
            ev=ev,
            edge=edge,
            status=status,
        )

    def test_build_acca_route_two_accas_one_slv(self):
        """Acca Route builds with 2 accas + 1 SLV from production bets."""
        # Create production bets with enough legs for 2 accas + singles
        legs_a = [
            self._make_leg("A v B", "PL", "HOME", 1.50, 0.70, 0.05, 0.10),
            self._make_leg("C v D", "PL", "DRAW", 1.60, 0.65, 0.04, 0.08),
            self._make_leg("E v F", "PL", "AWAY", 1.45, 0.75, 0.06, 0.12),
            self._make_leg("G v H", "PL", "OVER_25", 1.55, 0.68, 0.03, 0.06),
        ]
        legs_b = [
            self._make_leg("I v J", "LL", "HOME", 1.50, 0.70, 0.05, 0.10),
            self._make_leg("K v L", "LL", "DRAW", 1.60, 0.65, 0.04, 0.08),
            self._make_leg("M v N", "LL", "BTTS", 1.55, 0.68, 0.03, 0.06),
            self._make_leg("O v P", "LL", "DC", 1.45, 0.75, 0.06, 0.12),
        ]
        singles = [
            self._make_leg("Q v R", "SA", "HOME", 1.50, 0.70, 0.05, 0.10),
            self._make_leg("S v T", "SA", "DRAW", 1.60, 0.65, 0.04, 0.08),
        ]
        watchlist = [
            self._make_leg("U v V", "PL", "AWAY", 3.50, 0.30, 0.10, 0.05, status="watchlist"),
        ]

        acca_a = Acca(label="Acca A", legs=legs_a, combined_odds=5.5, combined_prob=0.15)
        acca_b = Acca(label="Acca B", legs=legs_b, combined_odds=5.2, combined_prob=0.14)

        production = ProductionBets(
            acca_a=acca_a,
            split_accas=[acca_b],
            singles=singles,
            watchlist=watchlist,
        )

        acca_route = _build_acca_route(production)

        assert acca_route.acca_a is not None
        assert acca_route.acca_a.label == "Acca A"
        assert acca_route.acca_a.n_legs == 4

        assert acca_route.acca_b is not None
        assert acca_route.acca_b.label == "Acca B"
        assert acca_route.acca_b.n_legs == 4

        assert acca_route.slv is not None
        assert acca_route.slv.fixture == "Q v R"  # Highest edge single

        assert len(acca_route.watchlist) == 1
        assert acca_route.watchlist[0].status == "watchlist"

    def test_build_acca_route_insufficient_legs(self):
        """Acca Route handles insufficient legs gracefully."""
        legs_a = [
            self._make_leg("A v B", "PL", "HOME", 1.50, 0.70, 0.05, 0.10),
        ]
        production = ProductionBets(
            acca_a=Acca(label="Acca A", legs=legs_a, combined_odds=1.5, combined_prob=0.70),
            split_accas=[],
            singles=[],
            watchlist=[],
        )

        acca_route = _build_acca_route(production)

        assert acca_route.acca_a is not None
        assert acca_route.acca_a.n_legs == 1
        assert acca_route.acca_b is None
        assert acca_route.slv is None


class TestThePickSelection:
    """Tests for THE PICK final selection."""

    def _make_leg(self, fixture: str, league: str, market: str, price: float,
                   prob: float, edge: float, ev: float) -> AccaLeg:
        return AccaLeg(
            fixture=fixture,
            league=league,
            market_key=market,
            market_name=market,
            price=price,
            prob=prob,
            ev=ev,
            edge=edge,
            status="capital",
        )

    def test_the_pick_prefers_acca_a_first_leg(self):
        """THE PICK selects Acca A first leg when available."""
        acca_a = Acca(label="Acca A", legs=[
            self._make_leg("Best v Match", "PL", "HOME", 1.50, 0.70, 0.05, 0.10),
            self._make_leg("Second v Leg", "PL", "DRAW", 1.60, 0.65, 0.04, 0.08),
        ], combined_odds=2.4, combined_prob=0.45)
        acca_b = Acca(label="Acca B", legs=[
            self._make_leg("Third v Leg", "LL", "HOME", 1.50, 0.70, 0.05, 0.10),
        ], combined_odds=1.5, combined_prob=0.70)
        slv = self._make_leg("Single v Best", "SA", "HOME", 1.50, 0.70, 0.05, 0.10)

        acca_route = ProductionAccaRoute(
            acca_a=acca_a,
            acca_b=acca_b,
            slv=slv,
            watchlist=[],
        )

        the_pick = _select_the_pick(acca_route)

        assert the_pick.leg is not None
        assert the_pick.leg.fixture == "Best v Match"
        assert "Acca A" in the_pick.rationale

    def test_the_pick_falls_back_to_acca_b(self):
        """THE PICK selects Acca B first leg when Acca A empty."""
        acca_b = Acca(label="Acca B", legs=[
            self._make_leg("Third v Leg", "LL", "HOME", 1.50, 0.70, 0.05, 0.10),
        ], combined_odds=1.5, combined_prob=0.70)
        slv = self._make_leg("Single v Best", "SA", "HOME", 1.50, 0.70, 0.05, 0.10)

        acca_route = ProductionAccaRoute(
            acca_a=None,
            acca_b=acca_b,
            slv=slv,
            watchlist=[],
        )

        the_pick = _select_the_pick(acca_route)

        assert the_pick.leg is not None
        assert the_pick.leg.fixture == "Third v Leg"
        assert "Acca B" in the_pick.rationale

    def test_the_pick_falls_back_to_slv(self):
        """THE PICK selects SLV when no accas."""
        slv = self._make_leg("Single v Best", "SA", "HOME", 1.50, 0.70, 0.05, 0.10)

        acca_route = ProductionAccaRoute(
            acca_a=None,
            acca_b=None,
            slv=slv,
            watchlist=[],
        )

        the_pick = _select_the_pick(acca_route)

        assert the_pick.leg is not None
        assert the_pick.leg.fixture == "Single v Best"
        assert "SLV" in the_pick.rationale

    def test_the_pick_none_when_no_legs(self):
        """THE PICK is None when no capital-eligible legs exist."""
        acca_route = ProductionAccaRoute(
            acca_a=None,
            acca_b=None,
            slv=None,
            watchlist=[],
        )

        the_pick = _select_the_pick(acca_route)

        assert the_pick.leg is None
        assert "No capital-eligible" in the_pick.rationale


class TestRunStageBIntegration:
    """Integration tests for run_stage_b (mocked dependencies)."""

    @patch("pipeline.production_stage_b._enrich_fixtures_with_models")
    @patch("pipeline.production_stage_b.build_production_bets")
    @patch("pipeline.production_stage_b._load_stage_a_output")
    def test_run_stage_b_basic(self, mock_load, mock_build_bets, mock_enrich):
        """run_stage_b loads Stage A, enriches, builds bets, produces 4 layers."""
        # Setup Stage A
        vf = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z",
            kickoff_date=date.today().isoformat(),
            verification_tier="VERIFIED",
            verification_note="OK",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="verified",
        )
        stage_a = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League"],
            fixtures=[vf],
            flags=[],
            stats={"total_fixtures": 1},
        )
        mock_load.return_value = stage_a

        # Setup enriched board
        bf = BoardFixture(
            fixture="Arsenal v Chelsea (Premier League)",
            probs=None,
            verification=VerificationResult(tier=Tier.VERIFIED, value="Arsenal v Chelsea", note="OK", factors={}),
            on_deploy_shortlist=True,
            kickoff_date=date.today().isoformat(),
        )
        mock_enrich.return_value = ([bf], [])

        # Setup production bets
        leg = AccaLeg(
            fixture="Arsenal v Chelsea",
            league="Premier League",
            market_key="HOME",
            market_name="Arsenal to win",
            price=1.50,
            prob=0.70,
            ev=0.05,
            edge=0.05,
            status="capital",
        )
        prod = ProductionBets(
            acca_a=Acca(label="Acca A", legs=[leg], combined_odds=1.5, combined_prob=0.70),
            split_accas=[],
            singles=[],
            watchlist=[],
        )
        mock_build_bets.return_value = prod

        with tempfile.TemporaryDirectory() as tmpdir:
            stage_a_path = Path(tmpdir) / "stage_a.json"
            stage_a.save(stage_a_path)

            output = run_stage_b(stage_a_path)

            assert output.run_date == date.today().isoformat()
            assert output.fixtures_season == "2627"
            assert output.stage_a_run_date == "2026-08-20"
            assert len(output.layer2.fixtures) == 1
            assert output.layer1.today_fixtures == [bf]
            assert output.acca_route.acca_a is not None
            assert output.the_pick.leg is not None

    def test_run_stage_b_preserves_no_data_fixtures(self):
        """NO DATA fixtures from Stage A are preserved in Layer 2."""
        vf_verified = VerifiedFixture(
            league="Premier League",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-08-25T19:45:00Z",
            kickoff_date=date.today().isoformat(),
            verification_tier="VERIFIED",
            verification_note="OK",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="verified",
        )
        vf_no_data = VerifiedFixture(
            league="EFL Cup",
            home_team="Team A",
            away_team="Team B",
            kickoff_utc=None,
            kickoff_date=None,
            verification_tier="NO-DATA",
            verification_note="NO DATA — PENDING: no history",
            verification_factors={},
            source="thesportsdb.com",
            source_tier="T2",
            status="no_data",
        )
        stage_a = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League", "EFL Cup"],
            fixtures=[vf_verified, vf_no_data],
            flags=[],
            stats={"total_fixtures": 2, "no_data": 1},
        )

        with patch("pipeline.production_stage_b._load_stage_a_output", return_value=stage_a), \
             patch("pipeline.production_stage_b._enrich_fixtures_with_models", side_effect=lambda board, *a, **k: (board, [])), \
             patch("pipeline.production_stage_b.build_production_bets", return_value=ProductionBets(
                 acca_a=None, split_accas=[], singles=[], watchlist=[])), \
             tempfile.TemporaryDirectory() as tmpdir:

            stage_a_path = Path(tmpdir) / "stage_a.json"
            stage_a.save(stage_a_path)

            output = run_stage_b(stage_a_path)

            # Both fixtures should be in Layer 2
            assert output.stats["total_fixtures_enriched"] == 2
            assert output.stats["no_data_fixtures"] == 1

            # Check Layer 2 has both fixtures
            fixture_leagues = {bf.fixture.split(" (")[-1].rstrip(")") for bf in output.layer2.fixtures}
            assert "Premier League" in fixture_leagues
            assert "EFL Cup" in fixture_leagues


class TestRenderStageBOutput:
    """Tests for rendering the 4-layer output."""

    def _make_leg(self, fixture: str, league: str, market: str, price: float,
                   prob: float, edge: float, ev: float, status: str = "capital") -> AccaLeg:
        return AccaLeg(
            fixture=fixture,
            league=league,
            market_key=market,
            market_name=market,
            price=price,
            prob=prob,
            ev=ev,
            edge=edge,
            status=status,
        )

    def test_render_four_layers_order(self):
        """Render output has correct 4-layer order: L2 → L1 → Acca Route → THE PICK."""
        leg = self._make_leg("Arsenal v Chelsea", "PL", "HOME", 1.50, 0.70, 0.05, 0.10)

        output = StageBOutput(
            run_date="2026-08-25",
            fixtures_season="2627",
            stage_a_run_date="2026-08-20",
            layer2=ProductionLayer2(
                fixtures=[],
                compact="LAYER 2 COMPACT",
                full_scan="LAYER 2 FULL SCAN",
            ),
            layer1=ProductionLayer1(
                today_fixtures=[],
                table="LAYER 1 TABLE",
            ),
            acca_route=ProductionAccaRoute(
                acca_a=Acca(label="Acca A", legs=[leg], combined_odds=1.5, combined_prob=0.70),
                acca_b=Acca(label="Acca B", legs=[], combined_odds=1.0, combined_prob=1.0),
                slv=self._make_leg("SLV Fixture", "LL", "DRAW", 1.60, 0.65, 0.04, 0.08),
                watchlist=[self._make_leg("Watch v List", "PL", "AWAY", 3.50, 0.30, 0.10, 0.05, status="watchlist")],
            ),
            the_pick=ProductionThePick(
                leg=leg,
                rationale="Top leg of headline Acca A",
            ),
            data_flags=[],
            stats={},
        )

        rendered = render_stage_b_output(output)

        # Check order
        l2_idx = rendered.find("LAYER 2")
        l1_idx = rendered.find("LAYER 1")
        acca_idx = rendered.find("ACCA ROUTE")
        pick_idx = rendered.find("THE PICK")

        assert l2_idx < l1_idx < acca_idx < pick_idx, "Layers must be in order: L2 → L1 → Acca Route → THE PICK"

        # Check content
        assert "LAYER 2 COMPACT" in rendered
        assert "LAYER 2 FULL SCAN" in rendered
        assert "LAYER 1 TABLE" in rendered
        assert "Acca A" in rendered
        assert "Acca B" in rendered
        assert "SLV" in rendered
        assert "WATCHLIST" in rendered
        assert "Top leg of headline Acca A" in rendered
        assert "Arsenal v Chelsea" in rendered


class TestStageBOutputSerialization:
    """Tests for StageBOutput JSON serialization."""

    def test_stage_b_output_to_json(self):
        """StageBOutput serializes to JSON with correct structure."""
        output = StageBOutput(
            run_date="2026-08-25",
            fixtures_season="2627",
            stage_a_run_date="2026-08-20",
            layer2=ProductionLayer2(fixtures=[], compact="", full_scan=""),
            layer1=ProductionLayer1(today_fixtures=[], table=""),
            acca_route=ProductionAccaRoute(),
            the_pick=ProductionThePick(),
            data_flags=[],
            stats={"test": 1},
        )

        json_str = output.to_json()
        data = json.loads(json_str)

        assert data["run_date"] == "2026-08-25"
        assert data["fixtures_season"] == "2627"
        assert data["stage_a_run_date"] == "2026-08-20"
        assert "layer2" in data
        assert "layer1" in data
        assert "acca_route" in data
        assert "the_pick" in data
        assert data["stats"]["test"] == 1

    def test_stage_b_output_save_load(self):
        """StageBOutput saves and loads from file."""
        output = StageBOutput(
            run_date="2026-08-25",
            fixtures_season="2627",
            stage_a_run_date="2026-08-20",
            layer2=ProductionLayer2(fixtures=[], compact="", full_scan=""),
            layer1=ProductionLayer1(today_fixtures=[], table=""),
            acca_route=ProductionAccaRoute(),
            the_pick=ProductionThePick(),
            data_flags=[],
            stats={},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stage_b.json"
            output.save(path)

            # Load raw JSON
            loaded = json.loads(path.read_text())
            assert loaded["run_date"] == "2026-08-25"
            assert loaded["fixtures_season"] == "2627"


class TestNoDataPreservationContract:
    """Tests verifying the NO DATA — PENDING preservation contract."""

    def test_all_stage_a_leagues_in_layer2(self):
        """Every league scanned in Stage A appears in Layer 2 output."""
        vf1 = VerifiedFixture(
            league="Premier League", home_team="A", away_team="B",
            kickoff_utc="2026-08-25T19:45:00Z", kickoff_date="2026-08-25",
            verification_tier="VERIFIED", verification_note="OK",
            verification_factors={}, source="test", source_tier="T2",
            status="verified",
        )
        vf2 = VerifiedFixture(
            league="La Liga", home_team="C", away_team="D",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING",
            verification_factors={}, source="test", source_tier="T2",
            status="no_data",
        )
        vf3 = VerifiedFixture(
            league="Serie A", home_team="E", away_team="F",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING",
            verification_factors={}, source="test", source_tier="T2",
            status="no_data",
        )
        stage_a = StageAOutput(
            run_date="2026-08-20",
            fixtures_season="2627",
            leagues_scanned=["Premier League", "La Liga", "Serie A"],
            fixtures=[vf1, vf2, vf3],
            flags=[],
            stats={"total_fixtures": 3, "no_data": 2},
        )

        with patch("pipeline.production_stage_b._load_stage_a_output", return_value=stage_a), \
             patch("pipeline.production_stage_b._enrich_fixtures_with_models", side_effect=lambda board, *a, **k: (board, [])), \
             patch("pipeline.production_stage_b.build_production_bets", return_value=ProductionBets(
                 acca_a=None, split_accas=[], singles=[], watchlist=[])), \
             tempfile.TemporaryDirectory() as tmpdir:

            stage_a_path = Path(tmpdir) / "stage_a.json"
            stage_a.save(stage_a_path)

            output = run_stage_b(stage_a_path)

            # All 3 leagues must be in Layer 2
            layer2_leagues = {bf.fixture.split(" (")[-1].rstrip(")") for bf in output.layer2.fixtures}
            assert layer2_leagues == {"Premier League", "La Liga", "Serie A"}

    def test_no_data_fixtures_not_dropped(self):
        """Contract: NO DATA fixtures appear in Layer 2, never silently dropped."""
        vf_no_data = VerifiedFixture(
            league="Test League", home_team="A", away_team="B",
            kickoff_utc=None, kickoff_date=None,
            verification_tier="NO-DATA", verification_note="NO DATA — PENDING",
            verification_factors={}, source="test", source_tier="T2",
            status="no_data",
        )
        stage_a = StageAOutput(
            run_date="2026-08-20", fixtures_season="2627",
            leagues_scanned=["Test League"], fixtures=[vf_no_data],
            flags=[], stats={"total_fixtures": 1, "no_data": 1},
        )

        with patch("pipeline.production_stage_b._load_stage_a_output", return_value=stage_a), \
             patch("pipeline.production_stage_b._enrich_fixtures_with_models", side_effect=lambda board, *a, **k: (board, [])), \
             patch("pipeline.production_stage_b.build_production_bets", return_value=ProductionBets(
                 acca_a=None, split_accas=[], singles=[], watchlist=[])), \
             tempfile.TemporaryDirectory() as tmpdir:

            stage_a_path = Path(tmpdir) / "stage_a.json"
            stage_a.save(stage_a_path)

            output = run_stage_b(stage_a_path)

            # The NO DATA fixture must be in Layer 2
            assert len(output.layer2.fixtures) == 1
            assert output.layer2.fixtures[0].fixture == "A v B (Test League)"
            assert output.layer2.fixtures[0].rejection_reason is not None
            assert "NO DATA — PENDING" in output.layer2.fixtures[0].rejection_reason

    def test_verification_tiers_preserved_to_layer2(self):
        """All verification tiers from Stage A preserved in Layer 2."""
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
        stage_a = StageAOutput(
            run_date="2026-08-20", fixtures_season="2627",
            leagues_scanned=["Test"], fixtures=fixtures,
            flags=[], stats={},
        )

        with patch("pipeline.production_stage_b._load_stage_a_output", return_value=stage_a), \
             patch("pipeline.production_stage_b._enrich_fixtures_with_models", side_effect=lambda board, *a, **k: (board, [])), \
             patch("pipeline.production_stage_b.build_production_bets", return_value=ProductionBets(
                 acca_a=None, split_accas=[], singles=[], watchlist=[])), \
             tempfile.TemporaryDirectory() as tmpdir:

            stage_a_path = Path(tmpdir) / "stage_a.json"
            stage_a.save(stage_a_path)

            output = run_stage_b(stage_a_path)

            output_tiers = [bf.verification.tier.value for bf in output.layer2.fixtures]
            assert output_tiers == tiers


class TestVehicleConstraint:
    """Tests for the 2 accas + 1 SLV vehicle constraint."""

    def _make_leg(self, fixture: str, league: str, market: str, price: float,
                   prob: float, edge: float, ev: float) -> AccaLeg:
        return AccaLeg(
            fixture=fixture,
            league=league,
            market_key=market,
            market_name=market,
            price=price,
            prob=prob,
            ev=ev,
            edge=edge,
            status="capital",
        )

    def test_vehicle_max_two_accas(self):
        """Vehicle constraint: max 2 accas (Acca A + Acca B)."""
        # Create enough legs for 3 accas
        legs_a = [self._make_leg(f"A{i} v B{i}", "PL", "HOME", 1.50, 0.70, 0.05, 0.10) for i in range(4)]
        legs_b = [self._make_leg(f"C{i} v D{i}", "PL", "DRAW", 1.60, 0.65, 0.04, 0.08) for i in range(4)]
        legs_c = [self._make_leg(f"E{i} v F{i}", "PL", "AWAY", 1.45, 0.75, 0.06, 0.12) for i in range(4)]
        singles = [self._make_leg(f"G{i} v H{i}", "PL", "OVER_25", 1.55, 0.68, 0.03, 0.06) for i in range(4)]

        prod = ProductionBets(
            acca_a=Acca(label="Acca A", legs=legs_a, combined_odds=5.0, combined_prob=0.15),
            split_accas=[
                Acca(label="Acca B", legs=legs_b, combined_odds=4.8, combined_prob=0.14),
                Acca(label="Acca C", legs=legs_c, combined_odds=4.5, combined_prob=0.13),
            ],
            singles=singles,
            watchlist=[],
        )

        acca_route = _build_acca_route(prod)

        # Only Acca A and Acca B should be kept
        assert acca_route.acca_a is not None
        assert acca_route.acca_b is not None
        assert acca_route.acca_a.label == "Acca A"
        assert acca_route.acca_b.label == "Acca B"
        # Acca C should be dropped (vehicle constraint: max 2 accas)

    def test_vehicle_one_slv(self):
        """Vehicle constraint: exactly 1 SLV (best single, highest edge)."""
        singles = [
            self._make_leg("Best v Single", "PL", "HOME", 1.50, 0.70, 0.05, 0.10),
            self._make_leg("Second v Single", "PL", "DRAW", 1.60, 0.65, 0.04, 0.08),
            self._make_leg("Third v Single", "PL", "AWAY", 1.45, 0.75, 0.06, 0.12),
        ]
        prod = ProductionBets(
            acca_a=None,
            split_accas=[],
            singles=singles,
            watchlist=[],
        )

        acca_route = _build_acca_route(prod)

        assert acca_route.slv is not None
        assert acca_route.slv.fixture == "Third v Single"  # Highest edge (0.06)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])