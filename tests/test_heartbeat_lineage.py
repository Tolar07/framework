"""
Tests for the heartbeat lineage survival/reproduction model.

Architect 2026-08-29 concept:
  WIN  -> lineage reproduces into OFFSPRING_PER_WIN offspring next generation
  LOSS -> lineage goes extinct
  starvation floor keeps the species alive after a wipeout
"""

import json
import sys
from pathlib import Path
from datetime import date

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import heartbeat_lineage as L
from output.heartbeat import HeartbeatFixture


def _make_board(n=6):
    """Build fake BoardFixture-like objects with positive edge + kickoff_date."""
    from types import SimpleNamespace

    board = []
    for i in range(n):
        board.append(SimpleNamespace(
            fixture=f"Team{i}A v Team{i}B",
            kickoff_date=date.today().isoformat(),
            kickoff_time="18:00",
            kickoff_utc=f"{date.today().isoformat()}T18:00:00Z",
            league="Test League",
            probs=SimpleNamespace(
                p_home=0.5 + i * 0.01, p_draw=0.2, p_away=0.3 - i * 0.01,
                p_over_15=0.7, p_over_25=0.5, p_over_35=0.3,
                p_btts_yes=0.6, p_btts_no=0.4,
            ),
            best_market=f"Over 2.5 goals",
            best_mes_ev=0.05 + i * 0.01,
            best_model_prob=0.5 + i * 0.01,
            best_bookmaker="TestBook",
            best_price=1.8 + i * 0.05,
            verification=SimpleNamespace(tier="TIER_A"),
            home_team=f"Team{i}A", away_team=f"Team{i}B",
        ))
    return board


@pytest.fixture
def clean_lineage(tmp_path, monkeypatch):
    """Point lineage state at a temp file and clear it before/after."""
    monkeypatch.setattr(L, "LINEAGE_FILE", tmp_path / "lineage.json")
    if L.LINEAGE_FILE.exists():
        L.LINEAGE_FILE.unlink()
    yield
    if L.LINEAGE_FILE.exists():
        L.LINEAGE_FILE.unlink()


class TestLineageSelection:
    def test_genesis_seeds_on_first_load(self, clean_lineage):
        pop = L.load_population()
        assert len(pop.lineages) == 1
        assert pop.living()[0].alive
        assert pop.living()[0].bankroll == L.DEFAULT_STARTING_BANKROLL

    def test_select_daily_returns_one_per_living_lineage(self, clean_lineage):
        board = _make_board(6)
        hbs = L.select_daily_heartbeats(board)
        assert len(hbs) == 1  # single genesis lineage -> one heartbeat
        assert isinstance(hbs[0], HeartbeatFixture)
        assert hbs[0].lineage_id is not None


class TestReproduction:
    def test_win_reproduces_into_two_offspring(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.last_result = "WIN"
        ln.bankroll = 110.0
        L.save_population(pop)

        pop2 = L.breed_next_generation([], target_date=date.today().isoformat())
        children = [x for x in pop2.lineages if x.parent_id == ln.lineage_id]
        assert len(children) == L.OFFSPRING_PER_WIN
        # bankroll split across offspring
        assert abs(sum(c.bankroll for c in children) - 110.0) < 0.5

    def test_loss_does_not_reproduce(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.last_result = "LOSS"
        ln.bankroll = 90.0
        L.save_population(pop)

        pop2 = L.breed_next_generation([], target_date=date.today().isoformat())
        assert all(x.parent_id != ln.lineage_id for x in pop2.lineages)

    def test_breed_is_idempotent_per_day(self, clean_lineage):
        pop = L.load_population()
        pop.living()[0].last_result = "WIN"
        pop.living()[0].bankroll = 110.0
        L.save_population(pop)

        d = date.today().isoformat()
        p1 = L.breed_next_generation([], target_date=d)
        p2 = L.breed_next_generation([], target_date=d)
        assert len(p1.lineages) == len(p2.lineages)


class TestExtinction:
    def test_extinction_when_bankroll_zero(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.bankroll = 0.0
        ln.alive = False
        L.save_population(pop)
        assert len(pop.living()) == 0

    def test_starvation_floor_reseeds(self, clean_lineage):
        pop = L.load_population()
        pop.lineages = []  # wipe everyone out
        L.save_population(pop)

        pop2 = L.breed_next_generation([], target_date=date.today().isoformat())
        assert len(pop2.living()) == 1
        assert pop2.living()[0].bankroll == L.STARVATION_FLOOR
        assert pop2.living()[0].parent_id is None


class TestResultProcessing:
    def test_record_win_grows_bankroll(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.current_stake = 1.0
        L.save_population(pop)

        hb = HeartbeatFixture(
            fixture="X v Y", kickoff_time="18:00", league="L",
            pick="Over 2.5", probability=0.6, edge=0.1, market_type="O/U",
            price=1.67, lineage_id=ln.lineage_id,
        )
        pop2 = L.record_heartbeat_result(hb, "WIN")
        same = next(x for x in pop2.lineages if x.lineage_id == ln.lineage_id)
        assert same.bankroll == pytest.approx(100.0 + 1.0 * (1.67 - 1.0), abs=0.05)
        assert same.wins == 1

    def test_record_loss_shrinks_bankroll(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.current_stake = 1.0
        L.save_population(pop)

        hb = HeartbeatFixture(
            fixture="X v Y", kickoff_time="18:00", league="L",
            pick="Over 2.5", probability=0.6, edge=0.1, market_type="O/U",
            price=1.67, lineage_id=ln.lineage_id,
        )
        pop2 = L.record_heartbeat_result(hb, "LOSS")
        same = next(x for x in pop2.lineages if x.lineage_id == ln.lineage_id)
        assert same.bankroll == pytest.approx(99.0, abs=0.05)
        assert same.losses == 1

    def test_record_loss_zero_bankroll_extinct(self, clean_lineage):
        pop = L.load_population()
        ln = pop.living()[0]
        ln.current_stake = 100.0
        ln.bankroll = 100.0
        L.save_population(pop)

        hb = HeartbeatFixture(
            fixture="X v Y", kickoff_time="18:00", league="L",
            pick="Over 2.5", probability=0.6, edge=0.1, market_type="O/U",
            price=1.67, lineage_id=ln.lineage_id,
        )
        pop2 = L.record_heartbeat_result(hb, "LOSS")
        same = next(x for x in pop2.lineages if x.lineage_id == ln.lineage_id)
        assert not same.alive


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
