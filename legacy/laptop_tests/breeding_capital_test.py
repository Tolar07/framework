"""Breeding must never destroy capital or delete a surviving lineage.

On 2026-09-19 the real population bred 6 winners into an 8-slot cap. The loop
gave the first four two children each (8 entries), appended winners five and
six via its "population cap reached" guard, and then
`new_lineages[:MAX_LINEAGES]` sliced those two off. Two lineages that had WON
were deleted and 26.11 of bankroll disappeared — not staked, not debited, just
gone. The nightly scheduled run did this on every breed.

These tests pin the invariant that makes that impossible: a lineage's capital
may only leave the population by losing a bet.
"""
import pytest

from engine.heartbeat_lineage import (
    MAX_LINEAGES,
    OFFSPRING_PER_WIN,
    Lineage,
    LineagePopulation,
    breed_next_generation,
    save_population,
)


def _pop(n_winners: int, bankroll: float = 13.0, n_losers: int = 0):
    lineages = []
    for i in range(n_winners):
        lineages.append(Lineage(
            lineage_id=f"win{i:02d}", parent_id=None, generation=3,
            bankroll=bankroll + i, current_stake=1.0, wins=1, losses=0,
            alive=True, born_date="2026-09-17", last_result="WIN"))
    for i in range(n_losers):
        lineages.append(Lineage(
            lineage_id=f"dead{i:02d}", parent_id=None, generation=3,
            bankroll=5.0, current_stake=1.0, wins=0, losses=1,
            alive=False, born_date="2026-09-17", last_result="LOSS"))
    return LineagePopulation(lineages=lineages, last_bred_date=None)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Never touch the production lineage file from a test."""
    import engine.heartbeat_lineage as HL
    monkeypatch.setattr(HL, "LINEAGE_FILE", tmp_path / "lineage.json")


class TestCapitalConservation:
    @pytest.mark.parametrize("n_winners", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_bankroll_is_conserved_across_breeding(self, n_winners):
        pop = _pop(n_winners)
        before = round(sum(l.bankroll for l in pop.lineages if l.alive), 2)
        save_population(pop)
        after_pop = breed_next_generation(board=[], target_date="2026-09-20")
        after = round(sum(l.bankroll for l in after_pop.lineages if l.alive), 2)
        assert after == pytest.approx(before, abs=0.05), (
            f"{n_winners} winners: {before} in, {after} out — capital vanished")

    def test_the_2026_09_19_case_loses_nothing(self):
        """6 winners, 8 slots — the exact shape that lost 26.11."""
        pop = _pop(6)
        before = round(sum(l.bankroll for l in pop.lineages), 2)
        save_population(pop)
        after_pop = breed_next_generation(board=[], target_date="2026-09-20")
        after = round(sum(l.bankroll for l in after_pop.lineages if l.alive), 2)
        assert after == pytest.approx(before, abs=0.05)


class TestNoSurvivorDeleted:
    @pytest.mark.parametrize("n_winners", [5, 6, 7, 8])
    def test_every_winner_keeps_a_bloodline(self, n_winners):
        """A winner must appear in the next generation, as itself or a child."""
        pop = _pop(n_winners)
        save_population(pop)
        after = breed_next_generation(board=[], target_date="2026-09-20")
        alive = [l for l in after.lineages if l.alive]
        represented = {l.lineage_id for l in alive} | {
            l.parent_id for l in alive if l.parent_id}
        for i in range(n_winners):
            assert f"win{i:02d}" in represented, (
                f"win{i:02d} won and left no descendant — bloodline deleted")

    def test_population_respects_cap_when_it_can(self):
        pop = _pop(3)
        save_population(pop)
        after = breed_next_generation(board=[], target_date="2026-09-20")
        alive = [l for l in after.lineages if l.alive]
        assert len(alive) <= MAX_LINEAGES
        # 3 winners, 8 slots — every winner can afford the full offspring count
        assert len(alive) == 3 * OFFSPRING_PER_WIN

    def test_extinct_lineages_do_not_reproduce(self):
        pop = _pop(2, n_losers=3)
        save_population(pop)
        after = breed_next_generation(board=[], target_date="2026-09-20")
        alive = [l for l in after.lineages if l.alive]
        parents = {l.parent_id for l in alive if l.parent_id} | {
            l.lineage_id for l in alive}
        assert not any(p and p.startswith("dead") for p in parents)
