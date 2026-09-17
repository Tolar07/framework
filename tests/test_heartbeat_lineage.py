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


# ---------------------------------------------------------------------------
# Regression tests — three defects the suite above did not catch (2026-09-17)
# ---------------------------------------------------------------------------
def test_win_without_price_does_not_debit_bankroll(clean_lineage):
    """A WIN must never REDUCE the bankroll.

    `price or 0.0` made an unpriced WIN pay stake * (0.0 - 1.0), debiting the
    lineage exactly as a LOSS would while still counting a win. Real instance
    in data/heartbeat/history.jsonl: 2026-08-27 "Brighton v Tromso", WIN,
    price null. Before the fix this assertion saw 99.0.
    """
    ln = L.Lineage(
        lineage_id="ln_nopr", parent_id=None, generation=0,
        bankroll=100.0, current_stake=1.0, wins=0, losses=0,
        alive=True, born_date=date.today().isoformat(),
    )
    L.save_population(L.LineagePopulation(lineages=[ln]))

    hb = HeartbeatFixture(
        fixture="Brighton v Tromso", kickoff_time="18:00", league="Test",
        pick="home", probability=0.6, edge=0.1, market_type="1X2", price=None,
    )
    hb.lineage_id = "ln_nopr"

    pop = L.record_heartbeat_result(hb, "WIN")
    won = pop.lineages[0]

    assert won.bankroll == 100.0, "an unpriced WIN must hold the bankroll flat, never debit it"
    assert won.wins == 1, "the win is still counted"
    assert won.unsettled_wins == 1, "and is flagged as unsettled rather than silently paid"
    assert won.alive is True


def test_priced_candidate_outranks_unpriced_favourite():
    """Edge and probability are different scales and must not be compared.

    The old scorer gave a priced fixture its EDGE (0.08) and an unpriced one
    its PROBABILITY (0.92), then compared them as plain floats — so the
    unpriced heavy favourite won every time, inverting the selection pressure.
    """
    from types import SimpleNamespace
    from output.heartbeat import select_top_heartbeats

    today = date.today().isoformat()
    common = dict(
        kickoff_date=today, kickoff_time="18:00",
        kickoff_utc=f"{today}T18:00:00Z", league="Test League",
        verification=SimpleNamespace(tier="TIER_A"),
    )
    unpriced_favourite = SimpleNamespace(
        fixture="BigFave v Minnow",
        probs=SimpleNamespace(p_home=0.92, p_draw=0.05, p_away=0.03),
        best_market=None, best_price=None, best_edge=None,
        best_mes_ev=None, best_model_prob=None, best_bookmaker=None,
        home_team="BigFave", away_team="Minnow", **common,
    )
    priced_value = SimpleNamespace(
        fixture="ValueHome v ValueAway",
        probs=SimpleNamespace(p_home=0.55, p_draw=0.25, p_away=0.20),
        best_market="ValueHome to win", best_price=2.10,
        best_edge=0.074, best_mes_ev=0.155, best_model_prob=0.55,
        best_bookmaker="TestBook",
        home_team="ValueHome", away_team="ValueAway", **common,
    )

    picks = select_top_heartbeats(
        [unpriced_favourite, priced_value], target_date=today, top_n=2,
    )

    assert picks, "expected candidates"
    assert picks[0].fixture == "ValueHome v ValueAway", (
        "the priced positive-edge fixture must rank above the unpriced favourite"
    )


def test_heartbeat_history_path_is_repo_rooted_not_cwd_relative():
    """Writer and reader must resolve the SAME file regardless of CWD.

    save_heartbeat_record() built Path("data/heartbeat") off the CWD while
    get_heartbeat_stats() resolved off __file__, so records written from any
    other directory were invisible to the reader. An orphan produced by that
    split still sits at the workspace root.
    """
    import output.heartbeat as H

    assert H.HISTORY_FILE.is_absolute(), "history path must not depend on the CWD"
    assert H.HISTORY_FILE == H.REPO_ROOT / "data" / "heartbeat" / "history.jsonl"
    assert H.HISTORY_FILE.parent == H.HEARTBEAT_DIR


def test_lineage_ledger_path_is_repo_rooted_not_cwd_relative():
    """Same defect class in the ledger this module exists to de-scatter."""
    import lineage_ledger

    assert lineage_ledger.LEDGER_PATH.is_absolute(), (
        "the lineage ledger must resolve to one file, not one per CWD"
    )


def test_lineage_state_survives_a_schema_addition(clean_lineage):
    """Older lineage.json (without newer fields) must load, not reseed genesis.

    from_dict used cls(**d); an unknown key would raise, be swallowed by the
    bare except in load_population, and silently WIPE the population back to
    a fresh genesis lineage — destroying the very history it preserves.
    """
    legacy = {
        "lineages": [{
            "lineage_id": "ln_legacy", "parent_id": None, "generation": 3,
            "bankroll": 42.5, "current_stake": 1.0, "wins": 5, "losses": 2,
            "alive": True, "born_date": "2026-09-01",
            "retired_field_from_the_future": "ignore me",
        }],
        "last_bred_date": "2026-09-01",
    }
    L.LINEAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    L.LINEAGE_FILE.write_text(json.dumps(legacy), encoding="utf-8")

    pop = L.load_population()

    assert len(pop.lineages) == 1
    assert pop.lineages[0].lineage_id == "ln_legacy", "must not reseed genesis"
    assert pop.lineages[0].bankroll == 42.5
    assert pop.lineages[0].unsettled_wins == 0, "new field defaults"


# ---------------------------------------------------------------------------
# Acca sizing — ratified Telegram spec §4.2 (LEGS_PER_ACCA = 5)
# ---------------------------------------------------------------------------
def test_acca_sizing_constants_are_not_shadowed():
    """Stage B must not redefine the engine's acca sizing with a different number.

    pipeline/production_stage_b.py declared its own ACCA_A_MAX = 4 and
    SPLIT_GROUP_TARGET = 4, shadowing engine.acca's 5s. Because Stage B passes
    its own values into build_production_bets, the engine's default never
    applied: calling the builder directly gave 5+5 while calling it through
    Stage B gave 4+6. A shadowed constant is invisible at the call site.
    """
    import engine.acca as A
    import pipeline.production_stage_b as P

    assert A.ACCA_A_MAX == 5, "spec §4.2: five legs per acca"
    assert A.SPLIT_GROUP_TARGET == 5
    assert P.ACCA_A_MAX == A.ACCA_A_MAX, (
        "Stage B must re-export the engine's constant, never redefine it"
    )
    assert P.SPLIT_GROUP_TARGET == A.SPLIT_GROUP_TARGET


def test_remainder_chunks_into_exact_fives():
    """Groups are exactly 5, except a deliberate 3-4 leg short tail.

    The old rule was "~4-5 legs, roughly": it permitted groups of SIX and split
    7 and 8 into 4+3 and 4+4, so the board printed accas of 4 and 6 against a
    spec that says 5.
    """
    from engine.acca import _chunk_remainder, SPLIT_GROUP_TARGET, MIN_SHORT_ACCA

    mk = lambda n: [object() for _ in range(n)]

    # 1-2 legs is a single, never an acca.
    assert _chunk_remainder(mk(1)) == []
    assert _chunk_remainder(mk(2)) == []

    for n in (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 16):
        sizes = [len(g) for g in _chunk_remainder(mk(n))]
        assert all(s <= SPLIT_GROUP_TARGET for s in sizes), (
            f"remainder {n} produced an oversized group: {sizes}"
        )
        assert all(s >= MIN_SHORT_ACCA for s in sizes), (
            f"remainder {n} produced a sub-minimum group: {sizes}"
        )
        # Every group except possibly the last must be a full five.
        assert all(s == SPLIT_GROUP_TARGET for s in sizes[:-1]), (
            f"remainder {n} produced a non-full group before the tail: {sizes}"
        )

    assert [len(g) for g in _chunk_remainder(mk(10))] == [5, 5]
    assert [len(g) for g in _chunk_remainder(mk(8))] == [5, 3]
    assert [len(g) for g in _chunk_remainder(mk(15))] == [5, 5, 5]


def test_acca_route_carries_up_to_four_accas():
    """MAX_ACCAS = 4 must be enforced by the ROUTE, not by two named fields.

    ProductionAccaRoute exposed only acca_a and acca_b, and _build_acca_route
    read accas[0]/accas[1] and dropped the rest. The cap was therefore enforced
    by the SHAPE of the return value, so raising the constant alone would have
    changed nothing visible. Architect ruling 2026-09-17 set it to 4.
    """
    from engine.acca import AccaLeg, Acca
    from pipeline.production_stage_b import _build_acca_route, VEHICLE_ACCA_MAX
    from output.production_board import MAX_ACCAS

    assert VEHICLE_ACCA_MAX == 4, "Architect ruling 2026-09-17"
    assert MAX_ACCAS == VEHICLE_ACCA_MAX, (
        "the board's label must match the cap the route actually applies"
    )

    def leg(i):
        return AccaLeg(fixture=f"H{i} v A{i}", league="La Liga", market_key="X",
                       market_name=f"Pick {i}", price=1.35, prob=0.80,
                       ev=0.08, edge=0.06)

    class _PB:
        acca_a = Acca(label="Acca A", legs=[leg(i) for i in range(5)])
        # Five more than the cap allows, so truncation is actually exercised.
        split_accas = [Acca(label=f"Acca {c}", legs=[leg(i) for i in range(5)])
                       for c in "BCDE"]
        singles = []
        watchlist = []

    route = _build_acca_route(_PB())
    assert len(route.accas) == 4, f"expected 4 accas, got {len(route.accas)}"
    assert [a.label for a in route.accas] == ["Acca A", "Acca B", "Acca C", "Acca D"]
    # acca_a/acca_b stay as views for existing readers.
    assert route.acca_a is route.accas[0]
    assert route.acca_b is route.accas[1]


def test_board_and_booking_payload_see_all_four_accas():
    """Accas C and D must reach BOTH the board and the booking payload.

    Reading acca_a/acca_b only would render four on the board and hand two to
    booking — visible to the Architect, silently unbookable.
    """
    import re
    from engine.acca import AccaLeg, Acca
    from types import SimpleNamespace
    from output.production_board import render_acca_route

    def leg(i):
        return AccaLeg(fixture=f"H{i} v A{i}", league="La Liga", market_key="X",
                       market_name=f"Pick {i}", price=1.35, prob=0.80,
                       ev=0.08, edge=0.06)

    accas = [Acca(label=f"Acca {c}", legs=[leg(i) for i in range(5)])
             for c in "ABCD"]
    route = SimpleNamespace(accas=accas, acca_a=accas[0], acca_b=accas[1],
                            slv=None, watchlist=[])

    rendered = re.findall(r"▸ (Acca [A-D]) — (\d+) legs", render_acca_route(route, 30))
    assert rendered == [("Acca A", "5"), ("Acca B", "5"),
                        ("Acca C", "5"), ("Acca D", "5")], rendered

    from run_daily import _acca_to_dict
    payload = [_acca_to_dict(a) for a in (getattr(route, "accas", None) or [])]
    assert len(payload) == 4, "booking payload must carry every formed acca"
    assert sum(len(a["legs"]) for a in payload) == 20
