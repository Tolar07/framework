"""ClubElo stretch-fallback tests (Architect 2026-08-12).

The ClubElo fallback is the THIRD rung of the rating ladder (primary DC fit ->
carry-over fit -> ClubElo stretch). It is what keeps a fixture rated when both
the primary model and the carry-over model have no history for the teams: a
keyless current-season Elo snapshot is a REAL rating (ID414 — a seed IS a
rating), so the row is bookable instead of NO DATA. Per the ratified decision
the board LABELS it (rating_source="clubelo") so a stretch rating is never
mistaken for a fitted one, and its goals markets stay None (HR35: a 1X2-only
rating is never priced on a goals market it has no opinion on).

Under test (driving the real scan_one_league loop with mocked data sources):
  1. A fixture neither fit rates -> ClubElo produces a probability, the board
     stamps rating_source="clubelo", and goals markets are None.
  2. A fixture where EITHER side has no ClubElo rating stays NO DATA — PENDING
     (HR35 — a missing side is never guessed around).
"""
import sys
import tempfile
from pathlib import Path
from unittest import mock

# Fix __file__ when running via exec
if '__file__' not in globals():
    __file__ = r'c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv\tests\clubelo_fallback_test.py'

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import MatchResult
from engine.dixon_coles import fit
import orchestrator

# A 5-team mini-league (20 matches, >=4 per team) so a real DC fit exists. The
# stretch fixture ("Zeta" v "Omega") is NOT in the roster — neither the primary
# fit nor the carry-over fit can rate it, which is exactly the gap ClubElo fills.
_TEAMS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]


def _synthetic() -> list[MatchResult]:
    out = []
    i = 0
    for _round in range(2):
        for h in _TEAMS:
            for a in _TEAMS:
                if h >= a:
                    continue
                i += 1
                out.append(MatchResult(
                    league="Test", date=f"2025-{i % 12 + 1:02d}-01",
                    home_team=h, away_team=a, fthg=2, ftag=1, ftr="H"))
    return out


def _scan(elo_map: dict) -> tuple[list, list]:
    """Run the orchestrator's per-league scan with every real data source
    stubbed out: deterministic history (so fit/elo run for real), no xG, no
    SportyBet odds, and ClubElo elo_for served from `elo_map` (None = unrated)."""
    def elo_for(team):
        return elo_map.get(team)
    with mock.patch.object(orchestrator, "load_league",
                           return_value=(_synthetic(), [])), \
         mock.patch.object(orchestrator, "load_second_division",
                           return_value=([], [])), \
         mock.patch.object(orchestrator, "xg_source") as xg, \
         mock.patch.object(orchestrator, "get_sportybet_odds_for_leg",
                           return_value=None), \
         mock.patch.object(orchestrator.clubelo_source, "elo_for",
                           side_effect=elo_for):
        xg.is_covered.return_value = False
        return orchestrator.scan_one_league(
            "Test League", season="2525", upcoming_fixtures=[("Zeta", "Omega")],
            fixtures_season="2526", brain=None)


# --- 1. both sides rated -> stretch probability + stamp + goals None ---------
board, flags = _scan({"Zeta": 1700.0, "Omega": 1600.0})
assert len(board) == 1, f"expected one fixture row, got {len(board)}"
fx = board[0]
assert fx.probs is not None, "a ClubElo-rating fixture must be priced, not NO DATA"
assert fx.rating_source == "clubelo", \
    f"rating_source must be 'clubelo', got {fx.rating_source!r}"
# Zeta (1700) is favoured over Omega (1600) — the Elo gap must read through.
assert fx.probs.p_home > fx.probs.p_away, \
    "the higher-Elo side must be favoured"
# A 1X2-only stretch rating has NO goals opinion (HR35) — never priced on a
# market it can't back.
assert fx.probs.p_over_15 is None, "stretch rating must leave O1.5 None"
assert fx.probs.p_over_25 is None and fx.probs.p_over_35 is None, \
    "stretch rating must leave O2.5/O3.5 None"
assert fx.probs.p_btts_yes is None, "stretch rating must leave BTTS None"
assert any("ClubElo stretch fallback" in f for f in flags), \
    f"board must flag the stretch rating ({flags})"
print("1. ClubElo stretch: probability + rating_source='clubelo' + goals None: OK")

# --- 2. either side unrated -> honest NO DATA (HR35) -------------------------
for partial in ({"Zeta": 1700.0},             # away missing
                {"Omega": 1600.0},            # home missing
                {}):                          # both missing
    board, _ = _scan(partial)
    fx = board[0]
    assert fx.probs is None, \
        "a fixture with an unrated side must stay NO DATA (HR35)"
    assert fx.rating_source is None, "no rating -> no provenance stamp"
    assert fx.rejection_reason is not None, "unrated row needs an honest reason"
    assert "NO DATA — PENDING" in fx.rejection_reason, fx.rejection_reason
print("2. either side unrated -> NO DATA — PENDING, never a guess (HR35): OK")

# --- 3. a fixture the primary fit CAN rate bypasses ClubElo ------------------
# Bravo v Charlie are both in the fitted roster — the primary fit prices them,
# so ClubElo must NOT be consulted and the stamp stays None (a fitted DC rating
# is the canonical source).
def _scan_known() -> tuple[list, list]:
    def elo_for(team):  # would fire if the fallback ran — prove it doesn't
        raise AssertionError("ClubElo must not be consulted for a fitted fixture")
    with mock.patch.object(orchestrator, "load_league",
                           return_value=(_synthetic(), [])), \
         mock.patch.object(orchestrator, "load_second_division",
                           return_value=([], [])), \
         mock.patch.object(orchestrator, "xg_source") as xg, \
         mock.patch.object(orchestrator, "get_sportybet_odds_for_leg",
                           return_value=None), \
         mock.patch.object(orchestrator.clubelo_source, "elo_for",
                           side_effect=elo_for):
        xg.is_covered.return_value = False
        return orchestrator.scan_one_league(
            "Test League", season="2525",
            upcoming_fixtures=[("Bravo", "Charlie")], fixtures_season="2526",
            brain=None)

board, flags = _scan_known()
fx = board[0]
assert fx.probs is not None, "a fitted fixture must be priced"
assert fx.rating_source is None, \
    f"a primary-fit rating must stay un-stamped (None), got {fx.rating_source!r}"
assert fx.probs.p_over_15 is not None, "a DC fit carries its goals opinion"
assert not any("ClubElo" in f for f in flags), "no stretch flag for a fitted row"
print("3. primary-fit fixture priced canonically, ClubElo untouched: OK")

print("\nclubelo_fallback_test: ALL 3 PASSED")
