"""Tactical engine action tests (ID417).

Verifies the team-state -> goal-expectancy nudge path:
  - formation classification (defensive / attacking / none)
  - squad-change detection (prior hash differs -> penalty)
  - multiplicative, conservative scaling
  - HR35: absent data -> 1.0 (no nudge, never a guess)
  - integration with predict_adjusted (the same scale path as the promoted-club
    level adjustment, so the two can never drift apart on the marginals).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
import os

from engine import tactical as tx
from engine.dixon_coles import fit, predict, predict_adjusted
from data.football_data_source import MatchResult
from brain.store import Brain

_tmp = Path(tempfile.mkdtemp(prefix="olp_tactical_"))
_db = _tmp / "tactical_test.db"


def _mini_fit():
    """5-team, 10-match mini-league so a DC fit exists."""
    out = []
    teams = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    for i in range(len(teams) - 1):
        h, a = teams[i], teams[i + 1]
        for _ in range(2):
            out.append(MatchResult(league="Test", date=f"2025-0{i+1:02d}-01",
                                   home_team=h, away_team=a,
                                   fthg=2, ftag=1, ftr="H"))
    return fit(out)


# --- 1. formation classification --------------------------------------------
def test_formation_classification():
    assert tx._formation_direction("5-3-2") == "defensive"
    assert tx._formation_direction("4-5-1") == "defensive"
    assert tx._formation_direction("3-4-3") == "attacking"
    assert tx._formation_direction("4-3-3") == "attacking"
    assert tx._formation_direction("4-4-2") is None  # balanced -> no opinion
    assert tx._formation_direction(None) is None
    assert tx._formation_direction("") is None
    print("1. formation classification (defensive/attacking/none): OK")


# --- 2. formation scales -----------------------------------------------------
def test_formation_scales():
    d_scale, d_note = tx._formation_scale("5-3-2")
    assert d_scale == 1.0 - tx.FORMATION_GOAL_SHAVE, d_scale
    assert "defensive" in d_note
    a_scale, a_note = tx._formation_scale("3-4-3")
    assert a_scale == 1.0 + tx.FORMATION_GOAL_LIFT, a_scale
    assert "attacking" in a_note
    none_scale, none_note = tx._formation_scale("4-4-2")
    assert none_scale == 1.0 and none_note == ""
    print("2. formation scales (defensive shave / attacking lift / none=1.0): OK")


# --- 3. squad-change detection ----------------------------------------------
def test_squad_change_detection():
    s, note = tx._squad_change_scale("abc123", "abc123")  # unchanged
    assert s == 1.0 and note == ""
    s, note = tx._squad_change_scale("abc123", "xyz789")  # changed
    assert s == 1.0 - tx.SQUAD_CHANGE_PENALTY, s
    assert "turnover" in note
    s, note = tx._squad_change_scale("abc123", None)  # no prior
    assert s == 1.0 and note == ""
    print("3. squad-change detection (changed -> penalty, no-prior -> none): OK")


# --- 4. tactical_for_fixture multiplicative + provenance ---------------------
def test_tactical_for_fixture():
    # No signals -> 1.0 / 1.0, not applied
    adj = tx.tactical_for_fixture()
    assert adj.scale_home == 1.0 and adj.scale_away == 1.0
    assert not adj.applied

    # Defensive home + squad change -> home nudged down, away untouched
    adj = tx.tactical_for_fixture(
        home_formation="5-3-2", home_squad_hash="a", home_prior_hash="b")
    assert adj.scale_home < 1.0, adj.scale_home
    assert adj.scale_away == 1.0, adj.scale_away
    assert adj.applied
    assert "formation" in adj.provenance and "squad-change" in adj.provenance

    # Both formations known, no squad change -> formation only
    adj = tx.tactical_for_fixture(
        home_formation="3-4-3", away_formation="4-5-1")
    assert adj.scale_home > 1.0 and adj.scale_away < 1.0
    assert "formation" in adj.provenance
    assert "squad-change" not in adj.provenance
    print("4. tactical_for_fixture multiplicative + provenance: OK")


# --- 5. HR35: absent data never nudges --------------------------------------
def test_hr35_no_fabrication():
    for kwargs in [
        {}, {"home_formation": None, "away_formation": None,
             "home_squad_hash": None, "away_squad_hash": None},
        {"home_squad_hash": "", "away_squad_hash": ""},
    ]:
        adj = tx.tactical_for_fixture(**kwargs)
        assert adj.scale_home == 1.0 and adj.scale_away == 1.0
        assert adj.provenance == "tactical: none"
    print("5. HR35: absent team-state -> 1.0 (no fabrication): OK")


# --- 6. integration with predict_adjusted -----------------------------------
def test_integration_with_predict_adjusted():
    m = _mini_fit()
    raw = predict(m, "Bravo", "Charlie")
    assert raw is not None

    # A defensive home shape should reduce Bravo's goal expectancy and win chance.
    adj = tx.tactical_for_fixture(home_formation="5-3-2")
    out = predict_adjusted(m, "Bravo", "Charlie",
                           scale_home=adj.scale_home, scale_away=adj.scale_away)
    assert out is not None
    assert out.p_home < raw.p_home, f"{out.p_home} !< {raw.p_home}"
    # probabilities still sum to 1 (BUG2-safe) — re-predict not post-scale.
    total = out.p_home + out.p_draw + out.p_away
    assert abs(total - 1.0) < 1e-9, total
    print("6. tactical nudge via predict_adjusted lowers home win, sums to 1: OK")


# --- 7. brain persistence + prior-hash lookup -------------------------------
def test_brain_persistence_and_prior_lookup():
    brain = Brain(path=str(_db))
    # Two snapshots for Alpha so load_prior_hashes finds a prior squad_hash.
    brain.log_team_state(
        team="Alpha", league="Test", as_of="2026-08-01",
        squad_hash="hash_old", derived_formation="4-3-3")
    brain.log_team_state(
        team="Alpha", league="Test", as_of="2026-08-17",
        squad_hash="hash_new", derived_formation="5-3-2")
    brain.log_team_state(
        team="Bravo", league="Test", as_of="2026-08-17",
        squad_hash="hash_b", derived_formation="4-4-2")

    h_prior, a_prior = tx.load_prior_hashes(brain, "Alpha", "Bravo", "Test",
                                            as_of="2026-08-17")
    assert h_prior == "hash_old", h_prior  # prior snapshot for Alpha
    assert a_prior is None  # Bravo has only one snapshot
    print("7. brain persistence + prior-hash lookup: OK")


if __name__ == "__main__":
    test_formation_classification()
    test_formation_scales()
    test_squad_change_detection()
    test_tactical_for_fixture()
    test_hr35_no_fabrication()
    test_integration_with_predict_adjusted()
    test_brain_persistence_and_prior_lookup()
    print("\n[OK] ALL TACTICAL ENGINE TESTS PASSED")
